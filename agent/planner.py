import logging

class Planner:
    def __init__(self):
        pass
        
    def match_trained_task(self, text: str, db, user_id: str):
        """Matches user input with trained tasks in MongoDB."""
        if db is None or not user_id:
            return None

        text_lower = (text or "").lower().strip()
        tasks = list(db.trained_tasks.find({"user_id": user_id}))
        
        for task in tasks:
            task_name = task.get("name", "").lower().strip()
            if task_name and (f"#{task_name}" in text_lower or task_name in text_lower):
                logging.info(f"Matched trained task: {task.get('name')}")
                return task
        return None

