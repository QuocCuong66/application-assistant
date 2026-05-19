import sys
import subprocess
import os

# --- TỰ ĐỘNG CÀI ĐẶT THƯ VIỆN ---
def install_dependencies():
    required = ["websockets", "pyautogui", "pynput"]
    for lib in required:
        try:
            __import__(lib)
        except ImportError:
            print(f"📦 Đang cài đặt thư viện {lib}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", lib])

install_dependencies()

import asyncio
import websockets
import json
import pyautogui
from pynput import mouse, keyboard
import platform
import time

# --- CẤU HÌNH ---
DEFAULT_SERVER = "ws://localhost:8000/automation/ws" 

class DesktopRecorder:
    def __init__(self):
        self.actions = []
        self.start_time = None
        self.is_recording = False
        self.mouse_listener = None
        self.keyboard_listener = None

    def _get_elapsed_time(self):
        return round(time.time() - self.start_time, 2)

    def on_click(self, x, y, button, pressed):
        if pressed and self.is_recording:
            self.actions.append({
                "action": "click",
                "parameters": {"x": x, "y": y, "button": str(button)},
                "time": self._get_elapsed_time()
            })

    def on_press(self, key):
        if self.is_recording:
            try:
                char = key.char
            except AttributeError:
                char = str(key)
            
            self.actions.append({
                "action": "type",
                "parameters": {"text": char},
                "time": self._get_elapsed_time()
            })

    def start_recording(self):
        if self.is_recording:
            return False
            
        self.actions = []
        self.start_time = time.time()
        self.is_recording = True
        
        self.mouse_listener = mouse.Listener(on_click=self.on_click)
        self.keyboard_listener = keyboard.Listener(on_press=self.on_press)
        
        self.mouse_listener.start()
        self.keyboard_listener.start()
        print("🔴 Đang ghi hình (Recording) thao tác chuột/bàn phím...")
        return True

    def stop_recording(self):
        if not self.is_recording:
            return None
            
        self.is_recording = False
        
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.keyboard_listener:
            self.keyboard_listener.stop()
            
        # Filter out actions in the last 1 second (usually the click to stop)
        if self.actions:
            end_time = self.actions[-1]["time"]
            self.actions = [a for a in self.actions if end_time - a["time"] > 1.0]
            
        print(f"⏹️ Đã dừng ghi hình. Thu thập được {len(self.actions)} hành động.")
        return self.actions

recorder = DesktopRecorder()

async def run_agent():
    print("========================================")
    print("   AI ASSISTANT - DESKTOP AGENT")
    print("========================================")
    
    server_url = input(f"Nhập Server URL (Để trống để dùng {DEFAULT_SERVER}): ").strip()
    if not server_url:
        server_url = DEFAULT_SERVER
        
    user_id = input("Nhập USER ID của bạn (Lấy từ giao diện web): ").strip()
    while not user_id:
        user_id = input("Lỗi: Bạn phải nhập USER ID để tiếp tục: ").strip()

    uri = f"{server_url}/{user_id}"
    print(f"\n🚀 Đang kết nối tới: {uri}...")
    
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                print("✅ Đã kết nối thành công! Agent đang lắng nghe lệnh từ Web...")
                
                while True:
                    message = await websocket.recv()
                    data = json.loads(message)
                    print(f"📩 Nhận lệnh: {data['type']}")

                    if data["type"] == "training_start":
                        recorder.start_recording()
                    
                    elif data["type"] == "training_stop":
                        actions = recorder.stop_recording()
                        if actions is not None:
                            task_name = data.get("task_name", "Untitled Task")
                            payload = {
                                "type": "save_task",
                                "task_name": task_name,
                                "actions": actions
                            }
                            await websocket.send(json.dumps(payload))
                            print(f"⬆️ Đã gửi dữ liệu '{task_name}' lên server.")
                        else:
                            print("⚠️ Không có task nào đang được record.")

                    elif data["type"] == "direct":
                        action = data["action"]
                        if action == "chrome":
                            if platform.system() == "Windows":
                                os.startfile("chrome.exe")
                            elif platform.system() == "Darwin":
                                subprocess.Popen(["open", "-a", "Google Chrome"])
                        elif action == "notepad":
                            if platform.system() == "Windows":
                                subprocess.Popen(["notepad.exe"])

                    elif data["type"] == "execution":
                        actions = data["actions"]
                        print(f"🚀 Đang thực thi Skill: {data.get('task_name', 'Unknown')} ({len(actions)} bước)")
                        
                        try:
                            last_time = 0
                            for step in actions:
                                delay = step["time"] - last_time
                                if delay > 0:
                                    time.sleep(delay)
                                
                                if step["action"] == "click":
                                    pyautogui.click(step["parameters"]["x"], step["parameters"]["y"])
                                elif step["action"] == "type":
                                    text = step["parameters"]["text"]
                                    if text.startswith("Key."):
                                        pyautogui.press(text.split(".")[1])
                                    else:
                                        pyautogui.write(text)
                                
                                last_time = step["time"]
                            print("✅ Thực thi hoàn tất.")
                        except Exception as e:
                            print(f"❌ Lỗi thực thi: {e}")

        except Exception as e:
            print(f"❌ Mất kết nối: {e}. Đang thử lại sau 5 giây...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    pyautogui.FAILSAFE = True
    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        print("\n👋 Đã đóng Agent.")
