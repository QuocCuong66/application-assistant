import logging
import json
import os

class Planner:
    def __init__(self):
        pass
        
    def match_trained_task(self, text: str, db_session, user_id: int) -> str:
        """Matches user input with trained tasks in the database."""
        from models import TrainedTask
        
        tasks = db_session.query(TrainedTask).filter(TrainedTask.user_id == user_id).all()
        text_lower = text.lower()
        
        for task in tasks:
            # Match strict #skill_name or normal name in text
            if f"#{task.name.lower()}" in text_lower or task.name.lower() in text_lower:
                logging.info(f"Matched trained task: {task.name}")
                
                # Execution is now handled entirely via WebSockets in routes.py
                return "execution_via_ws"
        return None

    def detect_and_execute_intent(self, text: str, db_session=None, user_id=None) -> str:
        """Detects simple intents like opening apps and executes them."""
        text_lower = text.lower()
        
        # 1. Check trained tasks first
        if db_session and user_id:
            trained_result = self.match_trained_task(text, db_session, user_id)
            if trained_result:
                return trained_result

        # 2. Check built-in intents
        if "open chrome" in text_lower:
            logging.info("Detected action: Open Chrome")
            return "direct:chrome"
        elif "open notepad" in text_lower:
            logging.info("Detected action: Open Notepad")
            return "direct:notepad"
            
        return None
