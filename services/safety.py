import re
import logging

# Simple regex-based safety checks for Layer 1
RISKY_KEYWORDS = [
    r"xóa", r"delete", r"remove", r"format", r"uninstall",
    r"chuyển tiền", r"transfer", r"pay ", r"mua", r"buy", r"checkout",
    r"gửi email", r"send email",
    r"đăng bài", r"post", r"publish", r"tweet",
    r"mật khẩu", r"password", r"token", r"api key",
    r"cài đặt", r"install", r"setup", r"setting"
]

def analyze_goal_safety(goal: str) -> dict:
    """Layer 1: Check the overall user goal for risky intentions."""
    goal_lower = goal.lower()
    
    for pattern in RISKY_KEYWORDS:
        if re.search(pattern, goal_lower):
            return {
                "is_risky": True,
                "reason": f"Mục tiêu chứa từ khóa nhạy cảm ({pattern}). Cần xác nhận trước khi thực hiện."
            }
            
    return {"is_risky": False, "reason": ""}

def analyze_action_safety(action: dict, history: list) -> dict:
    """Layer 2: Check the specific action outputted by the LLM."""
    tool = action.get("tool")
    args = action.get("args", {})
    
    # We could do more advanced checks here, but for now we flag risky tool arguments
    if tool == "type_text":
        text = args.get("text", "").lower()
        if re.search(r"password|mật khẩu", text):
            return {"is_risky": True, "reason": "Phát hiện hành động nhập mật khẩu/thông tin nhạy cảm."}
            
    if tool == "press" or tool == "hotkey":
        # e.g., pressing enter on a delete confirmation dialog
        pass

    return {"is_risky": False, "reason": ""}
