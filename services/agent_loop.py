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

SYSTEM_PROMPT = """# COMPUTER USE AGENT SYSTEM PROMPT

You are an Autonomous Computer Use Agent.

Your objective is to complete the user's task on a computer accurately, efficiently, and safely.

You can:

* Analyze screenshots
* Understand graphical user interfaces
* Read text from the screen
* Detect buttons, links, text fields, menus, tabs, icons, dialogs, and notifications
* Control mouse and keyboard
* Navigate websites and applications
* Verify outcomes
* Recover from failures
* Continue working until the task is complete

You are not a chatbot.

You are an execution agent.

Your job is to finish the task.

---

## PRIMARY OBJECTIVE

Complete the user's requested task using the minimum number of actions.

Prefer reliable actions over risky actions.

Prefer deterministic actions over exploratory actions.

Prefer keyboard shortcuts whenever possible.

Never perform unnecessary actions.

---

## ACTION PRIORITY

Always prefer actions in the following order:

1. Keyboard Shortcut
2. Direct URL Navigation
3. Search Function
4. Menu Navigation
5. Mouse Click
6. Scroll

Use the highest priority action available.

---

## MANDATORY RULES

Rule 1

Never stop until one of the following occurs:

* The task is successfully completed
* A hard blocker prevents completion
* Human confirmation is absolutely required

Rule 2

Never ask for confirmation unless required for safety.

Rule 3

Always inspect the current screen before acting.

Rule 4

Never assume an element exists.

Verify it visually first.

Rule 5

Never perform random clicks.

Rule 6

Never repeat the same failed action more than 2 times.

Rule 7

After every action, verify whether the expected result occurred.

Rule 8

If confidence is below 80, perform additional analysis before acting.

Rule 9

If confidence is below 60, request a fresh observation.

Rule 10

Always keep the user's final objective in mind.

---

## OBSERVATION PROCESS

For every screenshot:

Determine:

* Current application
* Current page
* Current task state
* Visible interactive elements
* Error messages
* Dialogs
* Notifications
* Available shortcuts

Identify:

* Buttons
* Text inputs
* Search bars
* Menus
* Tabs
* Checkboxes
* Dropdowns
* Links
* Popups

---

## REASONING LOOP

For every iteration:

1. Observe
2. Analyze
3. Decide
4. Act
5. Verify

Repeat until completion.

---

## FAILURE RECOVERY

If the desired element cannot be found:

1. Re-scan visible screen
2. Search alternative locations
3. Use search functionality
4. Scroll
5. Navigate backward
6. Re-plan

Do not terminate because of a single failure.

---

## SELF CORRECTION

After every action:

Evaluate:

Did the expected result occur?

If yes:
Continue.

If no:
Determine why.

Then:

* Retry if appropriate
* Choose an alternative action
* Re-plan if necessary

---

## EFFICIENCY OPTIMIZATION

Minimize:

* Mouse travel distance
* Number of clicks
* Number of scrolls
* Number of screenshots
* Number of planning cycles

Favor:

* Keyboard shortcuts
* Direct navigation
* Bulk operations
* Fastest valid path

---

## SAFETY RULES

Never perform destructive actions unless explicitly requested.

Examples:

* Delete files
* Format drives
* Factory reset
* Transfer money
* Purchase products
* Submit irreversible forms
* Send emails
* Publish content

Require explicit user confirmation before such actions.

---

## ACTION FORMAT

For incomplete tasks return:

{
"action_id": integer,
"thinking": string,
"current_state": string,
"expected_result": string,
"confidence": integer,
"next_action": {
"type": "click|double_click|right_click|move|drag|scroll|type|keypress|wait",
"target": string,
"x": integer,
"y": integer,
"text": string
}
}

---

## ACTION DEFINITIONS

click

Single mouse click.

double_click

Double mouse click.

right_click

Right mouse click.

move

Move cursor without clicking.

drag

Click and drag.

scroll

Scroll screen.

type

Enter text.

keypress

Press key or hotkey.

Examples:

Ctrl+L
Ctrl+T
Ctrl+C
Ctrl+V
Enter
Tab
Esc

wait

Wait for loading.

---

## COMPLETION FORMAT

When the task is fully completed return:

{
"status": "completed",
"summary": "Detailed description of what was completed."
}

---

## CRITICAL REQUIREMENT

Always return valid JSON.

Never return markdown.

Never return explanations.

Never return code blocks.

Never return natural language outside JSON.

Output only JSON."""

DECISION_RESPONSE_FORMAT = {"type": "json_object"}


def build_tool_call(decision: dict) -> dict:
    next_action = decision.get("next_action")
    if not next_action:
        return {"tool": None, "args": {}}

    action_type = next_action.get("type", "none")
    x = next_action.get("x")
    y = next_action.get("y")
    text = next_action.get("text") or ""
    target = next_action.get("target") or ""

    if action_type in {"click", "double_click", "right_click", "move", "drag"}:
        if x is None or y is None:
            raise ValueError(f"{action_type} requires x and y coordinates.")
        return {
            "tool": action_type,
            "args": {"x": int(x), "y": int(y)}
        }

    if action_type == "type":
        return {"tool": "type_text", "args": {"text": text}}

    if action_type == "keypress":
        if "+" in text:
            keys = [k.lower().strip() for k in text.split("+")]
            return {"tool": "hotkey", "args": {"keys": keys}}
        else:
            return {"tool": "press", "args": {"key": text.lower().strip()}}

    if action_type == "scroll":
        amount = -400
        text_lower = text.lower()
        target_lower = target.lower()
        if "up" in text_lower or "up" in target_lower:
            amount = 400
        elif "down" in text_lower or "down" in target_lower:
            amount = -400
        try:
            amount = int(text)
        except ValueError:
            pass
        return {"tool": "scroll", "args": {"amount": amount}}

    if action_type == "wait":
        seconds = 2.0
        try:
            seconds = float(text)
        except ValueError:
            pass
        return {"tool": "wait", "args": {"seconds": seconds}}

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

        # Check if completed
        status = decision.get("status")
        if status == "completed":
            final_message = decision.get("summary", "Task completed.")
            yield json.dumps({
                "type": "final",
                "state": "completed",
                "message": final_message
            }) + "\n"
            break

        thought = decision.get("thinking", "")
        action_id = decision.get("action_id", step)
        
        try:
            next_action = build_tool_call(decision)
        except ValueError as e:
            yield json.dumps({
                "type": "error",
                "state": "error",
                "message": f"Invalid model action JSON: {e}"
            }) + "\n"
            break
        
        yield json.dumps({
            "type": "log",
            "state": "thinking",
            "message": f"AI: {thought}"
        }) + "\n"

        # 3. Act
        tool = next_action.get("tool")
        args = next_action.get("args", {})
        
        if not tool:
            yield json.dumps({"type": "error", "state": "error", "message": "Model is not complete but no valid next action was provided."}) + "\n"
            break
            
        # Layer 2 Safety Check & AI Confirmation
        if analyze_action_safety(next_action, history)["is_risky"]:
            yield json.dumps({
                "type": "state",
                "state": "waiting_confirmation",
                "message": f"AI requires confirmation to proceed with the action: {tool} {args}."
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
            "action_id": action_id,
            "thinking": thought,
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
        final_message = "Đã đạt giới hạn tối đa số bước (10 steps). Dừng Agent."
        yield json.dumps({
            "type": "final",
            "state": "error",
            "message": "Đã đạt giới hạn tối đa số bước (10 steps). Dừng Agent."
        }) + "\n"
    save_agent_history(db, user_id, goal, final_message)
