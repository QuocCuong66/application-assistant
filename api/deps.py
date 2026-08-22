from fastapi import HTTPException, Header, Depends
import time
from database import get_db
import datetime
from bson import ObjectId

# Simple in-memory rate limiting
RATE_LIMIT_DURATION = 1.0  # seconds between requests
last_request_time = {}

def check_rate_limit(client_ip: str):
    current_time = time.time()
    if client_ip in last_request_time:
        time_passed = current_time - last_request_time[client_ip]
        if time_passed < RATE_LIMIT_DURATION:
            raise HTTPException(status_code=429, detail="Too Many Requests")
    last_request_time[client_ip] = current_time

def get_current_user(x_token: str = Header(None), db = Depends(get_db)):
    if not x_token:
        raise HTTPException(status_code=401, detail="Authentication token missing. Provide X-Token header.")
    users = db.users
    user = users.find_one({"token": x_token})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    # Convert ObjectId to string for id field if needed by the caller
    # We'll return the user document as is, but note that the 'id' field will be '_id' in MongoDB.
    # However, the schemas expect an 'id' field. We'll adjust in the caller or here.
    # For simplicity, we'll add an 'id' field to the user dict that is the string of '_id'.
    user["id"] = str(user["_id"])
    return user

def check_usage_limit(current_user: dict = Depends(get_current_user), db = Depends(get_db)):
    today_str = datetime.date.today().isoformat()
    usages = db.usage
    # Find usage document for this user
    usage = usages.find_one({"user_id": current_user["id"]})

    if not usage:
        usage_doc = {
            "user_id": current_user["id"],
            "request_count": 0,
            "last_reset_date": today_str
        }
        result = usages.insert_one(usage_doc)
        usage_doc["_id"] = result.inserted_id
        usage = usage_doc

    last_reset = str(usage.get("last_reset_date", ""))
    if last_reset < today_str:
        usages.update_one({"_id": usage["_id"]}, {"$set": {"request_count": 0, "last_reset_date": today_str}})
        usage["request_count"] = 0
        usage["last_reset_date"] = today_str

    if not current_user.get("is_pro", False) and usage.get("request_count", 0) >= 20:
        raise HTTPException(status_code=403, detail="Daily request limit exceeded. Upgrade to pro for unlimited requests.")

    return usage
