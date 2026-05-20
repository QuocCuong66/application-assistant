try:
    import pyautogui
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

import os
from datetime import datetime
import io
import base64
from PIL import Image

import os

class VisionSystem:
    def __init__(self, storage_dir=None):
        # Use /tmp/screenshots by default for serverless environments like Vercel.
        self.storage_dir = storage_dir or "/tmp/screenshots"
        if os.environ.get("VERCEL") == "1":
            self.storage_dir = "/tmp/screenshots"

        # Ensure the storage directory exists.
        os.makedirs(self.storage_dir, exist_ok=True)
    def capture_fullscreen(self, save=True):
        """Captures full screen and returns image data."""
        if not HAS_PYAUTOGUI:
            return {"path": None, "data": "", "size": (0,0), "error": "Not supported on Vercel"}

        screenshot = pyautogui.screenshot()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        filepath = os.path.join(self.storage_dir, filename)
        
        if save:
            screenshot.save(filepath)
            
        # Prepare for AI processing (convert to base64)
        buffered = io.BytesIO()
        screenshot.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        return {
            "path": filepath if save else None,
            "data": img_str,
            "size": screenshot.size
        }

    def detect_ui_elements(self, image_data):
        """
        Placeholder for AI detection of UI elements.
        In a real scenario, this would call a Vision model.
        Returns a list of elements with text and coordinates.
        """
        # Mock detection for now
        return [
            {"text": "Login", "x": 100, "y": 200, "width": 50, "height": 20},
            {"text": "Submit", "x": 300, "y": 400, "width": 60, "height": 30}
        ]
