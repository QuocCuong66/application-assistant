from openai import OpenAI
from config import OPENAI_API_KEY
import logging
import json
import time
import os

from agent.vision import VisionSystem

class Brain:
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.model = "gpt-4o-mini"
        self.vision = VisionSystem()
        
    def reason_and_act_loop(self, task_description: str, max_steps: int = 5):
        """
        Controlled loop: Capture -> Detect -> AI Decide -> Execute.
        Repeats until task is complete or max_steps reached.
        """
        # Note: automation is no longer supported on the backend directly.
        # This function should be deprecated or refactored to emit WebSocket commands.
        return "Backend automation loop is deprecated. Please use Desktop Agent directly."

        logging.info(f"Starting Reason & Act loop for task: {task_description}")
        steps = 0
        
        while steps < max_steps:
            steps += 1
            logging.info(f"Step {steps}/{max_steps}")
            
            # 1. Capture screen
            screenshot_info = self.vision.capture_fullscreen(save=True)
            
            # 2. Detect UI elements (mocked in vision.py)
            elements = self.vision.detect_ui_elements(screenshot_info["data"])
            
            # 3. AI Decides next action
            # We provide the task, screenshot data (base64), and elements to AI
            prompt = f"""
            Task: {task_description}
            Step: {steps}/{max_steps}
            Detected UI Elements: {json.dumps(elements)}
            
            Decide the next action. Return JSON format:
            {{
                "action": "click" | "type" | "complete" | "wait",
                "target": "text of element",
                "text_to_type": "if action is type",
                "reason": "why this action"
            }}
            """
            
            try:
                # In a real scenario, we'd use gpt-4o with image input
                # For this demo, we use text-based decision based on detected elements
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a desktop automation agent. Decide the next step based on the UI elements."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"}
                )
                
                decision = json.loads(response.choices[0].message.content)
                logging.info(f"AI Decision: {decision}")
                
                if decision["action"] == "complete":
                    return f"Task completed: {decision['reason']}"
                
                if decision["action"] == "click":
                    logging.info(f"AI decided to click on: {decision['target']}. Skipping execution since backend automation is disabled.")
                
                elif decision["action"] == "type":
                    logging.info(f"AI decided to type '{decision['text_to_type']}' into '{decision['target']}'. Skipping execution since backend automation is disabled.")
                
                elif decision["action"] == "wait":
                    time.sleep(2)
                    logging.info("Waiting...")

            except Exception as e:
                logging.error(f"Error in loop step {steps}: {str(e)}")
                break
                
        return f"Loop ended after {steps} steps."

    def process_message(self, message: str, system_prompt=None) -> str:
        """Sends a message to OpenAI API and returns the response."""
        try:
            logging.info(f"Sending prompt to OpenAI: {message}")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt or "You are a helpful AI assistant."},
                    {"role": "user", "content": message}
                ],
                timeout=15.0
            )
            ai_response = response.choices[0].message.content
            return ai_response
        except Exception as e:
            logging.error(f"Error communicating with OpenAI: {str(e)}")
            return "I'm sorry, I encountered an error while processing your request."
