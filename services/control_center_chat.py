"""
Control Center chat stream: intent routing, confirmations, desktop actions.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict

# Per-user lock to prevent concurrent agent loops (mitigates R10)
_agent_locks: Dict[str, asyncio.Lock] = {}

from api.automation import manager as ws_manager
from agent.brain import Brain
from services.agent_loop import run_agent_loop
from services.desktop_executor import execute_desktop_action
from services.intent_router import (
    AGENT_OFFLINE_MESSAGE,
    confirmation_prompt,
    detect_intent,
    execution_message,
    is_confirmation,
)
from services.pending_actions import clear_pending, get_pending, set_pending, pop_pending

brain = Brain()

CONTROL_SYSTEM = (
    "You are the AI Control Center assistant for desktop automation. "
    "Keep answers short (1-3 sentences). "
    "If the user wants to open apps, click, type, scroll, or capture the screen, "
    "tell them you can do it via Desktop Agent and ask them to phrase a clear command "
    "(e.g. 'open Google Chrome') — do NOT give long manual step-by-step OS tutorials."
)


def _yield_line(payload: Dict[str, Any]) -> str:
    return json.dumps(payload) + "\n"


async def _stream_text_fake(message: str, state: str = "completed") -> AsyncGenerator[str, None]:
    words = message.split()
    partial = ""
    for i, word in enumerate(words):
        partial = f"{partial} {word}".strip()
        if i % 2 == 1 or i == len(words) - 1:
            yield _yield_line({"type": "partial", "state": "thinking", "message": partial})
            await asyncio.sleep(0.04)
    yield _yield_line({"type": "final", "state": state, "message": message})


def _save_history(db, user_id: str, message: str, response: str) -> None:
    if db is None or not response:
        return
    import datetime
    db.message_history.insert_one({
        "user_id": user_id,
        "message": message,
        "response": response,
        "timestamp": datetime.datetime.now(datetime.timezone.utc),
    })


def _should_use_agent_loop(message: str, intent_result: Dict[str, Any]) -> bool:
    if intent_result.get("intent") == "agent_loop":
        return True
    text = message.lower()
    if len(text.split()) > 12 and any(
        w in text for w in ("click on", "find", "button", "window", "screen", "website", "form")
    ):
        return True
    return False


async def _analyze_screenshot_with_vision(base64_data: str, user_prompt: str) -> str:
    """Analyze a captured desktop screenshot using Gemini 2.5 Flash Vision or OpenAI Vision."""
    try:
        from config import GEMINI_API_KEY, GEMINI_MODEL, OPENAI_API_KEY, OPENAI_VISION_MODEL
        from openai import OpenAI

        if GEMINI_API_KEY:
            client = OpenAI(
                api_key=GEMINI_API_KEY,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
            )
            model_name = GEMINI_MODEL or "gemini-2.5-flash"
        else:
            client = brain.client
            model_name = OPENAI_VISION_MODEL or "gpt-4o"

        logging.info(f"Analyzing screenshot using Vision model '{model_name}'...")

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert AI assistant analyzing a desktop screenshot for the user. "
                    "Provide a helpful, structured analysis in the user's language (e.g. Vietnamese if prompt is in Vietnamese). "
                    "Keep it concise (3-5 sentences) unless a detailed breakdown is requested."
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"User question/request: {user_prompt}"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_data}",
                            "detail": "high",
                        },
                    },
                ],
            },
        ]
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=model_name,
            messages=messages,
            max_tokens=600,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error("Error analyzing screenshot with Vision API: %s", e)
        return f"Capturing screenshot succeeded, but AI vision analysis encountered an error: {e}"


async def _handle_desktop_intent(
    user_id: str,
    message: str,
    intent_result: Dict[str, Any],
    db,
) -> AsyncGenerator[str, None]:
    action = intent_result.get("action") or {}
    skill_id = intent_result.get("skill_id") or "DC"
    tool = action.get("tool")

    logging.info(
        "Intent detected for %s: intent=%s confidence=%.2f tool=%s",
        user_id,
        intent_result.get("intent"),
        intent_result.get("confidence", 0),
        tool,
    )

    yield _yield_line({
        "type": "intent",
        "intent": intent_result.get("intent"),
        "skill_id": skill_id,
        "skill_status": "active",
        "confidence": intent_result.get("confidence"),
    })

    if not ws_manager.is_connected(user_id):
        logging.warning("Intent blocked: Desktop Agent not connected for %s", user_id)
        yield _yield_line({"type": "intent", "skill_id": skill_id, "skill_status": "ready"})
        async for line in _stream_text_fake(AGENT_OFFLINE_MESSAGE, "error"):
            yield line
        _save_history(db, user_id, message, AGENT_OFFLINE_MESSAGE)
        return

    if action.get("requires_confirmation", True):
        set_pending(user_id, action)
        prompt = confirmation_prompt(action)
        logging.info("Confirmation required for user %s", user_id)
        yield _yield_line({
            "type": "state",
            "state": "waiting_confirmation",
            "message": prompt,
        })
        async for line in _stream_text_fake(prompt):
            yield line
        _save_history(db, user_id, message, prompt)
        return

    yield _yield_line({"type": "intent", "skill_id": skill_id, "skill_status": "training"})
    yield _yield_line({"type": "state", "state": "acting", "message": "Task queued…"})
    result = await execute_desktop_action(user_id, action)

    if result.get("success"):
        if tool == "screenshot" and result.get("result", {}).get("data"):
            base64_img = result["result"]["data"]
            analysis = await _analyze_screenshot_with_vision(base64_img, message)
            final = f"📸 **Phân tích màn hình:**\n\n{analysis}"
        else:
            final = execution_message(action)
    else:
        final = AGENT_OFFLINE_MESSAGE

    logging.info("Task queued for %s: success=%s", user_id, result.get("success"))
    async for line in _stream_text_fake(final):
        yield line
    yield _yield_line({"type": "intent", "skill_id": skill_id, "skill_status": "ready"})
    _save_history(db, user_id, message, final)


async def run_control_center_chat(user_id: str, message: str, db=None) -> AsyncGenerator[str, None]:
    yield _yield_line({
        "type": "log",
        "state": "thinking",
        "message": f"Processing: {message[:120]}",
    })

    # Pending confirmation (yes / no)
    pending = get_pending(user_id)
    if pending:
        decision = is_confirmation(message)
        if decision is not None:
            skill_id = pending.get("skill_id", "DC")
            if decision is False:
                clear_pending(user_id)
                msg = "Okay, I won't run that action."
                yield _yield_line({"type": "intent", "skill_id": skill_id, "skill_status": "ready"})
                async for line in _stream_text_fake(msg):
                    yield line
                _save_history(db, user_id, message, msg)
                return

            logging.info("User confirmed pending action for %s", user_id)
            action = pop_pending(user_id)
            yield _yield_line({
                "type": "log",
                "state": "thinking",
                "message": "Confirmation received. Running desktop action…",
            })
            yield _yield_line({"type": "intent", "skill_id": skill_id, "skill_status": "training"})

            if not ws_manager.is_connected(user_id):
                async for line in _stream_text_fake(AGENT_OFFLINE_MESSAGE, "error"):
                    yield line
                yield _yield_line({"type": "intent", "skill_id": skill_id, "skill_status": "ready"})
                _save_history(db, user_id, message, AGENT_OFFLINE_MESSAGE)
                return

            yield _yield_line({"type": "state", "state": "acting", "message": "Sending task to Desktop Agent…"})
            result = await execute_desktop_action(user_id, action)
            if result.get("success"):
                if action.get("tool") == "screenshot" and result.get("result", {}).get("data"):
                    base64_img = result["result"]["data"]
                    user_req = action.get("user_message", message)
                    analysis = await _analyze_screenshot_with_vision(base64_img, user_req)
                    final = f"📸 **Phân tích màn hình:**\n\n{analysis}"
                else:
                    final = execution_message(action)
                logging.info("Task executed for user %s: %s", user_id, action.get("tool"))
            else:
                err = result.get("error", "unknown")
                final = AGENT_OFFLINE_MESSAGE if err == "agent_offline" else f"Could not run the action: {err}"

            async for line in _stream_text_fake(final):
                yield line
            yield _yield_line({"type": "intent", "skill_id": skill_id, "skill_status": "ready"})
            _save_history(db, user_id, message, final)
            return

    # Check trained skills in MongoDB (Auto Skill AT)
    if db is not None:
        from agent.planner import Planner
        planner = Planner()
        matched_task = planner.match_trained_task(message, db, user_id)
        if matched_task:
            task_name = matched_task.get("name", "Trained Skill")
            actions_str = matched_task.get("actions_json", "[]")
            try:
                actions = json.loads(actions_str) if isinstance(actions_str, str) else actions_str
            except Exception:
                actions = []

            yield _yield_line({
                "type": "intent",
                "intent": "trained_task",
                "skill_id": "AT",
                "skill_status": "training",
                "confidence": 1.0,
            })

            if not ws_manager.is_connected(user_id):
                async for line in _stream_text_fake(AGENT_OFFLINE_MESSAGE, "error"):
                    yield line
                yield _yield_line({"type": "intent", "skill_id": "AT", "skill_status": "ready"})
                _save_history(db, user_id, message, AGENT_OFFLINE_MESSAGE)
                return

            yield _yield_line({"type": "state", "state": "acting", "message": f"Executing skill '{task_name}'…"})
            sent = await ws_manager.send_command(user_id, {
                "type": "execution",
                "task_name": task_name,
                "actions": actions
            })
            reply = f"Đã gửi lệnh thực thi skill '{task_name}' xuống máy tính của bạn." if sent else AGENT_OFFLINE_MESSAGE
            async for line in _stream_text_fake(reply):
                yield line
            yield _yield_line({"type": "intent", "skill_id": "AT", "skill_status": "ready"})
            _save_history(db, user_id, message, reply)
            return

    intent_result = detect_intent(message)
    action = intent_result.get("action")
    confidence = intent_result.get("confidence", 0)

    if action and confidence >= 0.7:
        async for line in _handle_desktop_intent(user_id, message, intent_result, db):
            yield line
        return

    if ws_manager.is_connected(user_id) and _should_use_agent_loop(message, intent_result):
        # Concurrency guard — only one agent loop per user at a time (R10)
        if user_id not in _agent_locks:
            _agent_locks[user_id] = asyncio.Lock()

        if _agent_locks[user_id].locked():
            msg = "An agent loop is already running for your account. Stop it first."
            async for line in _stream_text_fake(msg, "error"):
                yield line
            _save_history(db, user_id, message, msg)
            return

        logging.info("Routing to agent loop for user %s", user_id)
        yield _yield_line({
            "type": "intent",
            "intent": "agent_loop",
            "skill_id": "RA",
            "skill_status": "training",
        })
        async with _agent_locks[user_id]:
            async for line in run_agent_loop(user_id, message, db=db):
                yield line
        yield _yield_line({"type": "intent", "skill_id": "RA", "skill_status": "ready"})
        return

    logging.info("Fallback chat for user %s (confidence=%.2f)", user_id, confidence)
    yield _yield_line({"type": "intent", "skill_id": "AT", "skill_status": "active"})

    # Fetch recent conversation history context for Task Memory (TM skill)
    history_msgs = []
    if db is not None:
        try:
            recent_docs = list(db.message_history.find({"user_id": user_id}).sort("timestamp", -1).limit(6))
            recent_docs.reverse()
            for doc in recent_docs:
                if doc.get("message"):
                    history_msgs.append({"role": "user", "content": doc["message"]})
                if doc.get("response"):
                    history_msgs.append({"role": "assistant", "content": doc["response"]})
        except Exception as e:
            logging.warning("Failed to fetch chat history context: %s", e)

    reply = ""
    try:
        async for delta in brain.stream_message(message, CONTROL_SYSTEM, history_msgs):
            reply += delta
            yield _yield_line({"type": "partial", "state": "thinking", "message": reply})
    except Exception as e:
        logging.error("Brain error: %s", e)
    if not reply:
        reply = "Sorry, I could not process that request right now."
    yield _yield_line({"type": "final", "state": "completed", "message": reply})
    yield _yield_line({"type": "intent", "skill_id": "AT", "skill_status": "ready"})
    _save_history(db, user_id, message, reply)


async def execute_pending_for_user(user_id: str) -> Dict[str, Any]:
    """Called from /agent/confirm when user clicks Confirm in UI."""
    pending = get_pending(user_id)
    if not pending:
        return {"executed": False, "message": "No pending action to confirm."}

    skill_id = pending.get("skill_id", "DC")
    if not ws_manager.is_connected(user_id):
        clear_pending(user_id)
        return {
            "executed": False,
            "message": AGENT_OFFLINE_MESSAGE,
            "skill_id": skill_id,
            "skill_status": "ready",
        }

    action = pop_pending(user_id)
    result = await execute_desktop_action(user_id, action)
    if result.get("success"):
        tool = action.get("tool")
        if tool == "screenshot" and result.get("result", {}).get("data"):
            base64_img = result["result"]["data"]
            user_req = action.get("user_message", "chụp màn hình")
            analysis = await _analyze_screenshot_with_vision(base64_img, user_req)
            msg = f"📸 **Phân tích màn hình:**\n\n{analysis}"
        else:
            msg = execution_message(action)
        return {
            "executed": True,
            "message": msg,
            "skill_id": skill_id,
            "skill_status": "ready",
        }
    return {
        "executed": False,
        "message": "Could not run the desktop action.",
        "skill_id": skill_id,
        "skill_status": "ready",
    }

