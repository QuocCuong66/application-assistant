import json
import logging
import asyncio
import re
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_VISION_MODEL
from api.automation import manager
from services.safety import analyze_goal_safety, analyze_action_safety

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """
You are an intelligent desktop automation AI. You can observe the user's screen and execute actions to achieve their goal.
You are given the user's goal, a history of previous actions, and an image of the current screen.
You must analyze the screen, decide the next step, and output a strict JSON object.

Allowed tools:
- click(x: int, y: int): Click at the specified coordinates.
- double_click(x: int, y: int): Double click at the specified coordinates.
- type_text(text: str): Type a string of text.
- press(key: str): Press a specific key (e.g. "enter", "tab", "esc").
- hotkey(keys: list[str]): Press a combination of keys (e.g. ["ctrl", "c"], ["win", "r"]).
- scroll(amount: int): Scroll the mouse wheel (positive for up, negative for down).
- open_app(app_name: str): Open an application by name (e.g. "chrome", "notepad").
- wait(seconds: int): Wait for a number of seconds.

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

Response JSON Schema (STRICT):
{
  "thought_summary": "Short reason for this step",
  "status": "continue | completed | need_user_confirmation | failed",
  "next_action": {
    "tool": "tool_name",
    "args": {"arg1": "value1"}
  },
  "message_to_user": "Message to show the user (if completed, failed, or need confirmation)"
}

Do NOT wrap the JSON in Markdown block quotes (like ```json), just output the raw JSON.
"""

async def run_agent_loop(user_id: str, goal: str):
    max_steps = 10
    step = 0
    history = []
    
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
            yield json.dumps({"type": "final", "state": "completed", "message": "User cancelled the risky request."}) + "\n"
            return
    
    while step < max_steps:
        if manager.stop_flags.get(user_id):
            yield json.dumps({"type": "final", "state": "error", "message": "Agent loop stopped by user."}) + "\n"
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
                max_tokens=500,
                temperature=0.0
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
        next_action = decision.get("next_action", {})
        msg_to_user = decision.get("message_to_user", "")
        
        yield json.dumps({
            "type": "log",
            "state": "thinking",
            "message": f"AI: {thought}"
        }) + "\n"
        
        if status in ["completed", "failed"]:
            yield json.dumps({
                "type": "final",
                "state": status,
                "message": msg_to_user or f"Status: {status}"
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
                yield json.dumps({"type": "final", "state": "completed", "message": "User cancelled the action."}) + "\n"
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
        
    if step >= max_steps:
        yield json.dumps({
            "type": "final",
            "state": "error",
            "message": "Đã đạt giới hạn tối đa số bước (10 steps). Dừng Agent."
        }) + "\n"
