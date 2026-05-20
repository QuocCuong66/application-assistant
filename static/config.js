const isLocal = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";

window.APP_CONFIG = {
  // Thay đổi thành URL Render thật của bạn trước khi deploy Vercel (Hiện tại đã cấu hình sẵn theo yêu cầu)
  API_URL: isLocal 
    ? "http://localhost:8000" 
    : "https://application-assistant-backend.onrender.com",
  WS_URL: isLocal 
    ? "ws://localhost:8000/automation/ws" 
    : "wss://application-assistant-backend.onrender.com/automation/ws"
};
