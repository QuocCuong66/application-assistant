from openai import OpenAI
from config import OPENAI_API_KEY
import logging


class Brain:
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.model = "gpt-4o-mini"

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
