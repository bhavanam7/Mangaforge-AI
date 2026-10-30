"""
AI Pipeline Main Entry Point
============================
Single entry point used by the Django backend
(`backend/apps/projects/story_views.py`):

    from main import run_pipeline
    ai_reply, stage, enriched_content, json_output = run_pipeline(
        user_content=..., stage=..., enriched_content=..., json_output=..., action=...
    )

The actual hub-and-spoke phase machine lives in `orchestrator.py`; this module
only keeps the Django-facing signature stable, logs the inbound state, and
guarantees a JSON-serialisable return value (Django persists `json_output` in a
JSONField and `stage` in a CharField).
"""

import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from orchestrator import handle_turn  # noqa: E402  (path bootstrap above)
from pipeline_log import banner, get_logger, state_snapshot  # noqa: E402

LOG = get_logger("main")

__all__ = ["run_pipeline"]


def run_pipeline(
    user_content: str,
    stage: str,
    enriched_content: str,
    json_output: Dict[str, Any],
    action: str = "chat",
    scope: Optional[str] = None,
    target_id: Optional[str] = None,
) -> Tuple[str, str, str, Dict[str, Any]]:
    """
    Execute one orchestrated turn.

    Args:
        user_content: raw text from the React chat input.
        stage: current `StorySession.stage` (PROMPT_EVAL, ENRICHED_CONTENT,
            JSON_GENERATION, *_ENHANCEMENT, FINALIZED).
        enriched_content: working/finalized narrative stored on the session.
        json_output: persisted pipeline state (`StorySession.json_output`);
            the master extraction JSON lives under its `master_json` key.
        action: request action — "chat" (default), "finalize_stage", or a scope
            name such as "character" / "background" / "scene".
        scope: optional explicit scope (spec payload field); overrides `action`.
        target_id: optional character id for character-scoped turns.

    Returns:
        (ai_reply, new_stage, new_enriched_content, new_json_output)
    """
    started = time.perf_counter()

    banner(
        "RECEIVE | state as stored by Django",
        user_content=user_content,
        stage=stage,
        action=action,
        scope=scope,
        target_id=target_id,
        enriched_chars=len(enriched_content or ""),
        enriched_preview=enriched_content or "",
        state=_summarize_state(json_output),
    )

    try:
        reply, new_stage, new_enriched, new_state = handle_turn(
            user_content=user_content,
            stage=stage,
            enriched_content=enriched_content,
            json_output=json_output,
            action=action,
            scope=scope,
            target_id=target_id,
        )
    except Exception:
        # handle_turn already guards itself; this is the last-resort guard so a
        # pipeline bug can never take the Django endpoint down with a 500.
        traceback.print_exc()
        return (
            "The story engine could not process that message. Your story state was "
            "left unchanged — please try again.",
            stage,
            enriched_content or "",
            json_output if isinstance(json_output, dict) else {},
        )

    new_state = _json_safe_state(new_state)

    banner(
        "RESULT | state to persist on the Django session",
        stage=new_stage,
        reply=reply or "",
        enriched_chars=len(new_enriched or ""),
        state=_summarize_state(new_state),
        elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
    )

    return reply or "", new_stage, new_enriched or "", new_state


def _summarize_state(json_output: Any) -> Dict[str, Any]:
    """Compact, log-safe view of the persisted pipeline state."""
    if not isinstance(json_output, dict):
        return {"payload": repr(json_output)[:200]}

    summary = state_snapshot(json_output)
    summary["keys"] = sorted(json_output.keys())
    return summary


def _json_safe_state(state: Any) -> Dict[str, Any]:
    """Ensure the state Django stores in its JSONField is serialisable."""
    if not isinstance(state, dict):
        return {}
    try:
        json.dumps(state)
        return state
    except (TypeError, ValueError):
        traceback.print_exc()
        return json.loads(json.dumps(state, default=str))


if __name__ == "__main__":
    # Manual smoke check: `python main.py`
    demo_prompt = (
        "A young alchemist in a desert city discovers an artifact that freezes "
        "time whenever water touches it."
    )
    result = run_pipeline(
        user_content=demo_prompt,
        stage="PROMPT_EVAL",
        enriched_content="",
        json_output={},
        action="chat",
    )
    print("Pipeline reply:", result[0][:500])
    print("Next stage:", result[1])
