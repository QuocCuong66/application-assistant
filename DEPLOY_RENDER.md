# Hướng dẫn Deploy Backend lên Render

Tài liệu này hướng dẫn chi tiết từng bước để đưa Backend FastAPI của ứng dụng **Application Assistant** lên Render.com.

---

## 📋 Yêu cầu chuẩn bị trước khi deploy

1. Tài khoản [Render.com](https://render.com) (Đăng ký miễn phí, khuyên dùng đăng nhập bằng GitHub).
2. Một cơ sở dữ liệu **MongoDB** hoạt động (Ví dụ: MongoDB Atlas trực tuyến).
3. API Key của **OpenAI** (Dùng cho tính năng AI Assistant).

---

## 🚀 Các bước thực hiện Deploy

### Bước 1: Đăng ký Web Service mới trên Render
1. Truy cập vào **Render Dashboard** của bạn và bấm nút **New +** ở góc trên bên phải, chọn **Web Service**.
2. Chọn **Build and deploy from a Git repository**.
3. Chọn Repository chứa mã nguồn này từ tài khoản GitHub của bạn (Bấm *Connect*).

### Bước 2: Cấu hình thông tin dịch vụ
Điền các thông số cơ bản cho Web Service:
* **Name**: `application-assistant-backend` (hoặc tên tùy chọn của bạn).
* **Region**: Chọn khu vực gần bạn nhất (ví dụ: `Singapore` hoặc `Oregon`).
* **Branch**: Chọn nhánh chứa code sạch của bạn (thường là `main` hoặc `master`).
* **Language/Runtime**: `Python`
* **Build Command**: `pip install -r requirements.txt`
* **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

*(Lưu ý: Do dự án đã có sẵn file `render.yaml`, Render có thể tự động nhận diện các cấu hình này nếu bạn chọn deploy qua Blueprints. Nếu deploy thủ công bằng giao diện Web, hãy nhập như trên).*

### Bước 3: Cấu hình Biến môi trường (Environment Variables)
Trong tab **Environment**, bấm **Add Environment Variable** và điền đầy đủ các khóa sau đây để đảm bảo ứng dụng chạy đúng:

| Key | Value (Ví dụ / Mô tả) | Trạng thái bảo mật |
| :--- | :--- | :--- |
| **`PYTHON_VERSION`** | `3.10.13` | Cố định |
| **`MONGO_URI`** | `mongodb+srv://username:password@cluster...` | **Bí mật** (Chuỗi kết nối DB Atlas của bạn) |
| **`MONGO_DB_NAME`** | `CuongProAI` | Cố định tên Database |
| **`OPENAI_API_KEY`** | `sk-proj-xxxx...` | **Bí mật** (Key OpenAI của bạn) |
| **`AGENT_TOKEN`** | `my-super-secret-token-123` | **Bí mật** (Token tự chế để xác thực Desktop Agent) |
| **`FRONTEND_ORIGIN`** | `https://ten-app-cua-ban.vercel.app` | URL trang Vercel của bạn (chặn CORS chéo trang) |
| **`VNPAY_TMN_CODE`** | `8OT39IL8` | Mã merchant VNPay của bạn |
| **`VNPAY_HASH_SECRET`** | `S0XOBFAJQWIIGWG...` | Chuỗi mã hóa bí mật VNPay |
| **`VNPAY_RETURN_URL`** | `https://ten-backend-tren-render.onrender.com/payment/vnpay_return` | Link phản hồi VNPay (điền URL Render sau khi tạo) |

> 💡 **Mẹo nhỏ**: Sau khi Render khởi tạo xong Web Service, nó sẽ cấp cho bạn một domain ở góc trên bên trái màn hình (dạng `https://xyz.onrender.com`). Hãy copy link này để điền vào phần **`VNPAY_RETURN_URL`** của Backend và làm cấu hình cho Frontend Vercel ở bước sau.

### Bước 4: Bắt đầu Deploy
* Bấm nút **Create Web Service** ở cuối trang.
* Render sẽ tiến hành kéo code từ Git về, cài đặt các dependencies thông qua `requirements.txt` và khởi động máy chủ FastAPI.
* Khi log báo `Application startup complete` và nút trạng thái chuyển sang màu xanh **Live** là thành công!

---

## 🔍 Kiểm tra trạng thái hoạt động
Sau khi deploy xong, bạn có thể kiểm tra xem backend chạy đúng chưa bằng cách truy cập vào đường dẫn:
`https://tên-dịch-vụ-của-bạn.onrender.com/health`

If browser displays:
```json
{"status": "ok"}
```
Nghĩa là Backend của bạn đang trực tuyến và hoạt động hoàn toàn ổn định!
