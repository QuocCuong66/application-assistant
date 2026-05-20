import sys
import subprocess
import os

# --- TỰ ĐỘNG CÀI ĐẶT THƯ VIỆN ---
def install_dependencies():
    required = ["websockets", "pyautogui"]
    for lib in required:
        try:
            __import__(lib)
        except ImportError:
            print(f"📦 Đang cài đặt thư viện {lib}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", lib])

# Chạy cài đặt trước khi import các thư viện đó
install_dependencies()

import asyncio
import websockets
import json
import pyautogui
import platform
import time

# --- CẤU HÌNH ---
# Thay URL này bằng link Vercel của bạn (ví dụ: wss://your-app.vercel.app/automation/ws/)
DEFAULT_SERVER = "ws://localhost:8000/automation/ws" 

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

                    if data["type"] == "direct":
                        action = data["action"]
                        if action == "chrome":
                            if platform.system() == "Windows":
                                os.startfile("chrome.exe")
                            elif platform.system() == "Darwin": # macOS
                                subprocess.Popen(["open", "-a", "Google Chrome"])
                        elif action == "notepad":
                            if platform.system() == "Windows":
                                subprocess.Popen(["notepad.exe"])

                    elif data["type"] == "execution":
                        actions = data["actions"]
                        print(f"🚀 Đang thực thi Skill: {data['task_name']} ({len(actions)} bước)")
                        
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
            print(f"❌ Mất kết nối: {e}. Đang thử lại sau 5 giây...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    # Đảm bảo an toàn khi chạy pyautogui
    pyautogui.FAILSAFE = True
    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        print("\n👋 Đã đóng Agent.")
