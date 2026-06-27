import sys
import subprocess
import os

# --- TỰ ĐỘNG CÀI ĐẶT THƯ VIỆN ---
def install_dependencies():
    required = ["websockets", "pyautogui", "pynput", "Pillow", "pyperclip", "requests", "python-dotenv"]
    import_names = {
        "Pillow": "PIL",
        "python-dotenv": "dotenv",
    }
    for lib in required:
        mod = import_names.get(lib, lib.lower())
        try:
            __import__(mod)
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
import requests
from PIL import Image
from dotenv import load_dotenv
import getpass

load_dotenv()

# --- CẤU HÌNH ---
DEFAULT_SERVER = os.getenv("BACKEND_WS_URL", "ws://localhost:8000/automation/ws")
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_FILE = os.path.join(AGENT_DIR, "agent_session.json")

# --- QUẢN LÝ SESSION ---
def _ws_url_to_http(ws_url: str) -> str:
    """Chuyển ws://host/automation/ws → http://host"""
    url = ws_url.replace("wss://", "https://").replace("ws://", "http://")
    # Bỏ path /automation/ws để lấy base URL
    idx = url.find("/automation/ws")
    if idx != -1:
        url = url[:idx]
    return url

def load_session() -> dict | None:
    """Đọc session từ file local. Trả về dict hoặc None."""
    if not os.path.exists(SESSION_FILE):
        return None
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Kiểm tra các trường bắt buộc
        if data.get("user_id") and data.get("auth_token"):
            return data
    except (json.JSONDecodeError, IOError):
        pass
    return None

def save_session(user_id: str, auth_token: str, username: str, server_url: str, autostart: bool = False):
    """Lưu session vào file local."""
    data = {
        "user_id": user_id,
        "auth_token": auth_token,
        "username": username,
        "server_url": server_url,
        "autostart": autostart
    }
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"💾 Đã lưu session cho user '{username}'.")

def delete_session():
    """Xóa session file khi token hết hạn."""
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)
        print("🗑️ Đã xóa session cũ.")

def login_via_api(server_url: str) -> dict | None:
    """Đăng nhập qua REST API, trả về {user_id, auth_token, username}."""
    base_url = _ws_url_to_http(server_url)
    print(f"\n🔐 Đăng nhập vào server: {base_url}")
    print("─" * 40)

    username = input("   👤 Username: ").strip()
    password = getpass.getpass("   🔑 Password: ").strip()

    if not username or not password:
        print("   ❌ Username và password không được để trống!")
        return None

    # Bước 1: POST /auth/login → lấy token
    try:
        resp = requests.post(
            f"{base_url}/auth/login",
            json={"username": username, "password": password},
            timeout=15
        )
        if resp.status_code != 200:
            detail = resp.json().get("detail", resp.text) if resp.headers.get("content-type", "").startswith("application/json") else resp.text
            print(f"   ❌ Đăng nhập thất bại: {detail}")
            return None
        token = resp.json().get("token")
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Không thể kết nối tới {base_url}. Server đang offline?")
        return None
    except Exception as e:
        print(f"   ❌ Lỗi đăng nhập: {e}")
        return None

    # Bước 2: GET /auth/me → lấy user_id
    try:
        resp = requests.get(
            f"{base_url}/auth/me",
            headers={"X-Token": token},
            timeout=15
        )
        if resp.status_code != 200:
            print(f"   ❌ Không thể lấy thông tin user: {resp.text}")
            return None
        user_data = resp.json()
        user_id = user_data.get("id")
    except Exception as e:
        print(f"   ❌ Lỗi lấy thông tin user: {e}")
        return None

    print(f"   ✅ Đăng nhập thành công! User: {username} (ID: {user_id[:8]}...)")
    return {"user_id": user_id, "auth_token": token, "username": username}

# --- AUTO-START WINDOWS ---
def _get_startup_folder() -> str | None:
    """Lấy đường dẫn thư mục Startup của Windows."""
    if platform.system() != "Windows":
        return None
    return os.path.join(os.environ.get("APPDATA", ""), 
                        "Microsoft", "Windows", "Start Menu", "Programs", "Startup")

def setup_autostart():
    """Tạo file .vbs trong Startup để tự chạy agent khi bật Windows."""
    startup = _get_startup_folder()
    if not startup:
        print("   ⚠️ Auto-start chỉ hỗ trợ Windows.")
        return False
    
    vbs_path = os.path.join(startup, "DesktopAgent.vbs")
    agent_path = os.path.abspath(__file__)
    python_path = sys.executable
    agent_dir = os.path.dirname(agent_path)
    
    vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "{agent_dir}"
