import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("WARNING: OPENAI_API_KEY environment variable not set. Please create a .env file.")

VNPAY_TMN_CODE = os.getenv("VNPAY_TMN_CODE")
VNPAY_HASH_SECRET = os.getenv("VNPAY_HASH_SECRET")
VNPAY_URL = os.getenv("VNPAY_URL", "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html")
VNPAY_RETURN_URL = os.getenv("VNPAY_RETURN_URL", "http://localhost:8000/payment/vnpay_return")
