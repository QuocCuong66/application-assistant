from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
import json
import os
import logging
from typing import Dict
from datetime import datetime
from bson import ObjectId

from database import get_db
from schemas import TrainedTaskCreate, TrainedTaskResponse, TrainedTaskUpdate
from api.deps import get_current_user

router = APIRouter(prefix="/automation", tags=["automation"])

# Quản lý kết nối WebSocket theo user_id
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logging.info(f"Agent connected for user: {user_id}")

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logging.info(f"Agent disconnected for user: {user_id}")

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

manager = ConnectionManager()

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
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
                    
            except json.JSONDecodeError:
                logging.warning(f"Invalid JSON received from agent {user_id}: {data_str}")
    except WebSocketDisconnect:
        manager.disconnect(user_id)

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
