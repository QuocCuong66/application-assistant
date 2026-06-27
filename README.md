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

Giao diện Web được tách riêng ra và host trên Vercel dưới dạng trang tĩnh tốc độ cao.

1. Đăng nhập [Vercel.com](https://vercel.app).
2. Chọn **Add New Project**, kết nối GitHub và import repository này.
3. Trong phần cấu hình Project Vercel:
   - **Framework Preset**: Chọn `Other`
   - **Root Directory**: Giữ nguyên thư mục gốc (không chọn `static`). File [vercel.json](file:///d:/application-assistant/vercel.json) đã được cấu hình trỏ `outputDirectory: "static"` để Vercel tự động build và phục vụ trực tiếp các file tĩnh từ thư mục `static/` làm root của trang web.
4. Sửa cấu hình API URL cho môi trường chạy thật trước khi push code (hoặc cập nhật trực tiếp):
   - Chỉnh sửa file [static/config.js](file:///d:/application-assistant/static/config.js):
   ```javascript
   window.APP_CONFIG = {
     API_URL: "https://tên-dịch-vụ-của-bạn.onrender.com", // Đổi thành URL Render của bạn
     WS_URL: "wss://tên-dịch-vụ-của-bạn.onrender.com/automation/ws"
   };
   ```
5. Bấm **Deploy**. Truy cập URL của Vercel để sử dụng ứng dụng.

---

## C. Hướng dẫn chạy Desktop Agent Local (Điều khiển máy tính)

Lưu ý: `desktop_agent.py` **không** deploy lên Render hay Vercel. File này CHỈ chạy trên máy tính mà bạn muốn điều khiển. 

Hiện tại Desktop Agent đã được tích hợp các tính năng tự động hóa mạnh mẽ:
* **Tự động Đăng nhập & Lưu Session**: Không cần lấy hay copy USER ID thủ công nữa. Agent sẽ hiển thị prompt đăng nhập bằng chính tài khoản ứng dụng Web của bạn, sau đó tự lưu session an toàn vào file local `agent_session.json` (được tự động bỏ qua khi push git). Các lần khởi chạy tiếp theo sẽ tự động kết nối ngay lập tức mà không cần tương tác.
* **Tự khởi chạy cùng Windows (Auto-start)**: Trong lần chạy đầu tiên, Agent sẽ hỏi xem bạn có muốn tự khởi động cùng máy tính không. Nếu đồng ý, nó sẽ tự cài đặt shortcut VBS ẩn dưới nền.
* **Exponential Backoff Reconnect**: Tự động thử kết nối lại với thời gian tăng dần (2s -> 4s -> ... -> 60s) nếu server bị ngắt kết nối đột ngột hoặc mạng yếu.

### Cách chạy:
1. Kích hoạt môi trường ảo: `.\.venv\Scripts\Activate.ps1`
2. Cấu hình file `.env` ở local (cùng thư mục với `desktop_agent.py`):
   ```env
   BACKEND_WS_URL="wss://tên-dịch-vụ-của-bạn.onrender.com/automation/ws"
   AGENT_TOKEN="my-super-secret-token" # Trùng khớp với AGENT_TOKEN đã cấu hình trên Render
   ```
3. Chạy lệnh khởi động:
   ```powershell
   python desktop_agent.py
   ```
4. Đăng nhập bằng tài khoản và mật khẩu của bạn (đã đăng ký trên giao diện Web).
5. Khi màn hình hiện `✅ Đã kết nối thành công!`, thiết bị của bạn đã sẵn sàng nhận lệnh từ Web.

---

## D. Thông tin URL tham chiếu
- **Backend URL Mặc định**: `https://application-assistant-backend.onrender.com`
- **Server Local (Development)**: `http://127.0.0.1:8000`