import time
import tkinter as tk
import ctypes
import ctypes.wintypes
import base64

import keyboard
import requests
from PIL import ImageGrab
from pynput import mouse


class ScreenshotTool:
    def __init__(self):
        self.start_pos = None
        self.start_pos_logical = None
        self.is_capturing = False
        self.last_click_time = 0

        # 设置 DPI 感知
        self._set_dpi_awareness()

        # 创建主窗口
        self.root = tk.Tk()
        self.root.withdraw()
        self.selection_box = None
        self.overlay = None

        # 获取屏幕尺寸和缩放比例
        self._init_screen_info()

        # API配置（请替换为您自己的API key）
        self.api_url = "https://api.siliconflow.cn/v1/chat/completions"
        # 重要：请替换为您自己的API key
        self.api_key = "sk-fwhgteweqhqfijpvqkqxgkpxbkvgkqktzxjjvbhkpowdxtif"
        print("使用在线大模型API进行文字识别")

        # 添加文本窗口引用
        self.text_window = None
        self.text_area = None

    def _set_dpi_awareness(self):
        """设置 DPI 感知"""
        try:
            # 设置进程 DPI 感知
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # PROCESS_PER_MONITOR_DPI_AWARE
        except:
            try:
                # 备用方案
                ctypes.windll.user32.SetProcessDPIAware()
            except:
                print("无法设置 DPI 感知")

    def _init_screen_info(self):
        """初始化屏幕信息和缩放比例"""
        try:
            # 获取主显示器的物理尺寸
            user32 = ctypes.windll.user32
            self.physical_screen_width = user32.GetSystemMetrics(0)  # SM_CXSCREEN
            self.physical_screen_height = user32.GetSystemMetrics(1)  # SM_CYSCREEN

            # 获取逻辑尺寸
            self.logical_screen_width = self.root.winfo_screenwidth()
            self.logical_screen_height = self.root.winfo_screenheight()

            # 计算缩放比例
            self.scale_x = self.physical_screen_width / self.logical_screen_width
            self.scale_y = self.physical_screen_height / self.logical_screen_height

            print(f"物理屏幕尺寸: {self.physical_screen_width}x{self.physical_screen_height}")
            print(f"逻辑屏幕尺寸: {self.logical_screen_width}x{self.logical_screen_height}")
            print(f"缩放比例: {self.scale_x:.2f}x{self.scale_y:.2f}")

            # 使用物理尺寸作为屏幕尺寸
            self.screen_width = self.physical_screen_width
            self.screen_height = self.physical_screen_height

        except Exception as e:
            print(f"获取屏幕信息失败: {e}")
            # 备用方案：使用逻辑尺寸
            self.screen_width = self.root.winfo_screenwidth()
            self.screen_height = self.root.winfo_screenheight()
            self.scale_x = 1.0
            self.scale_y = 1.0

    def _logical_to_physical(self, x, y):
        """将逻辑坐标转换为物理坐标"""
        return int(x * self.scale_x), int(y * self.scale_y)

    def _physical_to_logical(self, x, y):
        """将物理坐标转换为逻辑坐标"""
        return int(x / self.scale_x), int(y / self.scale_y)

    def create_overlay(self):
        # 创建全屏半透明遮罩
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes('-alpha', 0.3)
        self.overlay.attributes('-topmost', True)
        self.overlay.attributes('-fullscreen', True)
        self.overlay.overrideredirect(True)
        self.overlay.configure(bg='black')

        # 创建一个全屏的 Frame 来捕获所有鼠标事件
        self.overlay_frame = tk.Frame(self.overlay)
        self.overlay_frame.pack(fill='both', expand=True)

        # 绑定所有需要的事件
        for widget in (self.overlay, self.overlay_frame):
            widget.bind('<Button-1>', self._on_overlay_click)
            widget.bind('<ButtonRelease-1>', self._on_overlay_release)
            widget.bind('<Motion>', self._on_overlay_motion)
            widget.bind('<Button-3>', lambda e: self.cancel_capture())  # 返回值会自动传递
            widget.bind('<Escape>', lambda e: self.cancel_capture())
            # 禁用右键菜单
            widget.bind('<Button-3>', lambda e: 'break', add='+')

    def _on_overlay_click(self, event):
        """处理遮罩层的鼠标点击事件"""
        if not self.is_capturing:
            return 'break'

        current_time = time.time()
        if current_time - self.last_click_time < 0.5:
            self.capture_fullscreen()
            return 'break'

        self.last_click_time = current_time
        # 将逻辑坐标转换为物理坐标用于截图
        physical_x, physical_y = self._logical_to_physical(event.x_root, event.y_root)
        self.start_pos = (physical_x, physical_y)
        # 但选择框仍使用逻辑坐标
        self.start_pos_logical = (event.x_root, event.y_root)
        self.create_selection_box()
        return 'break'

    def _on_overlay_release(self, event):
        """处理遮罩层的鼠标释放事件"""
        if not self.is_capturing or not self.start_pos:
            return 'break'

        # 将逻辑坐标转换为物理坐标用于截图
        physical_x, physical_y = self._logical_to_physical(event.x_root, event.y_root)
        end_pos = (physical_x, physical_y)

        if self.selection_box:
            self.selection_box.destroy()
        if self.overlay:
            self.overlay.destroy()
        self.capture_area(self.start_pos, end_pos)
        self.is_capturing = False
        return 'break'

    def _on_overlay_motion(self, event):
        """处理遮罩层的鼠标移动事件"""
        if not self.is_capturing or not self.start_pos_logical:
            return 'break'

        x, y = event.x_root, event.y_root
        if (x, y) != self.start_pos_logical and self.start_pos_logical != (0, 0):
            left = min(x, self.start_pos_logical[0])
            top = min(y, self.start_pos_logical[1])
            width = abs(x - self.start_pos_logical[0])
            height = abs(y - self.start_pos_logical[1])

            if width < 1 or height < 1:
                return 'break'

            geometry = f'{width}x{height}+{left}+{top}'
            self.selection_box.geometry(geometry)
            self.draw_selection_border(width, height)
        return 'break'

    def create_selection_box(self):
        if self.selection_box:
            self.selection_box.destroy()
        self.selection_box = tk.Toplevel(self.root)
        self.selection_box.attributes('-topmost', True)
        self.selection_box.overrideredirect(True)
        # 设置选择框完全透明
        self.selection_box.attributes('-alpha', 1.0)
        self.selection_box.attributes('-transparentcolor', 'white')

        # 创建画布用于绘制边框，设置白色背景
        self.canvas = tk.Canvas(self.selection_box, highlightthickness=0, bg='white')
        self.canvas.pack(fill='both', expand=True)

        # 为所有子组件绑定右键阻止事件
        for widget in (self.selection_box, self.canvas):
            widget.bind('<Button-3>', lambda e: 'break', add='+')  # 先阻止默认行为
            widget.bind('<Button-3>', lambda e: self.cancel_capture(), add='+')  # 再执行取消
            widget.bind('<Escape>', lambda e: self.cancel_capture())

    def draw_selection_border(self, width, height):
        self.canvas.delete('all')
        # 绘制边框
        self.canvas.create_rectangle(
            1, 1, width - 2, height - 2,  # 稍微内缩一点，避免边框被透明化
            outline='#00B7FF',
            width=2
        )

        # 绘制四角小方块
        square_size = 4
        corner_positions = [
            (0, 0), (width / 2, 0), (width - square_size, 0),  # 上边
            (0, height / 2), (width - square_size, height / 2),  # 中间
            (0, height - square_size), (width / 2, height - square_size), (width - square_size, height - square_size)
            # 下边
        ]

        for x, y in corner_positions:
            self.canvas.create_rectangle(
                x, y, x + square_size, y + square_size,
                fill='#00B7FF',  # 改用蓝色填充，避免被透明化
                outline='#00B7FF'
            )

    def on_click(self, x, y, button, pressed):
        if not self.is_capturing:
            return

        try:
            # 检测右键点击取消截图
            if button == mouse.Button.right and pressed:
                self.cancel_capture()
                return

            # 检测左键操作
            if button == mouse.Button.left:
                current_time = time.time()
                if pressed:
                    # 检测双击（两次点击间隔小于0.5秒）
                    if current_time - self.last_click_time < 0.5:
                        self.capture_fullscreen()  # 双击截取全屏
                        return
                    self.last_click_time = current_time
                    # pynput 的坐标已经是物理坐标，直接使用
                    self.start_pos = (x, y)
                    # 转换为逻辑坐标用于选择框显示
                    logical_x, logical_y = self._physical_to_logical(x, y)
                    self.start_pos_logical = (logical_x, logical_y)
                    self.create_selection_box()
                else:
                    # 如果没有起始位置，说明可能是双击或其他情况
                    if not self.start_pos:
                        return
                    # pynput 的坐标已经是物理坐标
                    end_pos = (x, y)
                    # 确保在释放鼠标时清理窗口
                    if self.selection_box:
                        self.selection_box.destroy()
                    if self.overlay:
                        self.overlay.destroy()
                    # 尝试截图
                    self.capture_area(self.start_pos, end_pos)
                    self.is_capturing = False
        except Exception as e:
            print(f"鼠标事件处理出错: {e}")
            self.cancel_capture()  # 出错时取消截图

    def on_move(self, x, y):
        if self.is_capturing and self.start_pos_logical and self.selection_box:
            # 将物理坐标转换为逻辑坐标用于选择框显示
            logical_x, logical_y = self._physical_to_logical(x, y)
            # 如果鼠标移动且不在原始位置，且不是初始全屏状态
            if (logical_x, logical_y) != self.start_pos_logical and self.start_pos_logical != (0, 0):
                # 计算选择框的位置和大小（使用逻辑坐标）
                left = min(logical_x, self.start_pos_logical[0])
                top = min(logical_y, self.start_pos_logical[1])
                width = abs(logical_x - self.start_pos_logical[0])
                height = abs(logical_y - self.start_pos_logical[1])

                if width < 1 or height < 1:
                    return

                # 更新选择框位置和大小
                geometry = f'{width}x{height}+{left}+{top}'
                self.selection_box.geometry(geometry)

                # 更新边框
                self.draw_selection_border(width, height)
                self.selection_box.lift()  # 确保选择框在最上层

                # 确保窗口可见
                self.selection_box.deiconify()
                if self.overlay:
                    self.overlay.deiconify()
                    self.overlay.lift()  # 确保遮罩在选择框下方
                    self.selection_box.lift()  # 再次确保选择框在最上层

    def show_text_window(self, text):
        """显示识别到的文本窗口"""
        try:
            # 检查窗口是否存在并且有效
            window_exists = False
            try:
                window_exists = self.text_window is not None and self.text_window.winfo_exists() and self.text_window.winfo_viewable()
            except:
                window_exists = False

            if not window_exists:
                # 创建新窗口
                self.text_window = tk.Toplevel(self.root)
                self.text_window.title("答题助手")
                self.text_window.geometry("800x600")
                self.text_window.attributes('-topmost', True)  # 确保窗口在最上层

                # 创建文本框
                self.text_area = tk.Text(self.text_window, wrap=tk.WORD)
                self.text_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

                # 创建按钮框架
                button_frame = tk.Frame(self.text_window)
                button_frame.pack(fill=tk.X, padx=10, pady=5)

                # 复制按钮
                copy_button = tk.Button(
                    button_frame,
                    text="复制到剪贴板",
                    command=lambda: [self.root.clipboard_clear(),
                                     self.root.clipboard_append(self.text_area.get("1.0", tk.END)),
                                     print("文本已复制到剪贴板")]
                )
                copy_button.pack(side=tk.LEFT, padx=5)

                # 关闭按钮
                close_button = tk.Button(
                    button_frame,
                    text="关闭",
                    command=lambda: [self.text_window.withdraw(), self.text_window.update()]  # 隐藏而不是销毁
                )
                close_button.pack(side=tk.RIGHT, padx=5)

                # 设置窗口位置在屏幕右侧
                self.text_window.update_idletasks()
                width = self.text_window.winfo_width()
                height = self.text_window.winfo_height()
                screen_width = self.text_window.winfo_screenwidth()
                screen_height = self.text_window.winfo_screenheight()

                x = screen_width - width - 150
                y = (screen_height - height) // 2

                self.text_window.geometry(f'+{x}+{y}')

                # 处理窗口关闭按钮事件
                self.text_window.protocol("WM_DELETE_WINDOW",
                                          lambda: [self.text_window.withdraw(), self.text_window.update()])
            else:
                # 如果窗口已经存在，确保它可见
                self.text_window.deiconify()

            # 清空文本框并插入新文本
            self.text_area.delete("1.0", tk.END)
            self.text_area.insert(tk.END, text)

            # 确保窗口可见并在最前
            self.text_window.lift()
            self.text_window.focus_force()

        except Exception as e:
            print(f"创建文本窗口失败: {e}")

    def perform_ocr(self, image_path):
        """使用在线大模型API对图片进行文字识别"""
        try:
            # 读取图片并转换为base64
            with open(image_path, 'rb') as f:
                image_data = f.read()
                base64_image = base64.b64encode(image_data).decode('utf-8')

            # 构建请求数据
            payload = {
                "max_tokens": 4096,
                "temperature": 0,
                "top_p": 0.7,
                "top_k": 50,
                "frequency_penalty": 0,
                "chat_id": "N0P6u00",
                "model": "deepseek-ai/DeepSeek-OCR",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            },
                            {
                                "type": "text",
                                "text": "识别题目问题和选项"
                            }
                        ]
                    }
                ]
            }
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            print("正在调用在线OCR API...")

            # 发送请求（添加超时）
            try:
                response = requests.post(self.api_url, json=payload, headers=headers, timeout=30)
                print(f"API响应状态码: {response.status_code}")

                # 检查响应状态
                if response.status_code == 200:
                    try:
                        result = response.json()
                        # 提取识别到的文本
                        full_text = result['choices'][0]['message']['content']
                        print("OCR 识别结果:")
                        print(full_text)
                    except ValueError as json_error:
                        print(f"JSON解析失败: {json_error}")
                        print(f"响应内容: {response.text[:500]}")  # 打印前500字符
                        return
                else:
                    print(f"API调用失败: HTTP {response.status_code}")
                    print(f"响应内容: {response.text[:500]}")  # 打印前500字符
                    return
            except requests.exceptions.Timeout:
                print("API请求超时（30秒）")
                return
            except requests.exceptions.RequestException as req_error:
                print(f"API请求异常: {req_error}")
                return

            # 先显示问题和加载提示
            loading_text = f"--------------------问题--------------------\n{full_text}\n\n--------------------答案--------------------\n正在获取答案..."
            self.root.after(100, lambda: self.show_text_window(loading_text))

            # 获取API答案
            try:
                def update_answer():
                    try:
                        answer = self.get_answer(full_text)
                        # 组合显示文本
                        display_text = f"--------------------问题--------------------\n{full_text}\n\n--------------------答案--------------------\n{answer}"
                        # 更新文本窗口
                        if self.text_area:
                            self.text_area.delete("1.0", tk.END)
                            self.text_area.insert(tk.END, display_text)
                    except Exception as e:
                        print(f"获取答案失败: {e}")
                        # 如果获取答案失败，显示错误信息
                        error_text = f"--------------------问题--------------------\n{full_text}\n\n--------------------答案--------------------\n获取答案失败: {e}"
                        if self.text_area:
                            self.text_area.delete("1.0", tk.END)
                            self.text_area.insert(tk.END, error_text)

                # 在主线程中执行更新
                self.root.after(200, update_answer)

            except Exception as e:
                print(f"获取答案失败: {e}")

            # 自动复制到剪贴板
            self.root.clipboard_clear()
            self.root.clipboard_append(full_text)
            print("文本已复制到剪贴板")

        except Exception as e:
            print(f"在线OCR识别失败: {e}")
            import traceback
            traceback.print_exc()

    def get_answer(self, text):
        url = "https://api.siliconflow.cn/v1/chat/completions"

        payload = {
            "model": "deepseek-ai/DeepSeek-V3.2",
            "messages": [
                {
                    "role": "system",
                    "content": "我想让你担任答题助手。我将为您提供问题和答案选项，您的任务是帮助我选出正确答案，然后只需要回答我正确答案选择什么选项。我的第一个请求是"
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            "stream": False,
            "max_tokens": 512,
            "stop": ["null"],
            "temperature": 0.7,
            "top_p": 0.7,
            "top_k": 50,
            "frequency_penalty": 0.5,
            "n": 1,
            "response_format": {"type": "text"}
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        response = requests.request("POST", url, json=payload, headers=headers)
        res = response.json()
        answer = res['choices'][0]['message']['content']
        print(answer)
        return answer

    def capture_area(self, start_pos, end_pos):
        if not start_pos:
            return

        try:
            # 如果是初始全屏状态，使用全屏坐标
            if start_pos == (0, 0):
                left, top = 0, 0
                right, bottom = self.screen_width, self.screen_height
            else:
                # start_pos 和 end_pos 已经是物理坐标，直接使用
                # 确保坐标正确（处理从右下往左上拖动的情况）
                left = max(0, min(start_pos[0], end_pos[0]))
                top = max(0, min(start_pos[1], end_pos[1]))
                right = min(self.screen_width, max(start_pos[0], end_pos[0]))
                bottom = min(self.screen_height, max(start_pos[1], end_pos[1]))

            width = right - left
            height = bottom - top

            # 检查截图区域是否有效
            if width < 1 or height < 1:
                print("截图区域太小")
                return

            print(f"截图区域: ({left}, {top}) -> ({right}, {bottom}), 尺寸: {width}x{height}")

            # 截图
            try:
                screenshot = ImageGrab.grab(bbox=(int(left), int(top), int(right), int(bottom)))

                # 生成文件名
                filename = "screenshot.png"

                # 保存截图
                screenshot.save(filename)
                print(f"截图已保存: {filename}")

                # 对保存的图片进行 OCR 识别
                self.perform_ocr(filename)

            except Exception as e:
                print(f"截图失败: {e}")

        except Exception as e:
            print(f"截图过程出错: {e}")
        finally:
            # 清空拖拽信息
            self.start_pos = None
            self.start_pos_logical = None
            if self.selection_box:
                self.selection_box.destroy()
                self.selection_box = None

    def cancel_capture(self):
        """取消截图"""
        if self.selection_box:
            self.selection_box.destroy()
            self.selection_box = None
        if self.overlay:
            self.overlay.destroy()
            self.overlay = None
        self.is_capturing = False
        self.start_pos = None
        self.start_pos_logical = None
        self.last_click_time = 0
        return 'break'  # 阻止事件继续传播

    def start_capture(self):
        # 如果已经在截图中，则忽略新的触发
        if self.is_capturing:
            return
        self.is_capturing = True
        self.create_overlay()

        # 设置焦点以接收键盘事件
        self.overlay.focus_force()

    def capture_fullscreen(self):
        """截取全屏"""
        try:
            # 清理窗口
            if self.selection_box:
                self.selection_box.destroy()
                self.selection_box = None
            if self.overlay:
                self.overlay.destroy()
                self.overlay = None

            # 等待一小段时间确保窗口已清理
            self.root.update()
            time.sleep(0.1)  # 给窗口清理一点时间

            # 截取全屏
            screenshot = ImageGrab.grab()  # 不指定 bbox 就是全屏

            # 生成文件名
            # filename = f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            filename = "screenshot.png"

            # 保存截图
            screenshot.save(filename)
            print(f"全屏截图已保存: {filename}")

        except Exception as e:
            print(f"全屏截图失败: {e}")
        finally:
            # 清理状态
            self.start_pos = None
            self.start_pos_logical = None
            self.is_capturing = False
            self.last_click_time = 0


def main():
    screenshot_tool = ScreenshotTool()

    # 注册F4热键
    keyboard.on_press_key('F4', lambda _: screenshot_tool.start_capture())

    # 保持程序运行
    screenshot_tool.root.mainloop()


if __name__ == "__main__":
    main()
