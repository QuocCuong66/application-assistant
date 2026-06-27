# Hướng dẫn Deploy Frontend lên Vercel

Tài liệu này hướng dẫn chi tiết từng bước để triển khai phần giao diện Frontend (HTML/CSS/JS tĩnh) của ứng dụng **Application Assistant** lên Vercel.

---

## 📋 Yêu cầu chuẩn bị trước khi deploy

1. Tài khoản [Vercel](https://vercel.com) (Có thể đăng ký miễn phí bằng tài khoản GitHub).
2. Đã hoàn thành triển khai Backend lên Render và lấy được **Backend URL** (ví dụ: `https://ten-app-backend.onrender.com`).

---

## 🚀 Các bước thực hiện Deploy

### Bước 1: Cấu hình liên kết API trong mã nguồn
Trước khi đẩy code lên Git để Vercel deploy, bạn cần sửa lại địa chỉ IP/Domain của Backend trong dự án để Frontend biết chỗ gửi dữ liệu:

1. Mở file [static/config.js](file:///d:/application-assistant/static/config.js) trong dự án.
2. Tìm và chỉnh sửa giá trị phần `production` (phía sau dấu hai chấm `:`):
   ```javascript
   const isLocal = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";

   window.APP_CONFIG = {
     API_URL: isLocal 
       ? "http://localhost:8000" 
       : "https://ten-backend-cua-ban.onrender.com", // Đổi thành URL Render thật của bạn
     WS_URL: isLocal 
       ? "ws://localhost:8000/automation/ws" 
       : "wss://ten-backend-cua-ban.onrender.com/automation/ws" // Đổi thành URL WebSocket Render thật của bạn
   };
   ```
3. Lưu file và thực hiện `git push` để cập nhật code mới lên GitHub.

### Bước 2: Import Project trên Vercel
1. Đăng nhập vào **Vercel Dashboard**.
2. Bấm nút **Add New...** ở góc phải và chọn **Project**.
3. Vercel sẽ liệt kê các Repository trong tài khoản GitHub của bạn. Tìm repository của dự án và chọn **Import**.

### Bước 3: Cấu hình Vercel trước khi Deploy
Tại trang cấu hình dự án, hãy thiết lập chuẩn xác các thông số sau:

* **Project Name**: `application-assistant-frontend` (Tự động điền hoặc đổi tùy chọn).
* **Framework Preset**: Chọn **`Other`** (Do chúng ta chạy web tĩnh HTML/CSS/JS thuần, không sử dụng framework React/Next/Vue nào).
* **Root Directory**: **Giữ nguyên thư mục gốc** (Không thay đổi thành `static`). File [vercel.json](file:///d:/application-assistant/vercel.json) ở thư mục gốc của dự án đã tự động cấu hình Vercel chỉ phục vụ các file bên trong thư mục `static/` ra ngoài Internet.
* **Build and Output Settings**: Giữ nguyên mặc định (Không điền lệnh build).

### Bước 4: Tiến hành Deploy
* Bấm nút **Deploy**.
* Vercel sẽ tự động tải dự án từ GitHub và bắt đầu biên dịch file tĩnh trong vài giây.
* Khi màn hình hiện thông báo **Congratulations!** cùng ảnh xem trước trang web là dự án của bạn đã hoạt động trực tuyến.
* Vercel sẽ cấp cho bạn một domain mặc định dạng `https://ten-app-frontend.vercel.app`.

---

## 🔗 Liên kết hai môi trường (Quan trọng)
Khi Vercel đã deploy thành công, bạn cần quay lại **Render Dashboard** và cập nhật domain Vercel vừa nhận được vào biến môi trường:

1. Vào Render Web Service (Backend).
2. Vào **Settings** -> **Environment Variables**.
3. Cập nhật biến **`FRONTEND_ORIGIN`** thành URL Vercel của bạn (ví dụ: `https://ten-app-frontend.vercel.app`).
4. Lưu cấu hình. Render sẽ tự động build lại để áp dụng CORS mới, cho phép Frontend Vercel gửi request đến Backend Render an toàn không bị chặn.
