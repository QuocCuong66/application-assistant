from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
import json
import os
import logging
from typing import Dict
from datetime import datetime
from bson import ObjectId
import uuid
import asyncio

from database import get_db
from schemas import TrainedTaskCreate, TrainedTaskResponse, TrainedTaskUpdate
from api.deps import get_current_user
from config import AGENT_TOKEN
from pydantic import BaseModel

router = APIRouter(prefix="/automation", tags=["automation"])

# Quản lý kết nối WebSocket theo user_id
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.pending_requests: Dict[str, Dict[str, asyncio.Future]] = {}
        self.user_events: Dict[str, asyncio.Event] = {}
        self.stop_flags: Dict[str, bool] = {}
        self.user_confirm_results: Dict[str, str] = {} # 'confirm' or 'cancel'

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        if user_id not in self.pending_requests:
            self.pending_requests[user_id] = {}
        self.stop_flags[user_id] = False
        logging.info(f"Agent connected for user: {user_id}")

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logging.info(f"Agent disconnected for user: {user_id}")
        if user_id in self.pending_requests:
            for req_id, future in list(self.pending_requests[user_id].items()):
                if not future.done():
                    future.set_exception(Exception("Agent disconnected"))
            del self.pending_requests[user_id]
        if user_id in self.user_events:
            self.user_confirm_results[user_id] = 'cancel'
            self.user_events[user_id].set()

    def is_connected(self, user_id: str) -> bool:
        return user_id in self.active_connections

    async def send_command(self, user_id: str, command: dict):
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(command)
                return True
            except Exception as e:
                logging.error(f"Error sending command to {user_id}: {e}")
                self.disconnect(user_id)
        return False

    async def send_command_and_wait(self, user_id: str, command: dict, timeout=30):
        if user_id not in self.active_connections:
            return {"success": False, "error": "Agent offline"}
            
        request_id = str(uuid.uuid4())
        command["request_id"] = request_id
        future = asyncio.get_event_loop().create_future()
        
        if user_id not in self.pending_requests:
            self.pending_requests[user_id] = {}
        self.pending_requests[user_id][request_id] = future
        
        try:
            await self.active_connections[user_id].send_json(command)
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            if user_id in self.pending_requests and request_id in self.pending_requests[user_id]:
                del self.pending_requests[user_id][request_id]
            return {"success": False, "error": "Timeout"}
        except Exception as e:
            if user_id in self.pending_requests and request_id in self.pending_requests[user_id]:
                del self.pending_requests[user_id][request_id]
            return {"success": False, "error": str(e)}

manager = ConnectionManager()

class ConfirmRequest(BaseModel):
    action: str # "confirm" or "cancel"

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str, token: str = None):
    if token != AGENT_TOKEN:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await manager.connect(user_id, websocket)
    db = get_db()
    try:
        while True:
            data_str = await websocket.receive_text()
            try:
                data = json.loads(data_str)
                if data.get("type") == "save_task":
                    # Lưu task vào db
                    task_doc = {
                        "user_id": user_id,
                        "name": data.get("task_name", "Untitled Task"),
                        "actions_json": json.dumps(data.get("actions", [])),
                        "created_at": datetime.utcnow()
                    }
                    db.trained_tasks.insert_one(task_doc)
                    logging.info(f"Task '{task_doc['name']}' saved successfully for user {user_id}.")
                
                elif data.get("type") == "tool_result":
                    req_id = data.get("request_id")
                    if req_id and user_id in manager.pending_requests:
                        if req_id in manager.pending_requests[user_id]:
                            future = manager.pending_requests[user_id][req_id]
                            if not future.done():
                                future.set_result(data)
                            del manager.pending_requests[user_id][req_id]
                    
            except json.JSONDecodeError:
                logging.warning(f"Invalid JSON received from agent {user_id}: {data_str}")
    except WebSocketDisconnect:
        manager.disconnect(user_id)

@router.post("/agent/stop")
async def stop_agent(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    manager.stop_flags[user_id] = True
    if user_id in manager.user_events:
        manager.user_confirm_results[user_id] = 'cancel'
        manager.user_events[user_id].set()
    
    # Optional: Send control stop to desktop agent
    await manager.send_command(user_id, {"type": "control", "command": "stop"})
    return {"message": "Agent stop signal sent."}

@router.post("/agent/confirm")
async def confirm_agent_action(req: ConfirmRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    if user_id in manager.user_events:
        manager.user_confirm_results[user_id] = req.action
        manager.user_events[user_id].set()
        return {"message": f"Action {req.action} received."}
    return {"message": "No pending action to confirm."}

@router.post("/training/start")
async def start_training(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    if not manager.is_connected(user_id):
        raise HTTPException(status_code=400, detail="Desktop Agent offline. Please run the agent on your local machine.")
    
    success = await manager.send_command(user_id, {"type": "training_start"})
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send command to Desktop Agent.")

    return {"message": "Training start command sent. Desktop Agent is recording actions."}

@router.post("/training/stop")
async def stop_training(
    task_data: TrainedTaskCreate,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["id"]
    if not manager.is_connected(user_id):
        raise HTTPException(status_code=400, detail="Desktop Agent offline. Please run the agent on your local machine.")

    success = await manager.send_command(user_id, {
        "type": "training_stop",
        "task_name": task_data.name
    })
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send stop command to Desktop Agent.")

    return {"message": "Training stop command sent. Task will be saved when agent returns actions."}

@router.get("/tasks", response_model=list[TrainedTaskResponse])
async def get_tasks(
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    trained_tasks = db.trained_tasks.find({"user_id": current_user["id"]})
    task_list = []
    for task in trained_tasks:
        task["id"] = str(task["_id"])
        task_list.append(task)
    return task_list

@router.post("/execute/{task_id}")
async def execute_task(
    task_id: str,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["id"]
    if not manager.is_connected(user_id):
        raise HTTPException(status_code=400, detail="Desktop Agent offline. Please run the agent on your local machine.")

    trained_tasks = db.trained_tasks
    task = trained_tasks.find_one({"_id": ObjectId(task_id), "user_id": user_id})

    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    actions = json.loads(task.get("actions_json", "[]"))
    if not actions:
        raise HTTPException(status_code=400, detail="Task has no actions to execute.")

    success = await manager.send_command(user_id, {
        "type": "execution",
        "task_name": task.get("name"),
        "actions": actions
    })

    if not success:
        raise HTTPException(status_code=500, detail="Failed to send execution command to Desktop Agent.")

    return {"message": f"Execution command for '{task.get('name')}' sent to agent."}

@router.put("/tasks/{task_id}", response_model=TrainedTaskResponse)
async def update_task(
    task_id: str,
    task_data: TrainedTaskUpdate,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    trained_tasks = db.trained_tasks
    task = trained_tasks.find_one({"_id": ObjectId(task_id), "user_id": current_user["id"]})

    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    update_doc = {}
    if task_data.name is not None:
        update_doc["name"] = task_data.name
    if task_data.note is not None:
        update_doc["note"] = task_data.note

    if update_doc:
        trained_tasks.update_one({"_id": ObjectId(task_id)}, {"$set": update_doc})

    updated_task = trained_tasks.find_one({"_id": ObjectId(task_id)})
    updated_task["id"] = str(updated_task["_id"])
    return updated_task

@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    trained_tasks = db.trained_tasks
    result = trained_tasks.delete_one({"_id": ObjectId(task_id), "user_id": current_user["id"]})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found.")

    return {"message": "Task deleted successfully"}
