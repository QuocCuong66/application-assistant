from openai import OpenAI, AsyncOpenAI
from config import OPENAI_API_KEY, GEMINI_API_KEY, GEMINI_MODEL
import logging


from typing import AsyncGenerator, List, Dict, Optional

ERROR_REPLY = "I'm sorry, I encountered an error while processing your request."

class Brain:
    def __init__(self):
        if GEMINI_API_KEY:
            client_kwargs = {
                "api_key": GEMINI_API_KEY,
                "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
            }
            self.model = GEMINI_MODEL or "gemini-2.5-flash"
        else:
            client_kwargs = {"api_key": OPENAI_API_KEY or "dummy-key"}
            self.model = "gpt-4o-mini"
        self.client = OpenAI(**client_kwargs)
        self.async_client = AsyncOpenAI(**client_kwargs)

    @staticmethod
    def _build_messages(
        message: str,
        system_prompt: Optional[str] = None,
        history_messages: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, str]]:
        messages = [{"role": "system", "content": system_prompt or "You are a helpful AI assistant."}]

        if history_messages and isinstance(history_messages, list):
            for item in history_messages:
                if isinstance(item, dict) and "role" in item and "content" in item:
                    messages.append({"role": item["role"], "content": item["content"]})

        messages.append({"role": "user", "content": message})
        return messages

    def process_message(
        self,
        message: str,
        system_prompt: Optional[str] = None,
        history_messages: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Sends a message to OpenAI API with conversation history support and returns response."""
        try:
            logging.info(f"Sending prompt to OpenAI: {message}")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self._build_messages(message, system_prompt, history_messages),
                timeout=15.0
            )
            ai_response = response.choices[0].message.content
            return ai_response
        except Exception as e:
            logging.error(f"Error communicating with OpenAI: {str(e)}")
            return ERROR_REPLY

    async def stream_message(
        self,
        message: str,
        system_prompt: Optional[str] = None,
        history_messages: Optional[List[Dict[str, str]]] = None,
    ) -> AsyncGenerator[str, None]:
        """Streams the response token-by-token. Yields text deltas; yields ERROR_REPLY on failure before any output."""
        emitted = False
        try:
            logging.info(f"Streaming prompt to OpenAI: {message}")
            stream = await self.async_client.chat.completions.create(
                model=self.model,
                messages=self._build_messages(message, system_prompt, history_messages),
                stream=True,
                timeout=15.0,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    emitted = True
                    yield delta
        except Exception as e:
            logging.error(f"Error streaming from OpenAI: {str(e)}")
            if not emitted:
                yield ERROR_REPLY
