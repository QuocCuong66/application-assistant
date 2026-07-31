"""
Centralized prompt construction for the Computer Use Agent.

Replaces the 330-line inline SYSTEM_PROMPT in the old agent_loop.py with
a focused, schema-enforced prompt and structured user-message builder.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from services.agent_memory import AgentMemory


# ======================================================================
# System Prompt — ~1 500 tokens, sent once per AI call
# ======================================================================

SYSTEM_PROMPT = """\
# Computer Use Agent

You are an autonomous desktop-control agent.  Your job is to complete the
user's goal by analysing screenshots and issuing ONE action at a time.

## Output Format (strict JSON — no markdown, no explanation)

When you still need to act, return:
{
  "status": "action_needed",
  "observation": "Describe what you see on the current screenshot.",
  "reasoning": "Explain why you chose this action.",
  "action": {
    "type": "<action_type>",
    "parameters": { ... }
  },
  "expected_result": "What should change after this action."
}

When the goal is fully achieved, return:
{
  "status": "completed",
  "observation": "Describe the screen confirming success.",
  "reasoning": "Explain why the goal is done.",
  "action": null,
  "expected_result": null
}

When you are blocked and cannot proceed, return:
{
  "status": "blocked",
  "observation": "Describe the screen.",
  "reasoning": "Explain why you are blocked.",
  "action": null,
  "expected_result": null
}

## Action Types

| type          | parameters                         | description               |
|---------------|------------------------------------|---------------------------|
| click         | {"x": int, "y": int}               | Single left click         |
| double_click  | {"x": int, "y": int}               | Double left click         |
| right_click   | {"x": int, "y": int}               | Right click               |
| type_text     | {"text": "string"}                 | Type text (Unicode safe)  |
| press_key     | {"key": "enter|tab|escape|..."}    | Press a single key        |
| hotkey        | {"keys": ["ctrl","c"]}             | Key combination           |
| scroll        | {"direction":"up|down","amount":3} | Scroll (amount = clicks)  |
| wait          | {"seconds": 2}                     | Wait for loading          |
| open_app      | {"app_name": "chrome"}             | Open an application       |

## Coordinate Rules

{coordinate_rules}

## Mandatory Rules

1. Return EXACTLY ONE action per response.
2. NEVER repeat the same action more than 2 times in a row.
3. Use at most 2 "wait" actions per session.  If the screen hasn't
   changed after waiting, try a different approach.
4. Always inspect the screenshot BEFORE acting — never guess.
5. Prefer keyboard shortcuts (hotkey) over mouse clicks when possible.
6. NEVER perform destructive actions (delete files, send money, etc.)
   unless the user explicitly requested it.
7. Output ONLY valid JSON.  No markdown.  No natural language outside JSON.
"""


# --- Coordinate rule variants ---
# NOTE (bugfix): Gemini models are trained for image-grounding tasks to
# ALWAYS return coordinates normalized to a 0-1000 grid, regardless of what
# the prompt asks for. Telling Gemini "return pixel coordinates" does not
# reliably override this trained prior, which was silently corrupting every
# click position when GEMINI_API_KEY was set (see agent_loop.scale_coordinates).
# OpenAI vision models, by contrast, do respect literal pixel-space instructions.
# So instead of fighting Gemini's native behavior, we ask each backend for the
# format it naturally produces and convert accordingly downstream.
_COORD_RULES_PIXEL = """\
- Coordinates are in **screenshot pixel space** (not native screen space).
- The screenshot dimensions are given in the user message (SCREEN INFO).
- Click at the CENTER of the target element.
- If you are unsure of the exact position, look for text labels or icons
  and estimate from there."""

_COORD_RULES_NORMALIZED_1000 = """\
- Coordinates are normalized to a **0-1000 by 0-1000 grid**, NOT literal
  screenshot pixels. (0,0) is the top-left corner, (1000,1000) is the
  bottom-right corner, regardless of the screenshot's actual pixel size.
