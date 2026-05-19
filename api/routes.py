from fastapi import APIRouter, HTTPException, Request, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from database import get_db
import datetime
from typing import List, Dict, Any
from agent.brain import Brain
from agent.planner import Planner
import logging
import json
import tempfile
import os
from bson import ObjectId
from schemas import ChatRequest, ChatResponse, HistoryItem
from api.deps import check_rate_limit, get_current_user, check_usage_limit

from api.automation import manager as ws_manager
from services.agent_loop import run_agent_loop

router = APIRouter()
brain = Brain()
planner = Planner()

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    fastapi_req: Request,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    usage: dict = Depends(check_usage_limit)
):
    client_ip = fastapi_req.client.host
    check_rate_limit(client_ip)

    user_message = request.message
    logging.info(f"User Input from {current_user.get('username', 'unknown')}: {user_message}")

    # 1. Kiểm tra lệnh/skill đã học
    tasks = db.trained_tasks.find({"user_id": current_user["id"]})
    matched_task = None
    for task in tasks:
        if task.get("name", "").lower() in user_message.lower():
            matched_task = task
            break

    if matched_task:
        # Gửi chuỗi hành động xuống Agent qua WebSocket
        actions = json.loads(matched_task.get("actions_json", "[]"))
        sent = await ws_manager.send_command(current_user["id"], {
            "type": "execution",
            "task_name": matched_task.get("name", ""),
            "actions": actions
        })
        ai_response = f"Đã gửi lệnh thực thi skill '{matched_task.get('name', '')}' xuống máy tính của bạn." if sent else "Không tìm thấy kết nối từ Desktop Agent trên máy bạn."
        action_result = "WebSocket Command Sent" if sent else "Agent Offline"
    else:
        # Xử lý các lệnh mặc định hoặc AI chat
        if "open chrome" in user_message.lower():
            sent = await ws_manager.send_command(current_user["id"], {"type": "direct", "action": "chrome"})
            ai_response = "Đang mở Chrome trên máy bạn..." if sent else "Agent offline."
            action_result = "Chrome Command Sent"
        elif "open notepad" in user_message.lower():
            sent = await ws_manager.send_command(current_user["id"], {"type": "direct", "action": "notepad"})
            ai_response = "Đang mở Notepad trên máy bạn..." if sent else "Agent offline."
            action_result = "Notepad Command Sent"
        else:
            ai_response = brain.process_message(user_message)
            action_result = None

    # Increment usage count in MongoDB
    db.usage.update_one(
        {"_id": ObjectId(usage["_id"])},
        {"$inc": {"request_count": 1}}
    )

    # Save chat history to MongoDB
    chat_history = {
        "user_id": current_user["id"],
        "message": user_message,
        "response": ai_response,
        "timestamp": datetime.datetime.utcnow()
    }
    db.message_history.insert_one(chat_history)

    return ChatResponse(
        response=ai_response,
        action_result=action_result
    )

@router.post("/agent/chat")
async def agent_chat_endpoint(
    request: ChatRequest,
    fastapi_req: Request,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    usage: dict = Depends(check_usage_limit)
):
    client_ip = fastapi_req.client.host
    check_rate_limit(client_ip)

    user_message = request.message
    logging.info(f"Agent Loop Input from {current_user.get('username', 'unknown')}: {user_message}")

    if not ws_manager.is_connected(current_user["id"]):
        raise HTTPException(status_code=400, detail="Desktop Agent chưa kết nối. Hãy chạy python desktop_agent.py")

    # Increment usage count in MongoDB
    db.usage.update_one(
        {"_id": ObjectId(usage["_id"])},
        {"$inc": {"request_count": 1}}
    )

    # Start the async generator
    return StreamingResponse(
        run_agent_loop(current_user["id"], user_message),
        media_type="application/x-ndjson"
    )


@router.get("/history", response_model=list[HistoryItem])
def get_history(
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Returns the last 20 messages for the current user."""
    history_cursor = db.message_history.find(
        {"user_id": current_user["id"]}
    ).sort(
        "timestamp", -1
    ).limit(20)

    history_list = []
    for doc in history_cursor:
        # Convert MongoDB document to HistoryItem format
        history_list.append(HistoryItem(
            message=doc.get("message", ""),
            response=doc.get("response", ""),
            timestamp=doc.get("timestamp", datetime.datetime.utcnow())
        ))

    return history_list


@router.get("/mongo/{collection_name}")
def read_mongo_collection(
    collection_name: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    if db is None:
        raise HTTPException(status_code=500, detail="MongoDB connection not configured.")

    allowed = {"users", "usage", "message_history", "transactions", "trained_tasks"}
    if collection_name not in allowed:
        raise HTTPException(status_code=404, detail="Collection not supported.")

    documents = list(db[collection_name].find().limit(100))
    for doc in documents:
        doc["_id"] = str(doc.get("_id"))
    return {"collection": collection_name, "count": len(documents), "documents": documents}


@router.post("/mongo/{collection_name}")
def insert_mongo_document(
    collection_name: str,
    document: Dict[str, Any],
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    if db is None:
        raise HTTPException(status_code=500, detail="MongoDB connection not configured.")

    allowed = {"users", "usage", "message_history", "transactions", "trained_tasks"}
    if collection_name not in allowed:
        raise HTTPException(status_code=404, detail="Collection not supported.")

    result = db[collection_name].insert_one(document)
    return {"inserted_id": str(result.inserted_id), "collection": collection_name}


@router.post("/mongo/refresh")
def refresh_mongo_data(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    if db is None:
        raise HTTPException(status_code=500, detail="MongoDB connection not configured.")

    # Refresh MongoDB data from SQLite tables.
    # Note: We are removing the refresh endpoint because we are no longer using SQLite.
    # But we can keep it as a no-op or remove it. Let's keep it as a no-op for now.
    # However, the original purpose was to copy from SQLite to MongoDB, which we don't have anymore.
    # We'll just return a message indicating that the refresh is not needed.
    return {
        "status": "no_refresh_needed",
        "message": "MongoDB is the primary storage. No refresh from SQLite needed."
    }