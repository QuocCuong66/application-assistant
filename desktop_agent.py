import sys
import subprocess
import os

# --- TỰ ĐỘNG CÀI ĐẶT THƯ VIỆN ---
def install_dependencies():
    required = ["websockets", "pyautogui", "pynput", "Pillow"]
    for lib in required:
        try:
            __import__(lib.lower() if lib != "Pillow" else "PIL")
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
import io
import base64
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

# --- CẤU HÌNH ---
DEFAULT_SERVER = os.getenv("BACKEND_WS_URL", "ws://localhost:8000/automation/ws")

# Biến toàn cục để tắt agent loop
EMERGENCY_STOP = False

def on_activate_h():
    global EMERGENCY_STOP
    print("\n🚨 [EMERGENCY STOP] Đã nhận lệnh dừng khẩn cấp!")
    EMERGENCY_STOP = True

def on_activate_resume():
    global EMERGENCY_STOP
    if EMERGENCY_STOP:
        print("\n✅ [RESUME] Đã reset cờ dừng khẩn cấp. Agent sẵn sàng nhận lệnh mới!")
        EMERGENCY_STOP = False

# Lắng nghe phím tắt khẩn cấp
hotkey_listener = keyboard.GlobalHotKeys({
    '<ctrl>+<alt>+q': on_activate_h,
    '<ctrl>+<alt>+r': on_activate_resume
})
hotkey_listener.start()

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
            
        if self.actions:
            end_time = self.actions[-1]["time"]
            self.actions = [a for a in self.actions if end_time - a["time"] > 1.0]
            
        print(f"⏹️ Đã dừng ghi hình. Thu thập được {len(self.actions)} hành động.")
        return self.actions

recorder = DesktopRecorder()

def handle_tool_call(tool, args):
    if tool == "screenshot":
        # Chụp ảnh và resize nếu màn hình quá lớn
        screenshot = pyautogui.screenshot()
        # Thay đổi kích thước để tiết kiệm token
        screenshot.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
        
        buffered = io.BytesIO()
        screenshot.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return {"data": img_str, "size": screenshot.size}
        
    elif tool == "click":
        x, y = args.get("x"), args.get("y")
        pyautogui.click(x, y)
        return {"status": "clicked", "x": x, "y": y}
        
    elif tool == "double_click":
        x, y = args.get("x"), args.get("y")
        pyautogui.doubleClick(x, y)
        return {"status": "double_clicked", "x": x, "y": y}
        
    elif tool == "type_text":
        text = args.get("text", "")
        # Thay vì gõ quá nhanh, set khoảng thời gian gõ để giống người
        for char in text:
            if EMERGENCY_STOP:
                return {"status": "error", "error": "Emergency stop active"}
            pyautogui.write(char)
            time.sleep(0.01)
        return {"status": "typed", "text": text}
        
    elif tool == "press":
        key = args.get("key")
        pyautogui.press(key)
        return {"status": "pressed", "key": key}
        
    elif tool == "hotkey":
        keys = args.get("keys", [])
        if isinstance(keys, list):
            pyautogui.hotkey(*keys)
        return {"status": "hotkey_executed", "keys": keys}
        
    elif tool == "scroll":
        amount = args.get("amount")
        pyautogui.scroll(amount)
        return {"status": "scrolled", "amount": amount}
        
    elif tool == "wait":
        seconds = args.get("seconds", 1)
        steps = int(seconds * 10)
        for _ in range(steps):
            if EMERGENCY_STOP:
                return {"status": "error", "error": "Emergency stop active"}
            time.sleep(0.1)
        return {"status": "waited", "seconds": seconds}
        
    elif tool == "open_app":
        app_name = args.get("app_name")
        if platform.system() == "Windows":
            # Cách an toàn để mở app trên win
            if "chrome" in app_name.lower():
                os.startfile("chrome.exe")
            elif "notepad" in app_name.lower():
                subprocess.Popen(["notepad.exe"])
            else:
                subprocess.Popen([app_name])
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", "-a", app_name])
        return {"status": "opened", "app_name": app_name}
    else:
        raise ValueError(f"Unknown tool: {tool}")

