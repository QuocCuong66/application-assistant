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
    "https://application-assistant-git-main-quoccuong66.vercel.app",
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:5500",
    "http://localhost:5500",
]

origins = [origin for origin in dict.fromkeys(origins) if origin]

# Cho phép TẤT CẢ mọi origin (cho phép test/dev thoải mái mà không bị chặn CORS)
# regex r".*" sẽ tự động khớp mọi tên miền và trả về Access-Control-Allow-Origin tương ứng
origin_regex = r".*"

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=origin_regex, # Cho phép tất cả các origin truy cập (bao gồm cả credentials)
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

@app.get("/favicon.ico", include_in_schema=False)
def favicon_ico():
    for p in ["favicon.ico", "static/favicon.ico", "favicon.png", "static/favicon.png"]:
        if os.path.exists(p):
            media = "image/x-icon" if p.endswith(".ico") else "image/png"
            return FileResponse(p, media_type=media)
    return None

@app.get("/favicon.png", include_in_schema=False)
def favicon_png():
    for p in ["favicon.png", "static/favicon.png", "favicon.ico"]:
        if os.path.exists(p):
            media = "image/png" if p.endswith(".png") else "image/x-icon"
            return FileResponse(p, media_type=media)
    return None

@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    logging.error(f"Unhandled exception on {request.url}: {exc}", exc_info=True)
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal Server Error: {str(exc)}"}
    )

@app.get("/health")
def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    logging.info("Starting AI Assistant Backend Server...")
    logging.info(f"Allowed CORS Origins: {origins}")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
