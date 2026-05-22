"""
Control Center chat stream: intent routing, confirmations, desktop actions.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict

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
from services.pending_actions import clear_pending, get_pending, set_pending

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
        "timestamp": datetime.datetime.utcnow(),
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
    final = execution_message(action) if result.get("success") else AGENT_OFFLINE_MESSAGE
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
            action = clear_pending(user_id)
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

    intent_result = detect_intent(message)
    action = intent_result.get("action")
    confidence = intent_result.get("confidence", 0)

    if action and confidence >= 0.7:
        async for line in _handle_desktop_intent(user_id, message, intent_result, db):
            yield line
        return

    if ws_manager.is_connected(user_id) and _should_use_agent_loop(message, intent_result):
        logging.info("Routing to agent loop for user %s", user_id)
        yield _yield_line({
            "type": "intent",
            "intent": "agent_loop",
            "skill_id": "RA",
            "skill_status": "training",
        })
        async for line in run_agent_loop(user_id, message, db=db):
            yield line
        yield _yield_line({"type": "intent", "skill_id": "RA", "skill_status": "ready"})
        return

    logging.info("Fallback chat for user %s (confidence=%.2f)", user_id, confidence)
    yield _yield_line({"type": "intent", "skill_id": "AT", "skill_status": "active"})
    try:
        reply = await asyncio.to_thread(brain.process_message, message, CONTROL_SYSTEM)
    except Exception as e:
        logging.error("Brain error: %s", e)
        reply = "Sorry, I could not process that request right now."
    async for line in _stream_text_fake(reply):
        yield line
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

    action = clear_pending(user_id)
    result = await execute_desktop_action(user_id, action)
    if result.get("success"):
        return {
            "executed": True,
            "message": execution_message(action),
            "skill_id": skill_id,
            "skill_status": "ready",
        }
    return {
        "executed": False,
        "message": "Could not run the desktop action.",
        "skill_id": skill_id,
        "skill_status": "ready",
    }
