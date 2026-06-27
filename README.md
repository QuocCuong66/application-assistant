# 🚀 AI Assistant & Desktop Automation System

Hệ thống Trợ lý AI và Tự động hóa máy tính toàn diện, được thiết kế theo kiến trúc **3 lớp tách biệt** nhằm tối ưu hóa hiệu năng, bảo mật và khả năng mở rộng:

1. **Frontend (Vercel)**: Giao diện người dùng Web tĩnh (HTML/CSS/JS) chạy trên mạng lưới CDN tốc độ cao của Vercel.
2. **Backend (Render)**: Máy chủ API FastAPI + WebSockets chạy trên Render để xử lý logic AI Brain, kết nối MongoDB và quản lý luồng điều khiển.
3. **Desktop Agent (Local Máy tính)**: Chương trình Python chạy ngầm trên máy của bạn để thực thi các lệnh điều khiển hệ thống (chuột, bàn phím, ứng dụng) từ Web gửi về.

---

## 💻 1. Chạy Thử Nghiệm ở Môi Trường Local (Development)

Để chạy thử nghiệm toàn bộ hệ thống dưới máy tính của bạn trước khi đưa lên đám mây:

### ⚙️ Bước chuẩn bị chung
* Yêu cầu máy tính cài đặt sẵn **Python 3.8+** và công cụ hỗ trợ xử lý giọng nói **FFmpeg** (nếu dùng tính năng voice).
* Tạo và kích hoạt môi trường ảo:
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  python -m pip install -r requirements.txt
  ```
* Sao chép file `.env.example` thành `.env` ở thư mục gốc và điền các khóa cần thiết:
  ```env
  OPENAI_API_KEY="key-openai-cua-ban"
  MONGO_URI="mongodb-atlas-uri-cua-ban"
  MONGO_DB_NAME="CuongProAI"
  AGENT_TOKEN="default-secret-token-123"
  ```

---

### 🔌 Bước 1: Khởi chạy Backend API Local
Mở terminal và chạy lệnh:
```powershell
python main.py
```
* Backend sẽ chạy tại: `http://127.0.0.1:8000`
* Bạn có thể kiểm tra trạng thái tại: `http://127.0.0.1:8000/health`

---

### 🌐 Bước 2: Khởi chạy Frontend Local
Bạn có hai cách để chạy giao diện web ở local:
* **Cách 1 (Khuyên dùng)**: Sử dụng extension **Live Server** trên VS Code để mở file `static/index.html`. Trang web sẽ chạy tại địa chỉ `http://127.0.0.1:5500`.
* **Cách 2**: Truy cập trực tiếp đường dẫn của server local `http://127.0.0.1:8000` trên trình duyệt. Backend sẽ tự động phát hiện thư mục `static/` ở local để serve trực tiếp giao diện cho bạn.

