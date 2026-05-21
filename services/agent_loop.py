import json
import logging
import asyncio
import re
import datetime
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_VISION_MODEL
from api.automation import manager
from services.safety import analyze_goal_safety, analyze_action_safety

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """
You are an intelligent desktop automation AI. You can observe the user's screen and execute actions to achieve their goal.
You are given the user's goal, previous actions, and a fresh screenshot on every step.
Analyze the current screen and choose exactly one next action. Output only the JSON object required by the response schema.

Allowed actions:
- click: use coordinates [x, y] for the center of the target.
- double_click: use coordinates [x, y] for the center of the target.
- type_text: use text.
- press: use key, e.g. "enter", "tab", "esc".
- hotkey: use keys, e.g. ["ctrl", "c"], ["win", "r"].
- scroll: use amount, positive for up and negative for down.
- open_app: use app_name, e.g. "chrome", "notepad".
- wait: use seconds.
- none: use only when completed, failed, or waiting for user confirmation.

Safety Protocol:
If the user's goal or the current step involves ANY of the following dangerous actions, you MUST set status to "need_user_confirmation":
- Sending an email
- Deleting files
- Transferring money
- Making a purchase
- Making a public post
- Submitting an important form
- Entering passwords/tokens/API keys
- Installing software
- Changing system settings

Coordinate rules:
- Use the screenshot coordinate system.
- If unsure, prefer wait or ask for confirmation instead of clicking randomly.
- For completed or failed status, set action to "none".
"""

DECISION_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "desktop_agent_decision",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "thought_summary": {"type": "string"},
                "status": {
                    "type": "string",
                    "enum": ["continue", "completed", "need_user_confirmation", "failed"]
                },
                "action": {
                    "type": "string",
                    "enum": ["click", "double_click", "type_text", "press", "hotkey", "scroll", "open_app", "wait", "none"]
                },
                "target": {"type": ["string", "null"]},
                "coordinates": {
                    "anyOf": [
                        {
                            "type": "array",
                            "items": {"type": "number"}
                        },
                        {"type": "null"}
                    ]
                },
                "text": {"type": ["string", "null"]},
                "key": {"type": ["string", "null"]},
                "keys": {
                    "anyOf": [
                        {"type": "array", "items": {"type": "string"}},
                        {"type": "null"}
                    ]
                },
                "amount": {"type": ["integer", "null"]},
                "app_name": {"type": ["string", "null"]},
                "seconds": {"type": ["number", "null"]},
                "message_to_user": {"type": "string"}
            },
            "required": [
                "thought_summary",
                "status",
                "action",
                "target",
                "coordinates",
                "text",
                "key",
                "keys",
                "amount",
                "app_name",
                "seconds",
                "message_to_user"
            ]
        }
    }
}


def build_tool_call(decision: dict) -> dict:
    action = decision.get("action", "none")
    coordinates = decision.get("coordinates")

    if action in {"click", "double_click"}:
        if not isinstance(coordinates, list) or len(coordinates) != 2:
            raise ValueError(f"{action} requires coordinates [x, y].")
        return {
            "tool": action,
            "args": {"x": int(coordinates[0]), "y": int(coordinates[1])}
        }

    if action == "type_text":
        return {"tool": action, "args": {"text": decision.get("text") or ""}}

    if action == "press":
        key = decision.get("key")
        if not key:
            raise ValueError("press requires key.")
        return {"tool": action, "args": {"key": key}}

    if action == "hotkey":
        keys = decision.get("keys")
        if not isinstance(keys, list) or not keys:
            raise ValueError("hotkey requires a non-empty keys array.")
        return {"tool": action, "args": {"keys": keys}}

    if action == "scroll":
        amount = decision.get("amount")
        if amount is None:
            raise ValueError("scroll requires amount.")
        return {"tool": action, "args": {"amount": int(amount)}}

    if action == "open_app":
        app_name = decision.get("app_name")
        if not app_name:
            raise ValueError("open_app requires app_name.")
        return {"tool": action, "args": {"app_name": app_name}}

    if action == "wait":
        return {"tool": action, "args": {"seconds": float(decision.get("seconds") or 1)}}

    return {"tool": None, "args": {}}


def save_agent_history(db, user_id: str, goal: str, response: str):
    if db is None or not response:
        return

    db.message_history.insert_one({
        "user_id": user_id,
        "message": goal,
        "response": response,
        "timestamp": datetime.datetime.utcnow()
    })