async def run_agent():
    global EMERGENCY_STOP
    print("========================================")
    print("   AI ASSISTANT - DESKTOP AGENT")
    print("   Hotkey khẩn cấp: Ctrl + Alt + Q để dừng AI")
    print("   Hotkey khôi phục: Ctrl + Alt + R để reset trạng thái")
    print("========================================")
    
    server_url = input(f"Nhập Server URL (Để trống để dùng {DEFAULT_SERVER}): ").strip()
    if not server_url:
        server_url = DEFAULT_SERVER
        
    user_id = input("Nhập USER ID của bạn (Lấy từ giao diện web): ").strip()
    while not user_id:
        user_id = input("Lỗi: Bạn phải nhập USER ID để tiếp tục: ").strip()

    agent_token = os.getenv("AGENT_TOKEN")
    if not agent_token:
        agent_token = input("Nhập AGENT_TOKEN (hoặc thêm vào .env): ").strip()

    uri = f"{server_url}/{user_id}?token={agent_token}"
    print(f"\n🚀 Đang kết nối tới: {uri}...")
    
    while True:
        try:
            async with websockets.connect(uri, max_size=20_000_000) as websocket: # 20MB limit for screenshots
                print("✅ Đã kết nối thành công! Agent đang lắng nghe lệnh từ Web...")
                
                while True:
                    # Reset emergency stop state upon reconnect/loop start
                    if EMERGENCY_STOP:
                        print("⏸️ Vẫn đang ở trạng thái dừng khẩn cấp. Không xử lý lệnh.")
                        await asyncio.sleep(1)
                        # Đợi đến khi có cơ chế reset, ở demo này tạm thời break
                        continue
                        
                    message = await websocket.recv()
                    data = json.loads(message)
                    msg_type = data.get('type')
                    print(f"📩 Nhận lệnh: {msg_type}")

                    if msg_type == "control" and data.get("command") == "stop":
                        print("🛑 Nhận lệnh Stop từ Server. Hủy tác vụ hiện tại.")
                        EMERGENCY_STOP = True
                        continue

                    if EMERGENCY_STOP:
                        print("🚨 Bỏ qua lệnh do đang bị Emergency Stop!")
                        if msg_type == "tool_call":
                            await websocket.send(json.dumps({
                                "type": "tool_result",
                                "request_id": data.get("request_id"),
                                "success": False,
                                "error": "Agent stopped by Emergency Hotkey"
                            }))
                        continue

                    if msg_type == "tool_call":
                        tool = data.get("tool")
                        args = data.get("args", {})
                        req_id = data.get("request_id")
                        print(f"🛠️ Thực thi tool: {tool} với args: {args}")
                        
                        try:
                            result = handle_tool_call(tool, args)
                            response = {
                                "type": "tool_result",
                                "request_id": req_id,
                                "success": True,
                                "result": result
                            }
                        except Exception as e:
                            print(f"❌ Lỗi tool {tool}: {e}")
                            response = {
                                "type": "tool_result",
                                "request_id": req_id,
                                "success": False,
                                "error": str(e)
                            }
                        
                        # Gửi lại kết quả
                        await websocket.send(json.dumps(response))

                    elif msg_type == "training_start":
                        recorder.start_recording()
                    
                    elif msg_type == "training_stop":
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

                    elif msg_type == "direct":
                        action = data["action"]
                        if action == "chrome":
                            if platform.system() == "Windows":
                                os.startfile("chrome.exe")
                            elif platform.system() == "Darwin":
                                subprocess.Popen(["open", "-a", "Google Chrome"])
                        elif action == "notepad":
                            if platform.system() == "Windows":
                                subprocess.Popen(["notepad.exe"])

                    elif msg_type == "execution":
                        actions = data["actions"]
                        print(f"🚀 Đang thực thi Skill: {data.get('task_name', 'Unknown')} ({len(actions)} bước)")
                        
                        try:
                            last_time = 0
                            for step in actions:
                                if EMERGENCY_STOP:
                                    print("🚨 Dừng thực thi khẩn cấp!")
                                    break
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
                            if not EMERGENCY_STOP:
                                print("✅ Thực thi hoàn tất.")
                        except Exception as e:
                            print(f"❌ Lỗi thực thi: {e}")

        except websockets.exceptions.ConnectionClosedError:
             print("❌ Mất kết nối WebSockets. Đang thử lại sau 5 giây...")
             await asyncio.sleep(5)
        except Exception as e:
            print(f"❌ Lỗi: {e}. Đang thử lại sau 5 giây...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    pyautogui.FAILSAFE = True
    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        print("\n👋 Đã đóng Agent.")

