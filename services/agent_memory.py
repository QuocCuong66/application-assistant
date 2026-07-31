"""
Per-session agent memory for the Observe → Plan → Act → Verify loop.

One AgentMemory instance is created per run_agent_loop() invocation.
Tracks goal, completed steps, stale-screen detection, anti-loop counters,
and failure budget.
"""
from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Optional


class AgentMemory:
    """Stateful memory for a single agent loop session."""

    def __init__(self, goal: str, max_steps: int = 15):
        # --- Core ---
        self.user_goal: str = goal
        self.max_steps: int = max_steps
        self.current_step: int = 0

        # --- Step history ---
        self.completed_steps: List[Dict[str, Any]] = []
        self.progress_summary: str = ""

        # --- Last action tracking ---
        self.last_action: Optional[Dict[str, Any]] = None
        self.last_expected_result: str = ""
        self.last_observation: str = ""

        # --- Screen tracking ---
        self.last_screenshot_hash: str = ""
        self.screen_resolution: Dict[str, int] = {"width": 0, "height": 0}
        self.screenshot_dimensions: Dict[str, int] = {"width": 0, "height": 0}

        # --- Coordinate space of the active VLM backend ---
        # "pixel"           -> model returns literal thumbnail pixel coords (OpenAI/GPT-4o)
        # "normalized_1000" -> model returns coords on a 0-1000 grid (Gemini's native format)
        self.coord_space: str = "pixel"

        # --- Anti-loop counters ---
        self.consecutive_wait_count: int = 0
        self.consecutive_same_action_count: int = 0
        self.stale_screen_count: int = 0

        # --- Failure tracking ---
        self.total_failures: int = 0
        self.last_error: Optional[str] = None

        # --- Session timing ---
        self.session_start_time: float = time.time()

    # ------------------------------------------------------------------
    # Step recording
    # ------------------------------------------------------------------

    def record_step(
        self,
        step_num: int,
        action: Dict[str, Any],
        observation: str,
        result: str,
        expected: str,
    ) -> None:
        """Append a completed step.  Triggers summary rotation when history
        grows beyond 5 entries so prompt length stays bounded."""
        self.completed_steps.append({
            "step": step_num,
            "action": action,
            "observation": observation,
            "result": result,
            "expected": expected,
        })
        self.current_step = step_num
        self.last_observation = observation

        # Rotate: keep last 3 detailed, summarize the rest
        if len(self.completed_steps) > 5:
            self._rotate_summary()

    def _rotate_summary(self) -> None:
        """Compress older steps into a short text summary, keep last 3."""
        old_steps = self.completed_steps[:-3]
        kept = self.completed_steps[-3:]

        # Build a compact summary string
        parts: List[str] = []
        for s in old_steps:
            action = s.get("action", {})
            atype = action.get("type", "?")
            result = s.get("result", "?")
            parts.append(f"Step {s['step']}: {atype} → {result}")

        new_summary = "; ".join(parts)
        if self.progress_summary:
            self.progress_summary = f"{self.progress_summary}; {new_summary}"
        else:
            self.progress_summary = new_summary

        # Cap summary length to avoid unbounded growth
        if len(self.progress_summary) > 800:
            self.progress_summary = self.progress_summary[-800:]

        self.completed_steps = kept

    # ------------------------------------------------------------------
    # Failure tracking
    # ------------------------------------------------------------------

    def record_failure(self, error_msg: str) -> None:
        self.total_failures += 1
        self.last_error = error_msg

    def is_budget_exceeded(self) -> bool:
        """True when the session has accumulated too many failures."""
        return self.total_failures >= 5

    # ------------------------------------------------------------------
    # Screenshot hash — stale-screen detection
    # ------------------------------------------------------------------

    def update_screenshot_hash(self, base64_data: str) -> str:
        """Compute a short hash of the screenshot bytes.  Returns the hash."""
        raw = base64_data[:2000]  # hash a prefix to keep it fast
        h = hashlib.md5(raw.encode("utf-8", errors="ignore")).hexdigest()[:12]

        if self.last_screenshot_hash == h:
            self.stale_screen_count += 1
        else:
            self.stale_screen_count = 0

        self.last_screenshot_hash = h
        return h

    def is_screen_stale(self) -> bool:
        return self.stale_screen_count >= 2

    # ------------------------------------------------------------------
    # Screen info
    # ------------------------------------------------------------------

    def set_screen_info(
        self,
        resolution: Dict[str, int],
        thumbnail_size: Dict[str, int],
    ) -> None:
        """Store the native resolution and the thumbnail dimensions sent
        to the AI, so coordinates can be scaled back."""
        self.screen_resolution = resolution
        self.screenshot_dimensions = thumbnail_size

    # ------------------------------------------------------------------
    # Anti-loop detection
    # ------------------------------------------------------------------

    def update_action_tracking(self, action: Dict[str, Any]) -> None:
        """Compare new action to the previous one.  Increment same-action
        counter if they match (coordinates within ±10 px), reset otherwise."""
        if action is None:
            return

        atype = action.get("type", "")
        params = action.get("parameters", {})

        # Track consecutive waits
        if atype == "wait":
            self.consecutive_wait_count += 1
        else:
            self.consecutive_wait_count = 0

        # Track same-action repeats
        if self.last_action is not None:
            prev_type = self.last_action.get("type", "")
            prev_params = self.last_action.get("parameters", {})

            is_same = prev_type == atype
            if is_same and atype in ("click", "double_click", "right_click"):
                dx = abs(params.get("x", 0) - prev_params.get("x", 0))
                dy = abs(params.get("y", 0) - prev_params.get("y", 0))
                is_same = dx <= 10 and dy <= 10
            elif is_same:
                is_same = params == prev_params

            if is_same:
                self.consecutive_same_action_count += 1
            else:
                self.consecutive_same_action_count = 0
        else:
            self.consecutive_same_action_count = 0

        self.last_action = action

    def should_force_replan(self) -> bool:
        """True when the agent is stuck in a loop."""
        return (
            self.consecutive_same_action_count >= 3
            or self.consecutive_wait_count >= 2
        )

    # ------------------------------------------------------------------
    # Prompt helpers
    # ------------------------------------------------------------------

    def get_progress_summary(self) -> str:
        """Return compressed text covering all steps except the last 3."""
        return self.progress_summary or "No previous steps."

    def get_recent_steps_text(self) -> str:
        """Return formatted detail for the last 3 completed steps."""
        if not self.completed_steps:
            return "No steps completed yet."

        lines: List[str] = []
        for s in self.completed_steps[-3:]:
            action = s.get("action", {})
            lines.append(
                f"- Step {s['step']}: {action.get('type', '?')}"
                f"({action.get('parameters', {})}) "
                f"→ {s.get('result', '?')}"
            )
        return "\n".join(lines)
        