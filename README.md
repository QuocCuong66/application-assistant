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

## Prerequisites
- Python 3.8+
- [FFmpeg](https://ffmpeg.org/download.html) (Required by Whisper for audio processing)
- Microphone (for voice features)

## Installation

### 1. Kiểm tra Python
Project yêu cầu Python 3.8 hoặc mới hơn.

Trên Windows PowerShell:
```powershell
python --version
```

Trên macOS / Linux:
```bash
python3 --version
```

Nếu bạn chưa cài, tải Python từ https://www.python.org/downloads/ và chọn "Add Python to PATH" trên Windows.

### 2. Tạo môi trường ảo
Sử dụng virtual environment để tách project khỏi hệ thống chung.

Trên Windows PowerShell:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Trên Windows CMD:
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

Trên macOS / Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Cài dependencies
Sau khi kích hoạt môi trường ảo:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Tạo file `.env`
Tạo file `.env` ở thư mục gốc project và thêm biến môi trường:
```env
OPENAI_API_KEY=your_openai_api_key_here
MONGO_URI="mongodb+srv://CuongProAI:rg5OlWyKYT1ovC4t@cluster0.bihl7tb.mongodb.net"
MONGO_DB_NAME="tên_database_của_bạn"
```

### 5. Khởi động server
```bash
python main.py
```

Sau khi khởi động, truy cập `http://localhost:8000`.

## Running the Server

Start the FastAPI server:
```bash
python main.py
```
The server will run on `http://localhost:8000`.

## API Usage

Endpoint: `POST /chat`

**Request:**
```json
{
  "message": "Hello, how are you?"
}
```

**Response:**
```json
{
  "response": "I'm doing well, thank you! How can I help you today?",
  "action_result": null
}
```
If you send "open chrome", `action_result` will show the execution status.

## MongoDB API Endpoints

Các route MongoDB dùng cùng token của user:

- `GET /mongo/{collection_name}`
  - list dữ liệu từ collection MongoDB
  - collection_name có thể là `users`, `usage`, `message_history`, `transactions`, `trained_tasks`

- `POST /mongo/{collection_name}`
  - insert document vào collection tương ứng
  - body JSON là document cần lưu

- `POST /mongo/refresh`
  - no-op endpoint; MongoDB is the primary storage and data should be stored directly there

### Ví dụ curl

Đọc dữ liệu users:
```bash
curl -H "X-Token: <your_user_token>" http://localhost:8000/mongo/users
```

Thêm document mới vào `message_history`:
```bash
curl -X POST -H "Content-Type: application/json" -H "X-Token: <your_user_token>" \
  -d '{"user_id": 1, "message": "Xin chào", "response": "Chào bạn", "timestamp": "2026-05-06T00:00:00"}' \
  http://localhost:8000/mongo/message_history
```

Refresh endpoint (no-op because MongoDB is primary storage):
```bash
curl -X POST -H "X-Token: <your_user_token>" http://localhost:8000/mongo/refresh
```

