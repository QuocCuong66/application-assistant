"""
Computer Use Agent Loop — Observe → Plan → Act → Verify

This module contains the core agent loop that drives desktop automation.
It captures screenshots, sends them to GPT-4o for analysis, parses the
structured JSON response, executes exactly one action per iteration,
and feeds the result back into the next iteration.

Risk mitigations implemented:
  R1  — Same-action loop detection via AgentMemory
  R2  — Wait-stall detection via AgentMemory
  R5  — Screenshot base64 never stored in history
  R6  — Prompt length bounded via summary rotation
  R7  — Failure budget (max 5 per session)
  R9  — JSON validation with structured re-ask
  R10 — Per-user concurrency lock (in control_center_chat.py)
  R13 — Coordinate scaling from thumbnail → screen space
"""
import json
import logging
import asyncio
import re
import datetime
from typing import Dict, Any, Optional

from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_VISION_MODEL
from api.automation import manager
from services.safety import analyze_goal_safety, analyze_action_safety
from services.agent_memory import AgentMemory
from services.prompt_builder import build_system_prompt, build_user_message

client = OpenAI(api_key=OPENAI_API_KEY)


# ======================================================================
# Coordinate Scaling  (mitigates R13)
# ======================================================================

def scale_coordinates(
    x: int,
    y: int,
    memory: AgentMemory,
) -> tuple[int, int]:
    """Scale AI coordinates from thumbnail space to native screen space.

    The AI sees a resized screenshot (e.g. 1280×720) but pyautogui
    operates in native screen resolution (e.g. 1920×1080).
    """
    tw = memory.screenshot_dimensions.get("width", 0)
    th = memory.screenshot_dimensions.get("height", 0)
    sw = memory.screen_resolution.get("width", 0)
    sh = memory.screen_resolution.get("height", 0)

    if tw <= 0 or th <= 0 or sw <= 0 or sh <= 0:
        logging.warning(
            "Cannot scale coordinates — missing dimensions: "
            "thumb=(%s,%s) screen=(%s,%s). Using raw coords.",
            tw, th, sw, sh,
        )
        return int(x), int(y)

    scale_x = sw / tw
    scale_y = sh / th
    return int(x * scale_x), int(y * scale_y)


# ======================================================================
# Tool Call Builder  (new schema)
# ======================================================================

def build_tool_call_v2(
    decision: dict,
    memory: AgentMemory,
) -> Dict[str, Any]:
    """Map the AI's action JSON to a desktop-agent tool_call command.

    Returns {"tool": str, "args": dict} or raises ValueError.
    """
    action = decision.get("action")
    if not action:
        raise ValueError("Decision has status 'action_needed' but no 'action' field.")

    atype = action.get("type", "").strip().lower()
    params = action.get("parameters") or {}

    if not atype:
        raise ValueError("action.type is empty.")

    # --- Click family: scale coordinates ---
    if atype in ("click", "double_click", "right_click"):
        raw_x = params.get("x")
        raw_y = params.get("y")
        if raw_x is None or raw_y is None:
            raise ValueError(f"{atype} requires x and y coordinates.")
        real_x, real_y = scale_coordinates(int(raw_x), int(raw_y), memory)
        return {"tool": atype, "args": {"x": real_x, "y": real_y}}

    if atype == "type_text":
        text = params.get("text", "")
        if not text:
            raise ValueError("type_text requires non-empty 'text' parameter.")
        return {"tool": "type_text", "args": {"text": text}}

    if atype == "press_key":
        key = params.get("key", "").strip().lower()
        if not key:
            raise ValueError("press_key requires 'key' parameter.")
        return {"tool": "press", "args": {"key": key}}

    if atype == "hotkey":
        keys = params.get("keys", [])
        if not isinstance(keys, list) or len(keys) == 0:
            raise ValueError("hotkey requires non-empty 'keys' list.")
        return {"tool": "hotkey", "args": {"keys": [k.lower().strip() for k in keys]}}

    if atype == "scroll":
        direction = params.get("direction", "down").lower()
        amount = int(params.get("amount", 3))
        # pyautogui: positive = up, negative = down
        scroll_val = amount * 120 if direction == "up" else -(amount * 120)
        return {"tool": "scroll", "args": {"amount": scroll_val}}

    if atype == "wait":
        seconds = float(params.get("seconds", 2))
        seconds = min(seconds, 5.0)  # cap wait
        return {"tool": "wait", "args": {"seconds": seconds}}

    if atype == "open_app":
        app_name = params.get("app_name", "").strip()
        if not app_name:
            raise ValueError("open_app requires 'app_name' parameter.")
        return {"tool": "open_app", "args": {"app_name": app_name}}

    raise ValueError(f"Unknown action type: '{atype}'")


