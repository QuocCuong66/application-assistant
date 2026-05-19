import os
from datetime import datetime
import io
import base64

class VisionSystem:
    def __init__(self, storage_dir=None):
        self.storage_dir = storage_dir or "/tmp/screenshots"
        if os.environ.get("VERCEL") == "1":
            self.storage_dir = "/tmp/screenshots"
        os.makedirs(self.storage_dir, exist_ok=True)

    def capture_fullscreen(self, save=True):
        """Captures full screen and returns image data."""
        # Backend does not support screen capturing directly anymore.
        return {"path": None, "data": "", "size": (0,0), "error": "Not supported on Backend"}

    def detect_ui_elements(self, image_data):
        return [
            {"text": "Login", "x": 100, "y": 200, "width": 50, "height": 20},
            {"text": "Submit", "x": 300, "y": 400, "width": 60, "height": 30}
        ]
