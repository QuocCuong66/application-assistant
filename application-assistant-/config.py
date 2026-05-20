import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = "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"
if not OPENAI_API_KEY:
    print("WARNING: OPENAI_API_KEY environment variable not set. Please create a .env file.")

VNPAY_TMN_CODE = os.getenv("VNPAY_TMN_CODE", "8OT39IL8")
VNPAY_HASH_SECRET = os.getenv("VNPAY_HASH_SECRET", "S0XOBFAJQWIIGWG0NTI13A7MX4B44CQR")
VNPAY_URL = os.getenv("VNPAY_URL", "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html")
VNPAY_RETURN_URL = os.getenv("VNPAY_RETURN_URL", "http://localhost:8000/payment/vnpay_return")
