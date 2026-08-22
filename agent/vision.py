import os
from datetime import datetime


class VisionSystem:
    """Thin utility for screenshot storage paths.

    Actual vision analysis is performed by GPT-4o/Gemini via prompt_builder
    and agent_loop.  Precise click coordinates are resolved locally on the
    Desktop Agent via screen_reader.py (Windows UI Automation + optional OCR).

    Screenshots are captured on the Desktop Agent side and sent to the
    backend via WebSocket.
    """

    def __init__(self, storage_dir=None):
        self.storage_dir = storage_dir or "/tmp/screenshots"
        if os.environ.get("VERCEL") == "1":
            self.storage_dir = "/tmp/screenshots"
        os.makedirs(self.storage_dir, exist_ok=True)
