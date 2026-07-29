from fastapi import APIRouter, HTTPException, Depends
import bcrypt
import uuid
from bson import ObjectId
from datetime import datetime, timezone

from database import get_db
from schemas import AuthRequest, TokenResponse, UserResponse
from api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

@router.get("/me", response_model=UserResponse)
def get_me(current_user: dict = Depends(get_current_user)):
    # current_user is a dict from get_current_user (we'll adjust deps later if needed)
    # For now, we assume it's a dict with user data
    return current_user

@router.post("/register")
def register(request: AuthRequest, db: dict = Depends(get_db)):
    # db is the MongoDB database object
    users = db.users
    # Check if user exists
    existing_user = users.find_one({"username": request.username})
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    # Hash password
    hashed_password = bcrypt.hashpw(request.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    # Create user document
    user_doc = {
        "username": request.username,
        "password": hashed_password,
        "token": None,
        "is_pro": False,
        "created_at": datetime.now(timezone.utc)
    }
    result = users.insert_one(user_doc)
    # We don't need to return the user object, just a success message
    return {"message": "User registered successfully"}

@router.post("/login", response_model=TokenResponse)
def login(request: AuthRequest, db: dict = Depends(get_db)):
    users = db.users
    # Find user
    user = users.find_one({"username": request.username})
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    # Verify password
    if not bcrypt.checkpw(request.password.encode('utf-8'), user["password"].encode('utf-8')):
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    # Generate simple token (in a real app, this should be a JWT)
    token = str(uuid.uuid4())

    # Save token to db
    users.update_one({"_id": user["_id"]}, {"$set": {"token": token}})

    # Prepare response
    # Convert ObjectId to string for the id field
    user_id = str(user["_id"])
    return TokenResponse(token=token, is_pro=user["is_pro"])
