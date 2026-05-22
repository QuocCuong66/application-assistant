"""
In-memory pending desktop actions per user (session).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

_pending: Dict[str, Dict[str, Any]] = {}


def set_pending(user_id: str, action: Dict[str, Any]) -> None:
    _pending[user_id] = action
    logging.info("Pending action set for user %s: tool=%s", user_id, action.get("tool"))


def get_pending(user_id: str) -> Optional[Dict[str, Any]]:
    return _pending.get(user_id)


def clear_pending(user_id: str) -> None:
    if user_id in _pending:
        del _pending[user_id]
        logging.info("Pending action cleared for user %s", user_id)


def pop_pending(user_id: str) -> Optional[Dict[str, Any]]:
    action = _pending.pop(user_id, None)
    if action:
        logging.info("Pending action popped for user %s: tool=%s", user_id, action.get("tool"))
    return action
