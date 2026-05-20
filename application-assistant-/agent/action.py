import os
import subprocess
import platform
import time
import json

try:
    import pyautogui
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

class ActionExecutor:
    def smart_click(self, elements, target_text):
        """Finds matching element by text and clicks its center."""
        if not HAS_PYAUTOGUI:
            return "Smart Click not supported on Vercel."
            
        target_text = target_text.lower()
        for el in elements:
            if target_text in el["text"].lower():
                center_x = el["x"] + el["width"] / 2
                center_y = el["y"] + el["height"] / 2
                pyautogui.click(center_x, center_y)
                return f"Clicked '{el['text']}' at ({center_x}, {center_y})"
        return f"Element with text '{target_text}' not found."

    def replay_actions(self, actions_file):
        """Reads recorded actions and executes them in order with timing."""
        try:
            with open(actions_file, 'r') as f:
                actions = json.load(f)
            
            if not actions:
                return "No actions to replay."

            last_time = 0
            for action in actions:
                # Wait for the recorded delay
                delay = action["time"] - last_time
                if delay > 0:
                    time.sleep(delay)
                
                self.execute_recorded_action(action)
                last_time = action["time"]
            
            return f"Successfully replayed {len(actions)} actions."
        except Exception as e:
            return f"Replay failed: {str(e)}"

    def execute_recorded_action(self, action_data):
        """Executes a single action from recorded data."""
        action = action_data["action"]
        params = action_data["parameters"]
        
        if action == "click":
            pyautogui.click(params["x"], params["y"])
        elif action == "type":
            text = params["text"]
            # Handle special keys if necessary
            if len(text) > 1 and text.startswith("Key."):
                key_name = text.split(".")[1]
                pyautogui.press(key_name)
            else:
                pyautogui.write(text)

    def execute(self, action: str) -> str:
        """Executes simple system commands."""
        action = action.lower().strip()
        system = platform.system()
        
        try:
            if "chrome" in action:
                if system == "Windows":
                    os.startfile("chrome.exe")
                elif system == "Darwin":
                    subprocess.Popen(["open", "-a", "Google Chrome"])
                else:
                    subprocess.Popen(["google-chrome"])
                return "Opened Google Chrome."
                
            elif "notepad" in action:
                if system == "Windows":
                    subprocess.Popen(["notepad.exe"])
                elif system == "Darwin":
                    subprocess.Popen(["open", "-a", "TextEdit"])
                else:
                    subprocess.Popen(["gedit"])
                return "Opened Notepad."
                
            return "No valid action found."
        except Exception as e:
            return f"Failed to execute action: {str(e)}"
