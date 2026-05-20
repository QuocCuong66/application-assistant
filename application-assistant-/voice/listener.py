from openai import OpenAI
import os
import tempfile
import logging
import requests
import time
from config import OPENAI_API_KEY

class Listener:
    def __init__(self):
        logging.info("Initializing Listener with OpenAI Whisper API...")
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        
    def transcribe_audio_file(self, file_path: str) -> str:
        """Converts an audio file to text using OpenAI Whisper API."""
        try:
            logging.info(f"Transcribing audio file via API: {file_path}")
            with open(file_path, "rb") as audio_file:
                transcription = self.client.audio.transcriptions.create(
                    model="whisper-1", 
                    file=audio_file
                )
            text = transcription.text.strip()
            logging.info(f"Transcribed text: {text}")
            return text
        except Exception as e:
            logging.error(f"Error during API transcription: {str(e)}")
            return ""

    def run_continuous_client(self, token: str, server_url: str = "http://localhost:8000"):
        """
        Lắng nghe liên tục (sử dụng API). 
        Lưu ý: Để chạy cái này cục bộ, bạn vẫn cần SpeechRecognition và PyAudio 
        để ghi âm từ mic, nhưng việc xử lý AI sẽ đẩy lên cloud.
        """
        logging.info("Chế độ Chat Voice qua API. Đang đợi tích hợp ghi âm cục bộ...")
        # Đây là placeholder vì Vercel không hỗ trợ Microphone trực tiếp.
        # Việc ghi âm nên thực hiện ở phía trình duyệt (Client-side) hoặc script cục bộ.
        pass