async def run_agent_loop(user_id: str, goal: str, db=None):
    max_steps = 10
    step = 0
    history = []
    final_message = ""
    
    yield json.dumps({
        "type": "log",
        "state": "thinking",
        "message": f"Goal: {goal}"
    }) + "\n"

    # Layer 1 Safety Check
    goal_safety = analyze_goal_safety(goal)
    if goal_safety["is_risky"]:
        yield json.dumps({
            "type": "state",
            "state": "waiting_confirmation",
            "message": goal_safety["reason"]
        }) + "\n"

        manager.user_events[user_id] = asyncio.Event()
        try:
            await asyncio.wait_for(manager.user_events[user_id].wait(), timeout=60.0)
            result = manager.user_confirm_results.get(user_id, 'cancel')
        except asyncio.TimeoutError:
            result = 'cancel'
            yield json.dumps({"type": "error", "state": "error", "message": "Confirmation timeout. Agent stopped."}) + "\n"
        
        if user_id in manager.user_events:
            del manager.user_events[user_id]
            
        if result == 'cancel':
            final_message = "User cancelled the risky request."
            yield json.dumps({"type": "final", "state": "completed", "message": final_message}) + "\n"
            save_agent_history(db, user_id, goal, final_message)
            return
    
    while step < max_steps:
        if manager.stop_flags.get(user_id):
            final_message = "Agent loop stopped by user."
            yield json.dumps({"type": "final", "state": "error", "message": final_message}) + "\n"
            break
            
        step += 1
        
        # 1. Observe (Get Screenshot)
        yield json.dumps({
            "type": "state",
            "state": "observing",
            "message": f"Step {step}: Quan sát màn hình..."
        }) + "\n"
        
        screenshot_result = await manager.send_command_and_wait(user_id, {"type": "tool_call", "tool": "screenshot", "args": {}}, timeout=10)
        
        if not screenshot_result.get("success"):
            yield json.dumps({
                "type": "error",
                "state": "error",
                "message": f"Lỗi lấy ảnh màn hình: {screenshot_result.get('error')}"
            }) + "\n"
            break
            
        screenshot_base64 = screenshot_result.get("result", {}).get("data")
        if not screenshot_base64:
            yield json.dumps({
                "type": "error",
                "state": "error",
                "message": "Không nhận được dữ liệu ảnh màn hình."
            }) + "\n"
            break

        # 2. Think (Call AI)
        yield json.dumps({
            "type": "state",
            "state": "thinking",
            "message": "AI đang phân tích và quyết định..."
        }) + "\n"
        
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": f"User Goal: {goal}\nAction History:\n{json.dumps(history, indent=2)}\n\nWhat is the next action?"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_base64}", "detail": "high"}}
            ]}
        ]
        
        try:
            # Note: We must await this using asyncio.to_thread if openai library is sync, 
            # or use AsyncOpenAI. Using to_thread for simplicity with the sync client.
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=OPENAI_VISION_MODEL,
                messages=messages,
                max_tokens=700,
                temperature=0.0,
                response_format=DECISION_RESPONSE_FORMAT
            )
            ai_text = response.choices[0].message.content.strip()
            # Clean possible markdown wrap more robustly
            json_match = re.search(r'```(?:json)?(.*?)```', ai_text, re.DOTALL)
            if json_match:
                ai_text = json_match.group(1).strip()
            elif ai_text.startswith("{") and ai_text.endswith("}"):
                pass # it's likely json already
            else:
                # If neither, try to parse anyway or fail
                pass
                
            decision = json.loads(ai_text)
        except Exception as e:
            logging.error(f"Error calling OpenAI: {e}")
            yield json.dumps({
                "type": "error",
                "state": "error",
                "message": f"Lỗi AI: {e}"
            }) + "\n"
            break

        thought = decision.get("thought_summary", "")
        status = decision.get("status", "failed")
        try:
            next_action = build_tool_call(decision)
        except ValueError as e:
            yield json.dumps({
                "type": "error",
                "state": "error",
                "message": f"Invalid model action JSON: {e}"
            }) + "\n"
            break
        msg_to_user = decision.get("message_to_user", "")
        
        yield json.dumps({
            "type": "log",
            "state": "thinking",
            "message": f"AI: {thought}"
        }) + "\n"
        
        if status in ["completed", "failed"]:
            final_message = msg_to_user or f"Status: {status}"
            yield json.dumps({
                "type": "final",
                "state": status,
                "message": final_message
            }) + "\n"
            break

        # 3. Act
        tool = next_action.get("tool")
        args = next_action.get("args", {})
        
        if not tool and status == "continue":
            yield json.dumps({"type": "error", "state": "error", "message": "Model status is continue but no tool was provided."}) + "\n"
            break
            
        # Layer 2 Safety Check & AI Confirmation
        if status == "need_user_confirmation" or analyze_action_safety(next_action, history)["is_risky"]:
            yield json.dumps({
                "type": "state",
                "state": "waiting_confirmation",
                "message": msg_to_user or "AI requires confirmation to proceed with the next action."
            }) + "\n"
            
            manager.user_events[user_id] = asyncio.Event()
            try:
                await asyncio.wait_for(manager.user_events[user_id].wait(), timeout=60.0)
                confirm_res = manager.user_confirm_results.get(user_id, 'cancel')
            except asyncio.TimeoutError:
                confirm_res = 'cancel'
                yield json.dumps({"type": "error", "state": "error", "message": "Confirmation timeout. Agent stopped."}) + "\n"
            
            if user_id in manager.user_events:
                del manager.user_events[user_id]
                
            if confirm_res == 'cancel':
                final_message = "User cancelled the action."
                yield json.dumps({"type": "final", "state": "completed", "message": final_message}) + "\n"
                break
        
        yield json.dumps({
            "type": "state",
            "state": "acting",
            "message": f"Thực thi {tool}..."
        }) + "\n"
        
        tool_result = await manager.send_command_and_wait(user_id, {
            "type": "tool_call",
            "tool": tool,
            "args": args
        }, timeout=15)
        
        if not tool_result.get("success"):
            yield json.dumps({
                "type": "error",
                "state": "error",
                "message": f"Lỗi thực thi {tool}: {tool_result.get('error')}"
            }) + "\n"
            break
            
        history.append({
            "step": step,
            "thought": thought,
            "action": tool,
            "args": args,
            "result": tool_result.get("result") or tool_result.get("error")
        })
        
        # Trim history to max 5 items
        if len(history) > 5:
            history = history[-5:]
        
        # Small delay to let UI breathe
        await asyncio.sleep(1)
        
    if step >= max_steps and not final_message:
        final_message = "Da dat gioi han toi da so buoc (10 steps). Dung Agent."
        yield json.dumps({
            "type": "final",
            "state": "error",
            "message": "Đã đạt giới hạn tối đa số bước (10 steps). Dừng Agent."
        }) + "\n"
    save_agent_history(db, user_id, goal, final_message)
