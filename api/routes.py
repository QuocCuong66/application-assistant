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
from api.automation import ConfirmRequest, confirm_agent_action, stop_agent
from services.control_center_chat import run_control_center_chat

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
        from services.intent_router import (
            AGENT_OFFLINE_MESSAGE,
            confirmation_prompt,
            detect_intent,
            execution_message,
            is_confirmation,
        )
        from services.pending_actions import clear_pending, get_pending, set_pending
        from services.desktop_executor import execute_desktop_action

        uid = current_user["id"]
        pending = get_pending(uid)
        if pending and is_confirmation(user_message) is True:
            action = clear_pending(uid)
            if ws_manager.is_connected(uid):
                await execute_desktop_action(uid, action)
                ai_response = execution_message(action)
                action_result = "Desktop action executed"
            else:
                ai_response = AGENT_OFFLINE_MESSAGE
                action_result = "Agent Offline"
        elif pending and is_confirmation(user_message) is False:
            clear_pending(uid)
            ai_response = "Okay, I won't run that action."
            action_result = None
        else:
            intent_result = detect_intent(user_message)
            action = intent_result.get("action")
            if action and intent_result.get("confidence", 0) >= 0.7:
                if not ws_manager.is_connected(uid):
                    ai_response = AGENT_OFFLINE_MESSAGE
                    action_result = "Agent Offline"
                elif action.get("requires_confirmation"):
                    set_pending(uid, action)
                    ai_response = confirmation_prompt(action)
                    action_result = "Confirmation required"
                else:
                    await execute_desktop_action(uid, action)
                    ai_response = execution_message(action)
                    action_result = "Desktop action queued"
            else:
                from services.control_center_chat import CONTROL_SYSTEM
                ai_response = brain.process_message(user_message, CONTROL_SYSTEM)
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
        "timestamp": datetime.datetime.now(datetime.timezone.utc)
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
    logging.info(f"Control Center chat from {current_user.get('username', 'unknown')}: {user_message}")

    # Increment usage count in MongoDB
    db.usage.update_one(
        {"_id": ObjectId(usage["_id"])},
        {"$inc": {"request_count": 1}}
    )

    return StreamingResponse(
        run_control_center_chat(current_user["id"], user_message, db=db),
        media_type="application/x-ndjson",
    )


@router.post("/agent/stop")
async def agent_stop_proxy(current_user: dict = Depends(get_current_user)):
    """Backward-compatible alias (frontend calls /agent/stop)."""
    return await stop_agent(current_user)


@router.post("/agent/confirm")
async def agent_confirm_proxy(
    req: ConfirmRequest,
    current_user: dict = Depends(get_current_user),
):
    """Backward-compatible alias (frontend calls /agent/confirm)."""
    return await confirm_agent_action(req, current_user)


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
            timestamp=doc.get("timestamp", datetime.datetime.now(datetime.timezone.utc))
        ))

    return history_list


@router.delete("/history")
def clear_history(
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Deletes chat history for the current user."""
    result = db.message_history.delete_many({"user_id": current_user["id"]})
    return {"message": "Chat history cleared.", "deleted_count": result.deleted_count}


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


@router.post("/voice/transcribe")
async def transcribe_voice(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Transcribes an uploaded audio file using OpenAI Whisper API (VC Skill)."""
    try:
        from voice.listener import Listener
        suffix = os.path.splitext(file.filename)[1] or ".mp3"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        listener = Listener()
        text = listener.transcribe_audio_file(tmp_path)
        
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
            
        return {"text": text}
    except Exception as e:
        logging.error(f"Error in /voice/transcribe: {e}")
        raise HTTPException(status_code=500, detail=f"Audio transcription error: {str(e)}")

