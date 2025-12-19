import time
import tkinter as tk
import base64

import keyboard
import requests
import pyautogui
from PIL import Image


class ScreenshotTool:
    def __init__(self):
        # 创建主窗口
        self.root = tk.Tk()
        self.root.withdraw()

        # API配置
        self.api_url = "https://api.siliconflow.cn/v1/chat/completions"
        self.ocr_model = "deepseek-ai/DeepSeek-OCR"
        self.answer_model = "deepseek-ai/DeepSeek-V3.2"
        self.api_key = "sk-fwhgteweqhqfijpvqkqxgkpxbkvgkqktzxjjvbhkpowdxtif"
        print("使用在线大模型API进行文字识别")

        # 添加文本窗口引用
        self.text_window = None
        self.text_area = None

        # scrcpy窗口标题
        self.scrcpy_title = "2410DPN6CC"

    def capture_scrcpy_window(self):
        """找到scrcpy窗口并截图"""
        try:
            # 获取所有窗口
            windows = pyautogui.getWindowsWithTitle(self.scrcpy_title)

            if not windows:
                print(f"未找到标题包含 '{self.scrcpy_title}' 的窗口")
                print("可用窗口标题:")
                all_windows = pyautogui.getAllWindows()
                for win in all_windows:
                    if win.title:
                        print(f"  - {win.title}")
                return False

            # 选择第一个匹配的窗口
            window = windows[0]
            print(f"找到窗口: {window.title}")
            print(f"窗口位置和大小: x={window.left}, y={window.top}, width={window.width}, height={window.height}")

            # 激活窗口（确保在最前面）
            try:
                window.activate()
                time.sleep(0.3)  # 等待窗口激活
            except:
                print("无法激活窗口，可能已在最前面")

            # 截取窗口
            screenshot = pyautogui.screenshot(region=(window.left, window.top, window.width, window.height))

            # 保存截图
            filename = "scrcpy_screenshot.png"
            screenshot.save(filename)
            print(f"截图已保存: {filename}")

            # 对保存的图片进行 OCR 识别
            self.perform_ocr(filename)
            return True

        except Exception as e:
            print(f"截图scrcpy窗口失败: {e}")
            import traceback
            traceback.print_exc()
            return False

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
                "model": self.ocr_model,
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
                                "text": "识别图片里的文字题目问题和选项"
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
                        print(f"响应内容: {response.text[:500]}")
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
            "model": self.answer_model,
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


def main():
    screenshot_tool = ScreenshotTool()

    # 注册F4热键
    keyboard.on_press_key('F4', lambda _: screenshot_tool.capture_scrcpy_window())
    print("程序已启动，按 F4 键截取scrcpy窗口并进行OCR识别")

    # 保持程序运行
    screenshot_tool.root.mainloop()


if __name__ == "__main__":
    main()
