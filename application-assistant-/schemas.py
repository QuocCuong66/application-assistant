from pydantic import BaseModel, Field
from typing import Optional
import datetime
from bson import ObjectId

class AuthRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    token: str
    is_pro: bool

class UserResponse(BaseModel):
    id: str
    username: str
    is_pro: bool

    class Config:
        validate_by_name = True
        populate_by_name = True
        json_encoders = {
            ObjectId: str
        }

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    action_result: Optional[str] = None

class HistoryItem(BaseModel):
    message: str
    response: str
    timestamp: datetime.datetime

    class Config:
        validate_by_name = True
        populate_by_name = True
        json_encoders = {
            ObjectId: str
        }

class PaymentCreateRequest(BaseModel):
    amount: int

class PaymentUrlResponse(BaseModel):
    url: str

class TrainedTaskCreate(BaseModel):
    name: str

class TrainedTaskUpdate(BaseModel):
    name: Optional[str] = None
    note: Optional[str] = None

class TrainedTaskResponse(BaseModel):
    id: str
    name: str
    note: Optional[str] = None
    created_at: datetime.datetime

    class Config:
        validate_by_name = True
        populate_by_name = True
        json_encoders = {
            ObjectId: str
        }