# ======================================================================
# AI Response Parser  (mitigates R9)
# ======================================================================

def parse_ai_response(ai_text: str) -> dict:
    """Parse and validate the AI's JSON response.

    Strips markdown wrappers, parses JSON, validates required fields.
    Raises ValueError with a descriptive message on failure.
    """
    text = ai_text.strip()

    # Strip markdown code fences
    md_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if md_match:
        text = md_match.group(1).strip()

    try:
        decision = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON from AI: {e}. Raw text: {text[:200]}")

    if not isinstance(decision, dict):
        raise ValueError(f"Expected JSON object, got {type(decision).__name__}")

    status = decision.get("status")
    if status not in ("action_needed", "completed", "blocked"):
        raise ValueError(
            f"Invalid status '{status}'. Must be 'action_needed', 'completed', or 'blocked'."
        )

    if status == "action_needed":
        action = decision.get("action")
        if not action or not isinstance(action, dict):
            raise ValueError("status is 'action_needed' but 'action' is missing or not an object.")
        if not action.get("type"):
            raise ValueError("action.type is required when status is 'action_needed'.")

    return decision


# ======================================================================
# History Helper
# ======================================================================

def save_agent_history(db, user_id: str, goal: str, response: str):
    if db is None or not response:
        return
    db.message_history.insert_one({
        "user_id": user_id,
        "message": goal,
        "response": response,
        "timestamp": datetime.datetime.now(datetime.timezone.utc),
    })


# ======================================================================
# Main Agent Loop
# ======================================================================

