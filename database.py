import logging
import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Ensure .env is loaded from project root
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(env_path)
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "").strip('"')
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "CuongProAI").strip('"')

mongo_client = None
mongo_db = None

def init_db():
    global mongo_client, mongo_db
    uri = os.getenv("MONGO_URI", "").strip('"') or MONGO_URI
    db_name = os.getenv("MONGO_DB_NAME", "CuongProAI").strip('"') or MONGO_DB_NAME

    if not uri:
        logging.warning("MONGO_URI not configured; skipping MongoDB connection.")
        return None

    client_kwargs = {
        "serverSelectionTimeoutMS": 10000,
        "tls": True,
    }

    try:
        import certifi
        client_kwargs["tlsCAFile"] = certifi.where()
    except Exception:
        pass

    # Try standard secure connection
    try:
        client = MongoClient(uri, **client_kwargs)
        client.admin.command("ping")
        mongo_client = client
        mongo_db = client[db_name]
        logging.info(f"Connected to MongoDB database '{db_name}'")
        return mongo_db
    except Exception as e:
        logging.warning(f"Initial MongoDB connection attempt error: {e}. Retrying with flexible TLS...")
        try:
            client = MongoClient(uri, serverSelectionTimeoutMS=10000, tls=True, tlsAllowInvalidCertificates=True)
            client.admin.command("ping")
            mongo_client = client
            mongo_db = client[db_name]
            logging.info(f"Connected to MongoDB database '{db_name}' (Flexible TLS Mode)")
            return mongo_db
        except Exception as e2:
            logging.error(f"MongoDB retry connection failed: {e2}")
            mongo_client = None
            mongo_db = None
            return None

# Attempt connection on module load
init_db()

# Dependency with automatic reconnect
def get_db():
    global mongo_db
    if mongo_db is None:
        init_db()
    if mongo_db is None:
        raise RuntimeError("Database not connected. Please check internet connection and MONGO_URI.")
    return mongo_db
