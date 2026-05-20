import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware  # Thêm dòng này
import uvicorn
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
    "https://application-assistant.vercel.app", # Domain frontend của bạn
    "http://localhost",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,            # Cho phép các nguồn này truy cập
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

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

if __name__ == "__main__":
    logging.info("Starting AI Assistant Backend Server...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)