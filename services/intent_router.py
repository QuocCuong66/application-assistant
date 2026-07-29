"""
Rule-based intent detection for Desktop Control Center chat.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

CONFIRM_PHRASES = (
    "yes", "yeah", "yep", "yup", "ok", "okay", "sure", "run", "do it",
    "go ahead", "confirm", "proceed", "execute", "start",
    "mở đi", "mo di", "làm đi", "lam di", "được", "duoc", "có", "co",
    "xác nhận", "xac nhan", "chạy đi", "chay di",
)

DECLINE_PHRASES = (
    "no", "nope", "cancel", "stop", "don't", "dont", "abort",
    "không", "khong", "hủy", "huy", "thôi", "thoi",
)


def normalize_message(message: str) -> str:
    return re.sub(r"\s+", " ", (message or "").strip().lower())


def is_confirmation(message: str) -> Optional[bool]:
    """
    Returns True if user confirms, False if declines, None if neither.
    """
    text = normalize_message(message)
    if not text:
        return None
    if text in CONFIRM_PHRASES or any(text == p or text.startswith(p + " ") for p in CONFIRM_PHRASES):
        return True
    if text in DECLINE_PHRASES or any(text == p or text.startswith(p + " ") for p in DECLINE_PHRASES):
        return False
    if re.match(r"^(yes|ok|sure|run|confirm|mở|mo|làm|lam|được|duoc)\b", text):
        return True
    if re.match(r"^(no|cancel|không|khong|hủy|huy)\b", text):
        return False
    return None


def skill_id_for_tool(tool: str, intent: str = "") -> str:
    mapping = {
        "open_app": "DC",
        "click": "DC",
        "type_text": "DC",
        "scroll": "DC",
        "screenshot": "SA",
        "search_web": "WA",
    }
    if intent == "agent_loop":
        return "RA"
    return mapping.get(tool, "DC")


import urllib.parse

def _open_app_intent(message: str) -> Optional[Tuple[str, float, Dict[str, Any]]]:
    apps: List[Tuple[str, str, float]] = [
        (r"(google\s+)?chrome|trình duyệt chrome|browser chrome", "chrome", 0.92),
        (r"edge|microsoft edge", "msedge", 0.9),
        (r"firefox", "firefox", 0.9),
        (r"notepad|ghi chú", "notepad", 0.9),
        (r"calculator|máy tính(?!\s+tính)", "calc", 0.88),
        (r"explorer|file explorer|thư mục|folder", "explorer", 0.85),
        (r"cmd|command prompt|trình điều khiển cmd", "cmd", 0.88),
        (r"powershell", "powershell", 0.88),
        (r"vscode|vs code|visual studio code", "vscode", 0.9),
        (r"word|microsoft word", "word", 0.88),
        (r"excel|microsoft excel", "excel", 0.88),
        (r"zalo", "zalo", 0.9),
        (r"spotify", "spotify", 0.88),
    ]
    open_verbs = r"(open|launch|start|run|m[oở]|khởi chạy|help me open|can you open|please open)"
    for pattern, app_name, conf in apps:
        if re.search(rf"{open_verbs}.{{0,40}}{pattern}", message, re.I):
            return app_name, conf, {"app_name": app_name}
        if re.search(rf"{pattern}.{{0,30}}{open_verbs}", message, re.I):
            return app_name, conf * 0.95, {"app_name": app_name}
    if re.search(rf"{open_verbs}.{{0,30}}(app|application|ứng dụng)", message, re.I):
        return "app", 0.55, {"app_name": "app"}
    return None


def detect_intent(message: str) -> Dict[str, Any]:
    """
    Detect desktop-control intent from a user message.

    Returns:
        {
            "intent": str,
            "confidence": float,
            "action": { type, tool, args, requires_confirmation, skill_id, label },
            "skill_id": str,
        }
        or low-confidence fallback with intent "chat".
    """
    raw = (message or "").strip()
    text = normalize_message(raw)

    if not text:
        return {"intent": "chat", "confidence": 0.0, "action": None, "skill_id": None}

    # --- open application ---
    open_match = _open_app_intent(text)
    if open_match:
        app_name, confidence, args = open_match
        display = "Google Chrome" if app_name == "chrome" else app_name.replace("_", " ").title()
        return {
            "intent": "open_app",
            "confidence": confidence,
            "skill_id": "DC",
            "action": {
                "type": "desktop_action",
                "tool": "open_app",
                "args": args,
                "requires_confirmation": True,
                "skill_id": "DC",
                "label": display,
                "user_message": raw,
            },
        }

    # --- screenshot ---
    if re.search(r"(screenshot|screen shot|chụp màn hình|chup man hinh|capture screen)", text, re.I):
        return {
            "intent": "screenshot",
            "confidence": 0.9,
            "skill_id": "SA",
            "action": {
                "type": "desktop_action",
                "tool": "screenshot",
                "args": {},
                "requires_confirmation": True,
                "skill_id": "SA",
                "label": "screenshot",
                "user_message": raw,
            },
        }

    # --- scroll ---
    if re.search(r"\b(scroll|cuộn|cuon)\b", text, re.I):
        amount = -400 if re.search(r"(down|xuống|xuong)", text, re.I) else 400
        return {
            "intent": "scroll",
            "confidence": 0.82,
            "skill_id": "DC",
            "action": {
                "type": "desktop_action",
                "tool": "scroll",
                "args": {"amount": amount},
                "requires_confirmation": True,
                "skill_id": "DC",
                "label": "scroll",
                "user_message": raw,
            },
        }

    # --- type text ---
    type_match = re.search(
        r"(type|gõ|go|nhập|nhap|enter text)\s+['\"]?(.+?)['\"]?\s*$",
        raw,
        re.I,
    )
    if type_match:
        typed = type_match.group(2).strip()
        if typed:
            return {
                "intent": "type_text",
                "confidence": 0.85,
                "skill_id": "DC",
                "action": {
                    "type": "desktop_action",
                    "tool": "type_text",
                    "args": {"text": typed},
                    "requires_confirmation": True,
                    "skill_id": "DC",
                    "label": "type text",
                    "user_message": raw,
                },
            }

    # --- click (generic — needs confirmation) ---
    if re.search(r"\b(click|bấm|bam|nhấn|nhan)\b", text, re.I):
        return {
            "intent": "click",
            "confidence": 0.7,
            "skill_id": "DC",
            "action": {
                "type": "desktop_action",
                "tool": "click",
                "args": {},
                "requires_confirmation": True,
                "skill_id": "DC",
                "label": "click",
                "user_message": raw,
                "note": "coordinates_required",
            },
        }

    # --- web search ---
    if re.search(r"(search web|google search|tìm trên web|tim tren web|search for|tìm kiếm)", text, re.I):
        query_match = re.search(r"(?:search for|search web for|google search|tìm kiếm|tìm trên web|tim tren web|tìm|tim)\s+(.+)", raw, re.I)
        query = query_match.group(1).strip() if query_match else raw
        search_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        return {
            "intent": "search_web",
            "confidence": 0.85,
            "skill_id": "WA",
            "action": {
                "type": "desktop_action",
                "tool": "open_app",
                "args": {"app_name": "chrome", "url": search_url, "query": query},
                "requires_confirmation": True,
                "skill_id": "WA",
                "label": f"Web search '{query}'",
                "user_message": raw,
                "search_query": query,
            },
        }

    # --- multi-step automation goals → agent loop ---
    automation_cues = (
        "automate", "fill form", "complete task", "do this for me",
        "navigate to", "find the button", "reason and act",
    )
    if any(cue in text for cue in automation_cues):
        return {
            "intent": "agent_loop",
            "confidence": 0.75,
            "skill_id": "RA",
            "action": None,
        }

    return {"intent": "chat", "confidence": 0.0, "action": None, "skill_id": None}


def confirmation_prompt(action: Dict[str, Any]) -> str:
    tool = action.get("tool")
    label = action.get("label") or tool
    args = action.get("args") or {}

    if tool == "open_app":
        app = args.get("app_name", "the app")
        name = "Google Chrome" if app == "chrome" else str(app).title()
        if args.get("query"):
            return f"I can search Google for '{args['query']}' in {name}. Do you want me to run it now?"
        return f"I can open {name} for you. Do you want me to run it now?"
    if tool == "screenshot":
        return "I can capture a screenshot and analyze it for you. Do you want me to run it now?"
    if tool == "scroll":
        return "I can scroll the active window for you. Do you want me to run it now?"
    if tool == "type_text":
        return "I can type that text on your desktop. Do you want me to run it now?"
    if tool == "click":
        return "I can perform a click action. Do you want me to run it now?"
    return f"I can run {label} for you. Do you want me to run it now?"


def execution_message(action: Dict[str, Any]) -> str:
    tool = action.get("tool")
    args = action.get("args") or {}

    if tool == "open_app":
        app = args.get("app_name", "app")
        name = "Google Chrome" if app == "chrome" else str(app).title()
        if args.get("query"):
            return f"Searching Google for '{args['query']}' in {name}…"
        return f"Opening {name} now…"
    if tool == "screenshot":
        return "Capturing screenshot and analyzing screen…"
    if tool == "scroll":
        return "Scrolling now…"
    if tool == "type_text":
        return "Typing on your desktop now…"
    if tool == "click":
        return "Sending click command now…"
    return "Running the desktop action now…"


AGENT_OFFLINE_MESSAGE = (
    "Desktop Agent is not connected. Please start desktop_agent.py, then I can run this for you."
)

