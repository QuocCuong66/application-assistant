import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("WARNING: OPENAI_API_KEY environment variable not set. Please create a .env file.")

OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")

AGENT_TOKEN = os.getenv("AGENT_TOKEN", "default-secret-token-123")

VNPAY_TMN_CODE = os.getenv("VNPAY_TMN_CODE")
VNPAY_HASH_SECRET = os.getenv("VNPAY_HASH_SECRET")
VNPAY_URL = os.getenv("VNPAY_URL", "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html")
VNPAY_RETURN_URL = os.getenv("VNPAY_RETURN_URL", "http://localhost:8000/payment/vnpay_return")

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "https://application-assistant.vercel.app")

BACKEND_WS_URL = os.getenv("BACKEND_WS_URL", "ws://localhost:8000/automation/ws")
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "CuongProAI")