- Example: the exact center of the screenshot is x=500, y=500.
- Click at the CENTER of the target element.
- If you are unsure of the exact position, look for text labels or icons
  and estimate from there."""


def build_system_prompt(coord_space: str = "pixel") -> str:
    """Return the system prompt string.

    Args:
        coord_space: "pixel" (OpenAI/GPT-4o) or "normalized_1000" (Gemini).
            Controls which coordinate convention the model is instructed to
            use, since this must match how the backend actually behaves.
    """
    rules = (
        _COORD_RULES_NORMALIZED_1000
        if coord_space == "normalized_1000"
        else _COORD_RULES_PIXEL
    )
    # Plain string replace (NOT str.format) because SYSTEM_PROMPT contains
    # literal JSON braces like {"x": int, "y": int} that .format() would
    # misinterpret as placeholders.
    return SYSTEM_PROMPT.replace("{coordinate_rules}", rules)


# ======================================================================
# User Message Builder
# ======================================================================

def build_user_message(
    goal: str,
    memory: "AgentMemory",
    error_context: Optional[str] = None,
) -> str:
    """Build the text part of the user message sent alongside the screenshot.

    The message is structured so the model always sees:
    1. The goal
    2. Screen dimensions (for coordinate reasoning)
    3. Compressed progress history
    4. Recent step detail
    5. Error/anti-loop hints when needed
    """
    parts: List[str] = []

    # --- Goal ---
    parts.append(f"## GOAL\n{goal}")

    # --- Screen Info ---
    sw = memory.screen_resolution.get("width", "?")
    sh = memory.screen_resolution.get("height", "?")
    tw = memory.screenshot_dimensions.get("width", "?")
    th = memory.screenshot_dimensions.get("height", "?")
    parts.append(
        f"## SCREEN INFO\n"
        f"Native resolution: {sw}×{sh}\n"
        f"Screenshot dimensions (coordinate space): {tw}×{th}"
    )

    # --- Progress ---
    parts.append(
        f"## PROGRESS\n"
        f"Step: {memory.current_step} / {memory.max_steps}\n"
        f"Summary of earlier steps: {memory.get_progress_summary()}"
    )

    # --- Recent Steps ---
    parts.append(
        f"## RECENT STEPS\n{memory.get_recent_steps_text()}"
    )

    # --- Error Context ---
    if error_context:
        parts.append(f"## ERROR\n{error_context}")

    if memory.last_error:
        parts.append(
            f"## LAST FAILURE\n"
            f"Your previous action failed: {memory.last_error}\n"
            f"Analyze the screenshot and try a different approach."
        )
        # Clear after injecting so it's not repeated
        memory.last_error = None

    # --- Anti-loop hints (mitigate R1, R2) ---
    hints = _build_anti_loop_hints(memory)
    if hints:
        parts.append(f"## IMPORTANT\n{hints}")

    # --- Final Instruction ---
    parts.append(
        "## INSTRUCTION\n"
        "Analyze the screenshot above.  Return exactly ONE action as JSON."
    )

    return "\n\n".join(parts)


def _build_anti_loop_hints(memory: "AgentMemory") -> str:
    """Generate warning text when the agent appears stuck."""
    hints: List[str] = []

    if memory.consecutive_wait_count >= 2:
        hints.append(
            f"You have issued {memory.consecutive_wait_count} consecutive "
            f"'wait' actions.  The screen has NOT changed.  You MUST take "
            f"a concrete action now or declare the task 'blocked'."
        )

    if memory.consecutive_same_action_count >= 2:
        hints.append(
            f"Your last {memory.consecutive_same_action_count + 1} actions "
            f"were identical.  They had no effect.  Try a DIFFERENT action "
            f"or DIFFERENT coordinates."
        )

    if memory.stale_screen_count >= 2:
        hints.append(
            "The screenshot has not changed after your recent actions.  "
            "Re-evaluate your approach."
        )

    return "\n".join(hints)


# ======================================================================
# Step Summarization (non-AI, rule-based)
# ======================================================================

def summarize_steps(steps: List[dict]) -> str:
    """Produce a compact one-line summary of a list of completed steps.

    This is a simple rule-based formatter, NOT an AI call, to avoid
    additional cost.  Used by AgentMemory._rotate_summary().

    Example output:
      "Steps 1-4: click(450,300) → success; type_text('hello') → success; ..."
    """
    if not steps:
        return ""

    first = steps[0].get("step", "?")
    last = steps[-1].get("step", "?")
    parts = []
    for s in steps:
        action = s.get("action", {})
        atype = action.get("type", "?")
        result = s.get("result", "?")
        parts.append(f"{atype} → {result}")

    body = "; ".join(parts)
    # Cap at 200 chars
    if len(body) > 200:
        body = body[:197] + "..."

    return f"Steps {first}-{last}: {body}"