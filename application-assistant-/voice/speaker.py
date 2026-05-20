import pyttsx3
import logging

class Speaker:
    def __init__(self):
        self.engine = pyttsx3.init()
        # You can adjust properties like speed and volume here
        self.engine.setProperty('rate', 170)
        
    def speak(self, text: str):
        """Converts text to speech and plays it."""
        try:
            logging.info(f"Speaking: {text}")
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception as e:
            logging.error(f"Error during speech synthesis: {str(e)}")