async def run_agent_loop(user_id: str, goal: str, db=None):
    """Observe → Plan → Act → Verify loop.

    Yields NDJSON lines for the frontend to consume via StreamingResponse.
    """
    max_steps = 15
    memory = AgentMemory(goal, max_steps=max_steps)
    final_message = ""
    json_error_retries = 0
    MAX_JSON_RETRIES = 2

    yield json.dumps({
        "type": "log",
        "state": "thinking",
        "message": f"Goal: {goal}",
    }) + "\n"

    # --- Layer 1: Safety check on the goal ---
    goal_safety = analyze_goal_safety(goal)
    if goal_safety["is_risky"]:
        yield json.dumps({
            "type": "state",
            "state": "waiting_confirmation",
            "message": goal_safety["reason"],
        }) + "\n"

        manager.user_events[user_id] = asyncio.Event()
        try:
            await asyncio.wait_for(
                manager.user_events[user_id].wait(), timeout=60.0,
            )
            result = manager.user_confirm_results.get(user_id, "cancel")
        except asyncio.TimeoutError:
            result = "cancel"
            yield json.dumps({
                "type": "error",
                "state": "error",
                "message": "Confirmation timeout. Agent stopped.",
            }) + "\n"

        if user_id in manager.user_events:
            del manager.user_events[user_id]

        if result == "cancel":
            final_message = "User cancelled the risky request."
            yield json.dumps({
                "type": "final",
                "state": "completed",
                "message": final_message,
            }) + "\n"
            save_agent_history(db, user_id, goal, final_message)
            return

    # --- Main loop ---
    step = 0
    while step < max_steps:
        # Check stop flag
        if manager.stop_flags.get(user_id):
            final_message = "Agent loop stopped by user."
            yield json.dumps({
                "type": "final",
                "state": "error",
                "message": final_message,
            }) + "\n"
            break

        # Check failure budget (mitigates R7)
        if memory.is_budget_exceeded():
            final_message = (
                f"Too many failures ({memory.total_failures}). "
                f"Agent stopped. Last error: {memory.last_error}"
            )
            yield json.dumps({
                "type": "final",
                "state": "error",
                "message": final_message,
            }) + "\n"
            break

        step += 1
        memory.current_step = step

        # ==============================================================
        # OBSERVE — capture screenshot
        # ==============================================================
        yield json.dumps({
            "type": "state",
            "state": "observing",
            "message": f"Step {step}/{max_steps}: Capturing screenshot…",
        }) + "\n"

        screenshot_result = await manager.send_command_and_wait(
            user_id,
            {"type": "tool_call", "tool": "screenshot", "args": {}},
            timeout=15,
        )

        if not screenshot_result.get("success"):
            err = screenshot_result.get("error", "Unknown")
            memory.record_failure(f"Screenshot failed: {err}")
            yield json.dumps({
                "type": "error",
                "state": "error",
                "message": f"Screenshot error: {err}",
            }) + "\n"
            if err in ("Agent offline", "Timeout"):
                final_message = f"Desktop Agent unreachable: {err}"
                yield json.dumps({
                    "type": "final",
                    "state": "error",
                    "message": final_message,
                }) + "\n"
                break
            # Non-fatal screenshot error → continue to next step
            await asyncio.sleep(2)
            continue

        result_data = screenshot_result.get("result", {})
        screenshot_base64 = result_data.get("data")
        thumb_size = result_data.get("size", (0, 0))
        original_size = result_data.get("original_size", thumb_size)

        if not screenshot_base64:
            memory.record_failure("Empty screenshot data")
            yield json.dumps({
                "type": "error",
                "state": "error",
                "message": "Empty screenshot data received.",
            }) + "\n"
            continue

        # Store screen info for coordinate scaling (mitigates R13)
        if isinstance(original_size, (list, tuple)) and len(original_size) >= 2:
            memory.set_screen_info(
                resolution={"width": int(original_size[0]), "height": int(original_size[1])},
                thumbnail_size={"width": int(thumb_size[0]), "height": int(thumb_size[1])},
            )

        # Stale-screen detection (mitigates R1, R2)
        memory.update_screenshot_hash(screenshot_base64)

        # ==============================================================
        # PLAN — call AI with screenshot + memory
        # ==============================================================
        yield json.dumps({
            "type": "state",
            "state": "thinking",
            "message": "AI analysing screenshot…",
        }) + "\n"

        error_context = None
        if memory.should_force_replan():
            error_context = (
                "WARNING: You appear stuck. Your recent actions had no effect. "
                "Try a completely different approach."
            )

        system_prompt = build_system_prompt()
        user_text = build_user_message(goal, memory, error_context)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [
                {"type": "text", "text": user_text},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{screenshot_base64}",
                        "detail": "high",
                    },
                },
            ]},
        ]

        try:
            from config import GEMINI_API_KEY, GEMINI_MODEL
            if GEMINI_API_KEY:
                loop_client = OpenAI(
                    api_key=GEMINI_API_KEY,
                    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
                )
                loop_model = GEMINI_MODEL or "gemini-2.5-flash"
            else:
                loop_client = client
                loop_model = OPENAI_VISION_MODEL or "gpt-4o"

            response = await asyncio.to_thread(
                loop_client.chat.completions.create,
                model=loop_model,
                messages=messages,
                max_tokens=700,
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            ai_text = response.choices[0].message.content.strip()
        except Exception as e:
            logging.error("OpenAI API error: %s", e)
            memory.record_failure(f"OpenAI error: {e}")
            yield json.dumps({
                "type": "error",
                "state": "error",
                "message": f"AI error: {e}",
            }) + "\n"
            await asyncio.sleep(2)
            continue

        # --- Parse AI response (mitigates R9) ---
        try:
            decision = parse_ai_response(ai_text)
            json_error_retries = 0  # reset on success
        except ValueError as e:
            json_error_retries += 1
            logging.warning("AI response parse error (attempt %d): %s", json_error_retries, e)
            memory.record_failure(f"Invalid AI response: {e}")

            if json_error_retries >= MAX_JSON_RETRIES:
                yield json.dumps({
                    "type": "error",
                    "state": "error",
                    "message": f"AI returned invalid JSON {MAX_JSON_RETRIES} times. Stopping.",
                }) + "\n"
                final_message = "AI consistently returned invalid responses."
                break

            yield json.dumps({
                "type": "log",
                "state": "thinking",
                "message": f"AI response invalid, retrying… ({json_error_retries}/{MAX_JSON_RETRIES})",
            }) + "\n"
            continue

        # ==============================================================
        # CHECK COMPLETION
        # ==============================================================
        status = decision.get("status")
        observation = decision.get("observation", "")
        reasoning = decision.get("reasoning", "")

        if status == "completed":
            final_message = (
                f"✅ Task completed.\n"
                f"Observation: {observation}\n"
                f"Reasoning: {reasoning}"
            )
            yield json.dumps({
                "type": "final",
                "state": "completed",
                "message": final_message,
            }) + "\n"
            break

        if status == "blocked":
            final_message = (
                f"⚠️ Task blocked.\n"
                f"Observation: {observation}\n"
                f"Reasoning: {reasoning}"
            )
            yield json.dumps({
                "type": "final",
                "state": "error",
                "message": final_message,
            }) + "\n"
            break

        # --- Log the AI's thinking ---
        yield json.dumps({
            "type": "log",
            "state": "thinking",
            "message": f"AI: {reasoning[:200]}",
        }) + "\n"

        # ==============================================================
        # ACT — build tool call and execute
        # ==============================================================
        action_dict = decision.get("action", {})
        expected_result = decision.get("expected_result", "")

        try:
            tool_call = build_tool_call_v2(decision, memory)
        except ValueError as e:
            memory.record_failure(f"Invalid action: {e}")
            yield json.dumps({
                "type": "error",
                "state": "error",
                "message": f"Invalid action from AI: {e}",
            }) + "\n"
            continue  # Don't break — let AI re-plan on next iteration

        tool = tool_call["tool"]
        args = tool_call["args"]

        # --- Layer 2: Safety check on the action ---
        safety_result = analyze_action_safety(tool_call, memory.completed_steps)
        if safety_result["is_risky"]:
            yield json.dumps({
                "type": "state",
                "state": "waiting_confirmation",
                "message": f"Safety check: {safety_result['reason']}",
            }) + "\n"

            manager.user_events[user_id] = asyncio.Event()
            try:
                await asyncio.wait_for(
                    manager.user_events[user_id].wait(), timeout=60.0,
                )
                confirm_res = manager.user_confirm_results.get(user_id, "cancel")
            except asyncio.TimeoutError:
                confirm_res = "cancel"
                yield json.dumps({
                    "type": "error",
                    "state": "error",
                    "message": "Confirmation timeout. Agent stopped.",
                }) + "\n"

            if user_id in manager.user_events:
                del manager.user_events[user_id]

            if confirm_res == "cancel":
                final_message = "User cancelled the action."
                yield json.dumps({
                    "type": "final",
                    "state": "completed",
                    "message": final_message,
                }) + "\n"
                break

        # --- Execute the action ---
        yield json.dumps({
            "type": "state",
            "state": "acting",
            "message": f"Executing: {tool} {args}",
        }) + "\n"

        tool_result = await manager.send_command_and_wait(
            user_id,
            {"type": "tool_call", "tool": tool, "args": args},
            timeout=15,
        )

        # ==============================================================
        # VERIFY — record result, update tracking
        # ==============================================================
        if tool_result.get("success"):
            result_status = "success"
        else:
            result_status = f"failed: {tool_result.get('error', 'unknown')}"
            memory.record_failure(result_status)
            yield json.dumps({
                "type": "log",
                "state": "thinking",
                "message": f"Action failed: {result_status}. AI will re-plan.",
            }) + "\n"
            # Do NOT break — feed failure context into next AI call

        # Record step in memory (never stores screenshot base64 — mitigates R5)
        memory.record_step(
            step_num=step,
            action=action_dict,
            observation=observation,
            result=result_status,
            expected=expected_result,
        )

        # Track repetitive actions (mitigates R1)
        memory.update_action_tracking(action_dict)
        memory.last_expected_result = expected_result

        # Let the UI settle before next screenshot
        await asyncio.sleep(1.5)

    # --- Loop ended ---
    if step >= max_steps and not final_message:
        final_message = f"Reached maximum steps ({max_steps}). Agent stopped."
        yield json.dumps({
            "type": "final",
            "state": "error",
            "message": final_message,
        }) + "\n"

    save_agent_history(db, user_id, goal, final_message)
