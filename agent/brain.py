from openai import OpenAI
from config import OPENAI_API_KEY
import logging


from typing import List, Dict, Optional

class Brain:
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.model = "gpt-4o-mini"

    def process_message(
        self,
        message: str,
        system_prompt: Optional[str] = None,
        history_messages: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Sends a message to OpenAI API with conversation history support and returns response."""
        try:
            logging.info(f"Sending prompt to OpenAI: {message}")
            messages = [{"role": "system", "content": system_prompt or "You are a helpful AI assistant."}]
            
            if history_messages and isinstance(history_messages, list):
                for item in history_messages:
                    if isinstance(item, dict) and "role" in item and "content" in item:
                        messages.append({"role": item["role"], "content": item["content"]})
            
            messages.append({"role": "user", "content": message})

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                timeout=15.0
            )
            ai_response = response.choices[0].message.content
            return ai_response
        except Exception as e:
            logging.error(f"Error communicating with OpenAI: {str(e)}")
            return "I'm sorry, I encountered an error while processing your request."

