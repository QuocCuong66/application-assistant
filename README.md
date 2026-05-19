## Quick test

1. Kích hoạt môi trường ảo và cài dependencies:
   ```powershell
   cd "d:\Application assistant"
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```
2. Tạo `.env` và kiểm tra MongoDB:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   MONGO_URI="mongodb+srv://CuongProAI:rg5OlWyKYT1ovC4t@cluster0.bihl7tb.mongodb.net"
   MONGO_DB_NAME="CuongProAI"
   ```
3. Kiểm tra kết nối MongoDB:
   ```powershell
   python mongo_example.py
   ```
4. Chạy server web:
   ```powershell
   python main.py
   py desktop_agent.py 
   
   Server URL: Bạn cứ nhấn Enter để dùng mặc định (ws://localhost:8000/automation/ws).
   USER ID: Nhập ID người dùng của bạn (thường là 1 nếu bạn là user đầu tiên, hoặc xem trên giao diện web).
   AGENT_TOKEN: Nhập default-secret-token-123 (đây là token mặc định trong file cấu hình).
   ID: 69ff169fe03ca96247b98195
   ```
5. Mở browser:
   - http://localhost:8000
   - test API MongoDB: http://localhost:8000/mongo/users

Sử dụng thông tin thẻ test của VNPay sau đây để thanh toán:
Ngân hàng: Chọn NCB
   Số thẻ: 9704198526191432198
   Tên chủ thẻ: NGUYEN VAN A
   Ngày phát hành:  07/15
   Mã OTP: 123456

---

1. Cách dùng Cài dependencies: 
   cd "d:\Application assistant"; python -m pip install -r requirements.txt
2. Tạo .env hoặc đặt biến môi trường: 
   MONGO_URI="mongodb+srv://CuongProAI:rg5OlWyKYT1ovC4t@cluster0.bihl7tb.mongodb.net"
   MONGO_DB_NAME="CuongProAI"
3. Trong code nếu cần truy cập MongoDB: 
   from database import mongo_db

4. Ví dụ thao tác MongoDB:
   - `mongo_db["users"]` tương ứng với collection `users`
   - `mongo_db["message_history"]` tương ứng với collection `message_history`
   - `mongo_db["transactions"]` tương ứng với collection `transactions`
   - `mongo_db["usage"]` tương ứng với collection `usage`
   - `mongo_db["trained_tasks"]` tương ứng với collection `trained_tasks`

5. Chạy file ví dụ:
   ```bash
   python mongo_example.py
   ```

# AI Assistant Backend System

A complete production-ready AI Assistant backend built with Python.

## Cấu trúc Dự án
Dự án sử dụng duy nhất một repository cho cả Frontend (static) và Backend (FastAPI). 
- `static/`: Chứa giao diện Frontend (HTML, CSS, JS).
- `api/`, `main.py`, `config.py`: Chứa Backend FastAPI & WebSockets.
- `desktop_agent.py`: Tool chạy **ở máy cục bộ (local)** để điều khiển máy tính.

---

## 1. Hướng dẫn chạy Local (Phát triển / Test)

### Cài đặt môi trường
1. Yêu cầu Python 3.8+ và [FFmpeg](https://ffmpeg.org/download.html).
2. Mở Terminal / PowerShell và tạo môi trường ảo:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. Cài dependencies:
   ```powershell
   python -m pip install -r requirements.txt
   ```

### Cấu hình `.env`
Tạo file `.env` từ `.env.example`:
```env
OPENAI_API_KEY=your_openai_api_key_here
MONGO_URI="mongodb+srv://CuongProAI:..."
MONGO_DB_NAME="CuongProAI"
AGENT_TOKEN="your-super-secret-token-here"
```

### Chạy Server & Web
Chạy Server API:
```powershell
python main.py
```
Mở trình duyệt truy cập: `http://localhost:8000`

---

## 2. Hướng dẫn Deploy Production lên Render (Backend)

Dự án đã được cấu hình sẵn cho **Render.com**. Bạn **KHÔNG** deploy WebSockets lên Vercel. Bạn sẽ đưa toàn bộ repo này lên Render.

1. Đăng nhập [Render.com](https://render.com).
2. Chọn **New > Web Service**, kết nối GitHub và chọn repository này.
3. Trong cài đặt Render Web Service:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Cấu hình Environment Variables (Biến môi trường) trên Render:
   - `OPENAI_API_KEY`: Key của bạn
   - `MONGO_URI`: Chuỗi kết nối MongoDB
   - `AGENT_TOKEN`: Mã bảo mật tự tạo
   - `FRONTEND_URL`: Để trống hoặc điền domain nếu bạn deploy frontend riêng. Mặc định Render sẽ host luôn thư mục `static/` ở thư mục gốc (vì FastAPI phục vụ static files).

*Sau khi deploy xong, bạn sẽ có URL dạng: `https://your-app.onrender.com`.*
*Truy cập trực tiếp URL này để dùng giao diện Web.*

---

## 3. Hướng dẫn chạy Desktop Agent (Local)

Lưu ý: `desktop_agent.py` **không** deploy lên Render. File này CHỈ chạy trên máy tính mà bạn muốn điều khiển.

1. Mở một Terminal mới.
2. Kích hoạt môi trường ảo: `.\.venv\Scripts\Activate.ps1`
3. Chạy lệnh:
   ```powershell
   python desktop_agent.py
   ```
4. Tool sẽ yêu cầu bạn nhập các thông tin sau (nếu không có trong file `.env`):
   - **Server URL**: Nhập địa chỉ WebSocket Backend của bạn trên Render. (Ví dụ: `wss://your-app.onrender.com/automation/ws`). Nếu chạy local, bạn nhấn Enter để dùng mặc định `ws://localhost:8000/automation/ws`.
   - **USER ID**: ID người dùng của bạn. *Cách lấy: Đăng nhập vào trang Web, nhìn xuống góc dưới màn hình sẽ có dòng "ID: 69ff..."*.
   - **AGENT_TOKEN**: Nhập mã token bạn đã cấu hình trong `.env` của Backend.

5. Khi màn hình hiện `✅ Đã kết nối thành công!`, bạn có thể lên giao diện Web và bấm **Start Skill Training** hoặc ra lệnh cho AI điều khiển máy tính.

*Mẹo: Để không phải nhập lại link server mỗi lần chạy Agent, hãy thêm biến sau vào `.env` ở máy tính của bạn:*
`BACKEND_WS_URL="wss://your-app.onrender.com/automation/ws"`