*(Lưu ý: File [static/config.js](file:///d:/application-assistant/static/config.js) đã được thiết lập tự động nhận diện nếu chạy trên `localhost` / `127.0.0.1` để kết nối thẳng tới server local cổng `8000`).*

---

### 🤖 Bước 3: Khởi chạy Desktop Agent Local
1. Mở một cửa sổ terminal mới và kích hoạt môi trường ảo: `.\.venv\Scripts\Activate.ps1`
2. Chạy lệnh:
   ```powershell
   python desktop_agent.py
   ```
3. Do chạy local lần đầu, Agent sẽ yêu cầu bạn đăng nhập. Sử dụng chính tài khoản và mật khẩu bạn đã đăng ký trên giao diện Web.
4. Sau khi đăng nhập thành công, Agent tự động lưu session vào file `agent_session.json` (được bảo mật không push Git) và kết nối tới cổng WebSocket local.

---
---

## ☁️ 2. Hướng Dẫn Triển Khai Lên Production (Deploy Cloud)

Để đưa hệ thống lên chạy thực tế trực tuyến 24/7, chúng ta tách biệt Frontend lên Vercel và Backend lên Render.

### 🟥 Phần A: Triển khai Backend FastAPI lên Render.com
Máy chủ Render sẽ chỉ chạy code Backend Python và kết nối Database.

1. Đăng nhập vào [Render.com](https://render.com).
2. Chọn **New > Blueprints** (Khuyên dùng vì dự án đã có sẵn file [render.yaml](file:///d:/application-assistant/render.yaml)).
3. Kết nối tài khoản GitHub của bạn và chọn repository của dự án.
4. Render sẽ tự động quét file `render.yaml` và liệt kê các biến môi trường cần thiết. Bạn chỉ cần điền giá trị cho các biến bảo mật:
   - `MONGO_URI`: Chuỗi kết nối MongoDB Atlas của bạn.
   - `OPENAI_API_KEY`: API Key của OpenAI.
   - `AGENT_TOKEN`: Token tự chọn để bảo mật kết nối Desktop Agent (Ví dụ: `token-bi-mat-cua-toi-123`).
5. Bấm **Apply**. Quá trình deploy sẽ tự động diễn ra.
6. Sau khi hoàn thành, bạn sẽ nhận được một đường dẫn Backend dạng: `https://ten-backend-cua-ban.onrender.com`.

---

### 📐 Phần B: Triển khai Frontend Tĩnh lên Vercel.com
Giao diện tĩnh HTML/CSS/JS sẽ được phân phối trên hạ tầng CDN siêu tốc của Vercel.

1. **Cấu hình API trước khi deploy**:
   Mở file [static/config.js](file:///d:/application-assistant/static/config.js) trên máy của bạn và cập nhật đường dẫn Backend Render bạn vừa nhận được ở Phần A vào phần cấu hình:
   ```javascript
   window.APP_CONFIG = {
     API_URL: "https://ten-backend-cua-ban.onrender.com",
     WS_URL: "wss://ten-backend-cua-ban.onrender.com/automation/ws"
   };
   ```
   Lưu file, thực hiện `git commit` và `git push` lên GitHub.
2. Đăng nhập [Vercel.com](https://vercel.com).
3. Chọn **Add New > Project**, chọn repository của bạn và bấm **Import**.
4. **Cấu hình quan trọng tại Vercel**:
   - **Framework Preset**: Chọn **`Other`**.
   - **Root Directory**: **Giữ nguyên thư mục gốc của project** (Không đổi thành thư mục `static`). File [vercel.json](file:///d:/application-assistant/vercel.json) ở thư mục gốc sẽ tự động cấu hình và định tuyến thư mục `static` làm root đích.
5. Bấm **Deploy**. Sau khi hoàn tất, Vercel sẽ cấp cho bạn một đường dẫn dạng: `https://ten-frontend-cua-ban.vercel.app`.

---

### 🔗 Phần C: Liên kết CORS (Bước bắt buộc)
Để bảo mật và cho phép Frontend Vercel gửi request đến Backend Render mà không bị chặn chéo trang (CORS):

1. Quay lại **Render Dashboard** của bạn, mở Web Service của Backend.
2. Vào mục **Environment Variables**.
3. Cập nhật biến môi trường **`FRONTEND_ORIGIN`** thành URL Vercel của bạn (Ví dụ: `https://ten-frontend-cua-ban.vercel.app`).
4. Cập nhật biến **`VNPAY_RETURN_URL`** thành: `https://ten-backend-cua-ban.onrender.com/payment/vnpay_return`
5. Lưu cấu hình. Render sẽ tự động chạy lại máy chủ để áp dụng bảo mật mới.

---
---

## 🖥️ 3. Chạy Desktop Agent Kết Nối Server Đám Mây

Khi hệ thống đã chạy trên Cloud, bạn có thể thiết lập Desktop Agent trên bất cứ máy tính nào bạn muốn điều khiển từ xa:

1. Đảm bảo file cấu hình `.env` của Desktop Agent có đường dẫn WS trỏ tới Render:
   ```env
   BACKEND_WS_URL="wss://ten-backend-cua-ban.onrender.com/automation/ws"
   AGENT_TOKEN="token-bi-mat-cua-toi-123" # Trùng khớp với token trên Render
   ```
2. Chạy lệnh khởi động:
   ```powershell
   python desktop_agent.py
   ```
3. Đăng nhập tài khoản Web của bạn. Agent sẽ tự lưu session vào file local và tự động duy trì kết nối. Bạn có thể đóng CMD lại nếu bạn đã đồng ý tích hợp tự chạy cùng Windows (Auto-start) ở lần khởi chạy đầu tiên.

---

## 📂 Các File Cấu Hình Hệ Thống Tham Chiếu
* **Cấu hình Vercel**: [vercel.json](file:///d:/application-assistant/vercel.json) (Quản lý thư mục chạy, rewrite đường dẫn tĩnh và cache).
* **Cấu hình Render**: [render.yaml](file:///d:/application-assistant/render.yaml) (Quản lý cấu hình xây dựng máy chủ tự động).
* **Hướng dẫn cụ thể Render**: [DEPLOY_RENDER.md](file:///d:/application-assistant/DEPLOY_RENDER.md).
* **Hướng dẫn cụ thể Vercel**: [DEPLOY_VERCEL.md](file:///d:/application-assistant/DEPLOY_VERCEL.md).