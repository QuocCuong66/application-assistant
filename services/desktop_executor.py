"""
Execute desktop tool commands via WebSocket Desktop Agent.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from api.automation import manager as ws_manager


async def execute_desktop_action(user_id: str, action: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send tool_call to Desktop Agent and optionally wait for result.
    """
    tool = action.get("tool")
    args = action.get("args") or {}

    if not ws_manager.is_connected(user_id):
        logging.warning("Desktop Agent not connected for user %s", user_id)
        return {"success": False, "error": "agent_offline"}

    if tool == "click" and not args.get("x") and not args.get("y"):
        # Generic click without coordinates — open agent loop path instead
        return {"success": False, "error": "coordinates_required"}

    logging.info("Task queued for user %s: tool=%s args=%s", user_id, tool, args)

    if tool == "screenshot":
        result = await ws_manager.send_command_and_wait(
            user_id,
            {"type": "tool_call", "tool": "screenshot", "args": {}},
            timeout=15,
        )
        return result

    # Fire-and-forget for most actions (open_app, scroll, type_text)
    sent = await ws_manager.send_command(
        user_id,
        {"type": "tool_call", "tool": tool, "args": args},
    )
    if not sent:
        return {"success": False, "error": "send_failed"}
    return {"success": True, "queued": True, "tool": tool}
