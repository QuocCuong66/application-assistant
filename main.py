import logging
import json
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import config
from api.routes import router
from api.auth import router as auth_router
from api.payment import router as payment_router
from api.automation import router as automation_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)

app = FastAPI(
    title="AI Assistant Backend",
    description="Backend system for an AI Assistant using FastAPI, OpenAI, and Whisper",
    version="1.0.0"
)

# --- CẤU HÌNH CORS TẠI ĐÂY ---
origins = [
    config.FRONTEND_ORIGIN,
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:5500",   # <-- THÊM DÒNG NÀY (Địa chỉ IP của Live Server)
    "http://localhost:5500",   # <-- THÊM DÒNG NÀY (Địa chỉ localhost của Live Server)
]

origins = [origin for origin in dict.fromkeys(origins) if origin]
local_origin_regex = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,            # Cho phép các nguồn này truy cập
    allow_origin_regex=local_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],               # Cho phép tất cả các phương thức (GET, POST, OPTIONS...)
    allow_headers=["*"],               # Cho phép tất cả các headers
)
# ------------------------------

# Include API routes
app.include_router(auth_router)
app.include_router(payment_router)
app.include_router(automation_router)
app.include_router(router)

@app.get("/static/config.js")
def frontend_config():
    api_url = config.PUBLIC_API_URL or ""
    ws_url = config.PUBLIC_WS_URL or ""
    payload = (
        "const isLocal = window.location.hostname === \"localhost\" || "
        "window.location.hostname === \"127.0.0.1\";\n\n"
        "window.APP_CONFIG = {\n"
        f"  API_URL: {json.dumps(api_url)} || window.location.origin,\n"
        f"  WS_URL: {json.dumps(ws_url)} || "
        "`${window.location.protocol === \"https:\" ? \"wss\" : \"ws\"}://${window.location.host}/automation/ws`\n"
        "};\n"
    )
    return Response(content=payload, media_type="application/javascript")

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

@app.get("/health")
def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    logging.info("Starting AI Assistant Backend Server...")
    logging.info(f"Allowed CORS Origins: {origins}")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
