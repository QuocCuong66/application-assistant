import logging
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
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
frontend_origin = config.FRONTEND_ORIGIN.rstrip("/") if config.FRONTEND_ORIGIN else ""

origins = [
    frontend_origin,
    "https://application-assistant.vercel.app",
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:5500",
    "http://localhost:5500",
]

origins = [origin for origin in dict.fromkeys(origins) if origin]

# Regex hỗ trợ Localhost, 127.0.0.1 và TẤT CẢ domain/preview Vercel (*.vercel.app)
origin_regex = r"^(https?://(localhost|127\.0\.0\.1)(:\d+)?|https://.*\.vercel\.app)$"

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ------------------------------

# Include API routes
app.include_router(auth_router)
app.include_router(payment_router)
app.include_router(automation_router)
app.include_router(router)

# --- STATIC FILES (chỉ cho local dev, Render không cần serve frontend) ---
if os.path.isdir("static"):
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
