from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
import json
import os
from typing import Dict
from datetime import datetime
from bson import ObjectId

from database import get_db
from schemas import TrainedTaskCreate, TrainedTaskResponse, TrainedTaskUpdate
from api.deps import get_current_user
from agent.recorder import ActionRecorder
from agent.action import ActionExecutor

router = APIRouter(prefix="/automation", tags=["automation"])
recorder = ActionRecorder()
executor = ActionExecutor()

# Quản lý kết nối WebSocket theo user_id
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_command(self, user_id: str, command: dict):
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_json(command)
            return True
        return False

manager = ConnectionManager()

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(user_id, websocket)
    try:
        while True:
            # Nhận tín hiệu từ Agent (nếu cần phản hồi ngược lại)
            data = await websocket.receive_text()
            # Xử lý log hoặc phản hồi từ Agent
    except WebSocketDisconnect:
        manager.disconnect(user_id)

@router.post("/training/start")
async def start_training(current_user: dict = Depends(get_current_user)):
    recorder.start_recording()
    return {"message": "Training started. Actions are being recorded."}

@router.post("/training/stop")
async def stop_training(
    task_data: TrainedTaskCreate,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    actions = recorder.stop_recording()
    if not actions:
        raise HTTPException(status_code=400, detail="No actions were recorded.")

    # Create task document
    task_doc = {
        "user_id": current_user["id"],  # This is now a string from get_current_user
        "name": task_data.name,
        "actions_json": json.dumps(actions),
        "created_at": datetime.utcnow()
    }
    trained_tasks = db.trained_tasks
    result = trained_tasks.insert_one(task_doc)

    return {"message": f"Task '{task_data.name}' saved successfully.", "task_id": str(result.inserted_id)}

@router.get("/tasks", response_model=list[TrainedTaskResponse])
async def get_tasks(
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    trained_tasks = db.trained_tasks.find({"user_id": current_user["id"]})
    # Convert to list of dicts and ensure id is string
    task_list = []
    for task in trained_tasks:
        task["id"] = str(task["_id"])  # Add id field for Pydantic model
        task_list.append(task)
    return task_list

@router.post("/execute/{task_id}")
async def execute_task(
    task_id: str,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    trained_tasks = db.trained_tasks
    # Find task by id and user_id
    task = trained_tasks.find_one({"_id": ObjectId(task_id), "user_id": current_user["id"]})

    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    # Save to temp file for the replay_actions method
    temp_file = f"temp_task_{task_id}.json"
    with open(temp_file, 'w') as f:
        f.write(task["actions_json"])

    try:
        result = executor.replay_actions(temp_file)
        return {"message": result}
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)

@router.put("/tasks/{task_id}", response_model=TrainedTaskResponse)
async def update_task(
    task_id: str,
    task_data: TrainedTaskUpdate,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    trained_tasks = db.trained_tasks
    # Find task by id and user_id
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

    # Get updated task
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
    # Find task by id and user_id
    result = trained_tasks.delete_one({"_id": ObjectId(task_id), "user_id": current_user["id"]})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found.")

    return {"message": "Task deleted successfully"}
