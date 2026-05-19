import logging
import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "").strip('"')
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "CuongProAI").strip('"')

mongo_client = None
mongo_db = None

if MONGO_URI:
    try:
        # Tối ưu kết nối cho Vercel/Serverless
        client_kwargs = {
            "serverSelectionTimeoutMS": 5000,
            "tls": True,
            "tlsAllowInvalidCertificates": False # Luôn ưu tiên bảo mật
        }

        # Nếu gặp lỗi SSL trên Vercel, đôi khi cần dùng certifi
        try:
            import certifi
            client_kwargs["tlsCAFile"] = certifi.where()
        except ImportError:
            pass

        mongo_client = MongoClient(MONGO_URI, **client_kwargs)
        mongo_client.admin.command("ping")
        mongo_db = mongo_client[MONGO_DB_NAME]
        logging.info(f"Connected to MongoDB database '{MONGO_DB_NAME}'")
    except Exception as e:
        logging.error(f"Could not connect to MongoDB: {e}")
        # Thử lại với tùy chọn linh hoạt hơn nếu lỗi handshake (chỉ dùng khi thực sự cần thiết)
        if "SSL handshake failed" in str(e) or "internal error" in str(e):
            try:
                logging.info("Retrying MongoDB connection with flexible TLS options...")
                mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000, tls=True, tlsInsecure=True)
                mongo_client.admin.command("ping")
                mongo_db = mongo_client[MONGO_DB_NAME]
                logging.info(f"Connected to MongoDB (Insecure Mode)")
            except Exception as e2:
                logging.error(f"MongoDB retry failed: {e2}")
                mongo_client = None
                mongo_db = None
        else:
            mongo_client = None
            mongo_db = None
else:
    logging.info("MONGO_URI not set; skipping MongoDB connection.")

# Dependency
def get_db():
    if mongo_db is None:
        raise RuntimeError("Database not connected")
    return mongo_db
