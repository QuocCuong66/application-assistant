# AI Assistant System

A complete production-ready AI Assistant system separated into 3 independent layers for maximum scalability and security:
1. **Frontend**: Static Web UI (HTML/CSS/JS) deployable to Vercel.
2. **Backend**: FastAPI + WebSockets for AI logic and Database management deployable to Render.
3. **Desktop Agent**: Local Python script running on the user's computer to execute automation tasks.

---

## 1. Cấu hình & Chạy Local (Môi trường Phát triển)

### Cài đặt môi trường
1. Yêu cầu Python 3.8+ và [FFmpeg](https://ffmpeg.org/download.html).
2. Tạo môi trường ảo và cài dependencies:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

### Cấu hình
Tạo file `.env` từ `.env.example` và điền các thông số:
- `OPENAI_API_KEY`: Key của bạn
- `MONGO_URI`: Chuỗi kết nối MongoDB

### Chạy Server & Web
1. Khởi động Backend API:
   ```powershell
   python main.py
   ```
2. Mở trình duyệt truy cập: `http://localhost:8000` (FastAPI mặc định sẽ phục vụ tĩnh thư mục `static` ở root).

---

## A. Hướng dẫn Deploy Backend lên Render

Backend FastAPI sẽ chạy độc lập và xử lý WebSockets. Không deploy chung Frontend lên đây (trừ khi test).

1. Đăng nhập [Render.com](https://render.com).
2. Chọn **New > Web Service**, kết nối GitHub và chọn repository này.
3. Cấu hình Render Web Service:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Cấu hình **Environment Variables** trên Render:
   - `OPENAI_API_KEY`: Key OpenAI của bạn
   - `MONGO_URI`: Chuỗi kết nối MongoDB
   - `AGENT_TOKEN`: Chuỗi bí mật tự tạo (Ví dụ: `my-super-secret-token`)
   - `FRONTEND_ORIGIN`: URL Vercel của bạn (Ví dụ: `https://my-frontend.vercel.app`) - Dùng để chặn CORS.
   - `VNPAY_RETURN_URL`: URL Backend của bạn (Ví dụ: `https://my-backend.onrender.com/payment/vnpay_return`)

*Sau khi deploy xong, bạn sẽ có URL dạng: `https://my-backend.onrender.com`.*

---

## B. Hướng dẫn Deploy Frontend lên Vercel

Giao diện Web sẽ được tách riêng ra và host trên Vercel.

1. Đăng nhập [Vercel.com](https://vercel.com).
2. Chọn **Add New Project**, kết nối GitHub và import repository này.
3. Trong phần cấu hình Project Vercel:
   - **Root Directory**: GIỮ NGUYÊN (Không đổi thành static). File `vercel.json` ở thư mục gốc sẽ tự động lo việc routing `static/` thành trang chính.
   - Bấm **Deploy**.
4. Cấu hình API URL cho Production:
   - Sửa nội dung file `static/config.js` trước khi push code lên GitHub (Hoặc sửa trực tiếp trên nhánh main nếu muốn):
   ```javascript
   window.APP_CONFIG = {
     API_URL: "https://my-backend.onrender.com", // Đổi thành URL Render của bạn
     WS_URL: "wss://my-backend.onrender.com/automation/ws"
   };
   ```

*Truy cập trực tiếp URL Vercel của bạn để dùng giao diện Web.*

---

## C. Hướng dẫn chạy Desktop Agent local

Lưu ý: `desktop_agent.py` **không** deploy lên Render hay Vercel. File này CHỈ chạy trên máy tính mà bạn muốn điều khiển.

1. Kích hoạt môi trường ảo: `.\.venv\Scripts\Activate.ps1`
2. Cấu hình file `.env` ở local (cùng thư mục với `desktop_agent.py`):
   ```env
   BACKEND_WS_URL="wss://my-backend.onrender.com/automation/ws"
   AGENT_TOKEN="my-super-secret-token" # Giống hệt token cài trên Render
   ```
3. Chạy lệnh:
   ```powershell
   python desktop_agent.py
   ```
4. Tool sẽ tự đọc link Server. Bạn chỉ cần nhập **USER ID** (Lấy từ giao diện web, góc dưới màn hình "ID: 69ff...").

Khi màn hình hiện `✅ Đã kết nối thành công!`, bạn có thể lên giao diện Web (Vercel) và ra lệnh cho AI điều khiển máy tính.