WshShell.Run """{python_path}"" ""{agent_path}""", 0, False
'''
    try:
        with open(vbs_path, "w", encoding="utf-8") as f:
            f.write(vbs_content)
        print(f"   ✅ Đã thiết lập auto-start tại: {vbs_path}")
        return True
    except Exception as e:
        print(f"   ❌ Lỗi tạo auto-start: {e}")
        return False

def remove_autostart():
    """Gỡ bỏ auto-start."""
    startup = _get_startup_folder()
    if not startup:
        return
    vbs_path = os.path.join(startup, "DesktopAgent.vbs")
    if os.path.exists(vbs_path):
        os.remove(vbs_path)
        print("   🗑️ Đã gỡ bỏ auto-start.")

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
        original_size = screenshot.size
        # Thay đổi kích thước để tiết kiệm token
        screenshot.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
        
        buffered = io.BytesIO()
        screenshot.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return {"data": img_str, "size": screenshot.size, "original_size": original_size}
        
    elif tool == "click":
        x, y = args.get("x"), args.get("y")
        pyautogui.click(x, y)
        return {"status": "clicked", "x": x, "y": y}
        
    elif tool == "double_click":
        x, y = args.get("x"), args.get("y")
        pyautogui.doubleClick(x, y)
        return {"status": "double_clicked", "x": x, "y": y}

    elif tool == "right_click":
        x, y = args.get("x"), args.get("y")
        pyautogui.rightClick(x, y)
        return {"status": "right_clicked", "x": x, "y": y}

    elif tool == "move":
        x, y = args.get("x"), args.get("y")
        pyautogui.moveTo(x, y)
        return {"status": "moved", "x": x, "y": y}

    elif tool == "drag":
        x, y = args.get("x"), args.get("y")
        pyautogui.dragTo(x, y)
        return {"status": "dragged", "x": x, "y": y}
        
    elif tool == "type_text":
        text = args.get("text", "")
        if EMERGENCY_STOP:
            return {"status": "error", "error": "Emergency stop active"}
        # Sử dụng clipboard để hỗ trợ Unicode đầy đủ
        try:
            import pyperclip
            pyperclip.copy(text)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.05)
        except ImportError:
            # Fallback: gõ từng ký tự nếu không có pyperclip
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
    print("╔══════════════════════════════════════════╗")
    print("║     AI ASSISTANT - DESKTOP AGENT         ║")
    print("║  Ctrl+Alt+Q  → Dừng khẩn cấp            ║")
    print("║  Ctrl+Alt+R  → Khôi phục trạng thái      ║")
    print("╚══════════════════════════════════════════╝")
    
    # --- Xác định Server URL ---
    server_url = os.getenv("BACKEND_WS_URL")
    if not server_url:
        print("\n⚠️  BACKEND_WS_URL chưa cấu hình trong .env.")
        print("   → Fallback: ws://localhost:8000/automation/ws")
        server_url = "ws://localhost:8000/automation/ws"
    else:
        print(f"\n🌐 Server: {server_url}")

    # --- Đăng nhập / Đọc Session ---
    agent_token = os.getenv("AGENT_TOKEN", "default-secret-token-123")
    session = load_session()

    if session:
        user_id = session["user_id"]
        username = session.get("username", "?")
        # Dùng server_url từ session nếu .env không có
        if session.get("server_url"):
            server_url = session["server_url"]
        print(f"📂 Session tìm thấy: {username} (ID: {user_id[:8]}...)")
        print(f"   → Tự động kết nối, không cần đăng nhập lại.")
    else:
        print("\n📋 Chưa có session. Cần đăng nhập lần đầu.")
        while True:
            credentials = login_via_api(server_url)
            if credentials:
                user_id = credentials["user_id"]
                username = credentials["username"]
                
                # Hỏi auto-start (chỉ lần đầu, chỉ Windows)
                autostart = False
                if platform.system() == "Windows":
                    print("\n⚙️  Bạn có muốn agent tự chạy khi bật Windows?")
                    choice = input("   (y/n, mặc định n): ").strip().lower()
                    if choice in ("y", "yes"):
                        autostart = setup_autostart()
                
                save_session(user_id, credentials["auth_token"], username, server_url, autostart)
                break
            else:
                print("\n🔄 Thử lại đăng nhập...")
                retry = input("   Nhấn Enter để thử lại (hoặc gõ 'q' để thoát): ").strip()
                if retry.lower() == 'q':
                    print("👋 Đã thoát agent.")
                    return

    # --- Kết nối WebSocket với Exponential Backoff ---
    uri = f"{server_url}/{user_id}?token={agent_token}"
    backoff = 2  # Bắt đầu 2 giây
    max_backoff = 60
    retry_count = 0

    print(f"\n🚀 Đang kết nối tới server...")
    
    while True:
        try:
            async with websockets.connect(uri, max_size=20_000_000) as websocket:
                # Kết nối thành công → reset backoff
                backoff = 2
                retry_count = 0
                print("✅ Đã kết nối thành công! Agent đang lắng nghe lệnh từ Web...")
                
                while True:
                    # Kiểm tra Emergency Stop
                    if EMERGENCY_STOP:
                        print("⏸️ Đang dừng khẩn cấp. Nhấn Ctrl+Alt+R để tiếp tục.")
                        await asyncio.sleep(1)
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

        except websockets.exceptions.InvalidStatusCode as e:
            if hasattr(e, 'status_code') and e.status_code == 4001:
                # Token không hợp lệ hoặc hết hạn → xóa session, đăng nhập lại
                print("\n🔒 Token không hợp lệ hoặc đã hết hạn!")
                delete_session()
                print("   Cần đăng nhập lại.")
                while True:
                    credentials = login_via_api(server_url)
                    if credentials:
                        user_id = credentials["user_id"]
                        save_session(user_id, credentials["auth_token"], credentials["username"], server_url)
                        uri = f"{server_url}/{user_id}?token={agent_token}"
                        print("🔄 Đang kết nối lại...")
                        break
                    else:
                        retry = input("   Nhấn Enter để thử lại (hoặc 'q' để thoát): ").strip()
                        if retry.lower() == 'q':
                            return
            else:
                retry_count += 1
                print(f"❌ Lỗi kết nối (lần {retry_count}). Thử lại sau {backoff}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

        except websockets.exceptions.ConnectionClosedError:
            retry_count += 1
            print(f"❌ Mất kết nối WebSocket (lần {retry_count}). Thử lại sau {backoff}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)

        except ConnectionRefusedError:
            retry_count += 1
            print(f"❌ Server từ chối kết nối (lần {retry_count}). Thử lại sau {backoff}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)

        except Exception as e:
            retry_count += 1
            print(f"❌ Lỗi: {e} (lần {retry_count}). Thử lại sau {backoff}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)

if __name__ == "__main__":
    pyautogui.FAILSAFE = True
    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        print("\n👋 Đã đóng Agent.")
