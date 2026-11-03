"""
Django Central Orchestrator (Intent Router & State)
===================================================
Hub-and-spoke, state-driven orchestration exactly as described in
`system_architecture_technical_specification.md` (Sections 1 and 4).

Phase <-> Django ``StorySession.Stage`` mapping
-----------------------------------------------
    Phase 0  Laya prompt validation      -> PROMPT_EVAL
    Phase 1  2-question clarification    -> ENRICHED_CONTENT (entry)
    Phase 2  Interactive story chat      -> ENRICHED_CONTENT
    Phase 3  Master JSON extraction      -> JSON_GENERATION
    Phase 4  Enhancement hub             -> CHARACTER_ENHANCEMENT
                                            BACKGROUND_ENHANCEMENT
                                            SCENE_DIALOGUE_ENHANCEMENT

Contract with the Django backend (`backend/apps/projects/story_views.py`):

    reply, stage, enriched_content, json_output = handle_turn(
        user_content, stage, enriched_content, json_output,
        action="chat", scope=None, target_id=None,
    )

`enriched_content` holds the working/finalized narrative text.
`json_output` (persisted in `StorySession.json_output`) holds the pipeline
state: the master extraction JSON, plus the small amount of bookkeeping the
state machine needs between HTTP requests. Because only these two fields
survive between turns, no module-level or per-process state is used.

Phase 4 note: the specification requires unrestricted entity switching, so the
stage reported back simply mirrors the active scope (character / background /
scene) instead of enforcing the linear chain in
`StorySession.ALLOWED_TRANSITIONS` (that matrix is never invoked by the view).

Narrative <-> state synchronisation
-----------------------------------
`master_json` is derived state: it is only valid for the exact narrative text
it was extracted from (see `state_sync.py`). Every narrative change bumps
`narrative_version`, and a master JSON produced from an older version is stale:
it is re-extracted before the enhancement hub reads it, so the story the user
just edited and the character/background/scene slices can never disagree.
Manual hub edits are recorded as leaf patches and re-applied after each
re-extraction instead of being silently discarded.

Logging
-------
Every state function is decorated with `log_call`, which prints its arguments,
its return value and its duration, and `banner` prints the state going in and
out of a turn. Records go to stdout, so they sit next to Django's own output.
Set `AI_PIPELINE_LOG_LEVEL=DEBUG` for the very chatty internals.
"""

import copy
import json
import logging
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

import ollama_driver
import scope_router
import state_sync
from ollama_driver import build_messages, complete, complete_structured
from prompts.agents_prompt import (
    BACKGROUND_EDIT_SYSTEM_PROMPT,
    BACKGROUND_SUMMARY_SYSTEM_PROMPT,
    CHARACTER_EDIT_SYSTEM_PROMPT,
    CHARACTER_SUMMARY_SYSTEM_PROMPT,
    PROMPT_CLARIFICATION_2Q,
    PROMPT_STORY_GENERATION_CHAT,
    SCENE_EDIT_SYSTEM_PROMPT,
    SCENE_SUMMARY_SYSTEM_PROMPT,
    SYNTHESIS_SYSTEM_PROMPT,
    TURN_EXTRACTION_OUTPUT_PROMPT,
)
from pipeline_log import banner, get_logger, log_call, state_snapshot
from schemas import (
    BackgroundState,
    CharacterSceneInfo,
    SceneState,
    TurnExtractionOutput,
    validate_master_state,
)

LOG = get_logger("orchestrator")

# --- Django StorySession.Stage mirrors (kept in sync with models.py) --------
PROMPT_EVAL = "PROMPT_EVAL"
ENRICHED_CONTENT = "ENRICHED_CONTENT"
JSON_GENERATION = "JSON_GENERATION"
CHARACTER_ENHANCEMENT = "CHARACTER_ENHANCEMENT"
BACKGROUND_ENHANCEMENT = "BACKGROUND_ENHANCEMENT"
SCENE_DIALOGUE_ENHANCEMENT = "SCENE_DIALOGUE_ENHANCEMENT"
FINALIZED = "FINALIZED"

ENHANCEMENT_STAGES = (
    CHARACTER_ENHANCEMENT,
    BACKGROUND_ENHANCEMENT,
    SCENE_DIALOGUE_ENHANCEMENT,
)

_STAGE_BY_SCOPE = {
    "character": CHARACTER_ENHANCEMENT,
    "background": BACKGROUND_ENHANCEMENT,
    "scene": SCENE_DIALOGUE_ENHANCEMENT,
}

MODEL_ERROR = (
    "I couldn't reach the story model for that step (Ollama unavailable or it "
    "returned an unusable response). Your story state was left untouched — "
    "please try again."
)
INVALID_JSON_ERROR = (
    "The model returned malformed structured data, so your story state was left "
    "untouched. Please try again, or rephrase the request."
)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def handle_turn(
    user_content: str,
    stage: str,
    enriched_content: str,
    json_output: Any,
    action: str = "chat",
    scope: Optional[str] = None,
    target_id: Optional[str] = None,
) -> Tuple[str, str, str, Dict[str, Any]]:
    """Run one orchestrated turn and return the new (reply, stage, enriched, state)."""
    user_content = (user_content or "").strip()
    stage = stage or PROMPT_EVAL
    enriched_content = enriched_content or ""
    state = _normalize_state(json_output)

    # INFO already shows the turn banners emitted by `main.run_pipeline`; the
    # orchestrator copies them at DEBUG so direct calls stay traceable too.
    banner(
        "TURN IN",
        level=logging.DEBUG,
        stage=stage,
        action=(action or "chat"),
        scope=scope,
        target_id=target_id,
        user_content=user_content,
        enriched_chars=len(enriched_content),
        enriched_preview=enriched_content,
        state=state_snapshot(state),
    )

    try:
        result = _dispatch(
            user_content=user_content,
            stage=stage,
            enriched_content=enriched_content,
            state=state,
            action=(action or "chat"),
            scope=scope,
            target_id=target_id,
        )
    except Exception:  # never let the pipeline 500 the Django endpoint
        traceback.print_exc()
        _log("unhandled exception — returning the previous state unchanged")
        return (
            "The story engine hit an unexpected error while handling that message. "
            "Nothing was lost — please try again.",
            stage,
            enriched_content,
            state,
        )

    reply, new_stage, new_enriched, new_state = result
    banner(
        "TURN OUT",
        level=logging.DEBUG,
        stage=new_stage,
        reply_chars=len(reply or ""),
        reply=reply,
        enriched_chars=len(new_enriched or ""),
        state=state_snapshot(new_state),
    )
    return result


@log_call()
def _dispatch(
    user_content: str,
    stage: str,
    enriched_content: str,
    state: Dict[str, Any],
    action: str,
    scope: Optional[str],
    target_id: Optional[str],
) -> Tuple[str, str, str, Dict[str, Any]]:
    _log(f"dispatch | stage={stage} action={action} scope={scope} target={target_id}")

    if stage == FINALIZED:
        return (
            "This story session is finalized. Start a new session to keep writing.",
            FINALIZED,
            enriched_content,
            state,
        )

    if stage == PROMPT_EVAL:
        return _phase_zero(user_content, state, enriched_content)

    if stage == ENRICHED_CONTENT:
        if state.get("awaiting_clarifications"):
            return _phase_one_answers(user_content, state, enriched_content)
        if scope_router.wants_finalize(action, user_content):
            # Finalising always re-extracts — even when a master JSON already
            # exists — so the structured state describes the draft the user
            # just finalised rather than the previous revision of it.
            return _phase_three(enriched_content, state, stage, reason="finalize")
        return _phase_two(user_content, state, enriched_content)

    if stage == JSON_GENERATION:
        if not state.get("master_json"):
            return _phase_three(enriched_content, state, stage)
        return _phase_four(user_content, state, enriched_content, action, scope, target_id, stage)

    if stage in ENHANCEMENT_STAGES:
        return _phase_four(user_content, state, enriched_content, action, scope, target_id, stage)

    # Unknown/legacy stage value: resume at the furthest phase whose state exists.
    _log(f"unknown stage '{stage}' — resuming from persisted state")
    if state.get("master_json"):
        return _phase_four(user_content, state, enriched_content, action, scope, target_id, JSON_GENERATION)
    if enriched_content.strip():
        return _phase_two(user_content, state, enriched_content)
    return _phase_zero(user_content, state, enriched_content)


# ---------------------------------------------------------------------------
# Phase 0 — Laya prompt validation (gatekeeper)
# ---------------------------------------------------------------------------

@log_call()
def _phase_zero(
    user_content: str, state: Dict[str, Any], enriched_content: str
) -> Tuple[str, str, str, Dict[str, Any]]:
    sufficient, reason = _validate_prompt(user_content)
    if not sufficient:
        reply = "Your prompt needs a bit more detail before we can start the story."
        if reason:
            reply += f" {reason.strip()}"
        reply += (
            "\n\nAdd specifics such as the main character, the setting, the central "
            "conflict, or the tone you want — then send it again."
        )
        return reply, PROMPT_EVAL, enriched_content, state

    # Phase 1 — exactly two clarification questions.
    questions = _generate_clarification_questions(user_content)
    if questions is None:
        return MODEL_ERROR, PROMPT_EVAL, enriched_content, state

    state["initial_prompt"] = user_content
    state["clarification_questions"] = questions
    state["awaiting_clarifications"] = True
    state["active_scope"] = "story"
    state["target_id"] = None

    # Seed the working narrative with the validated prompt (spec Phase 1).
    enriched_content = user_content
    state_sync.set_narrative(state, enriched_content, "phase0_validated_prompt")

    _log("Phase 0 passed -> Phase 1 (clarification questions issued)")
    return questions, ENRICHED_CONTENT, enriched_content, state


def _validate_prompt(text: str) -> Tuple[bool, str]:
    """Run the Laya gatekeeper; degrade to a heuristic if the model is unavailable."""
    try:
        from agents.laya_agent import evaluate_user_prompt

        result = evaluate_user_prompt(user_content=text, stage=PROMPT_EVAL)
        print(result)
        return bool(result.get("is_efficient")), _prompt_feedback(result)
    except Exception:
        _log("Laya model unavailable — falling back to heuristic prompt validation")
        traceback.print_exc()
        return _heuristic_prompt_sufficient(text), ""


def _prompt_feedback(result: Dict[str, Any]) -> str:
    raw = result.get("raw_response")
    if isinstance(raw, dict):
        sufficiency = raw.get("sufficiency")
        candidates = [sufficiency, raw] if isinstance(sufficiency, dict) else [raw]
        for candidate in candidates:
            for key in ("reason", "feedback", "explanation", "detail"):
                value = candidate.get(key)
                if value:
                    return str(value)
    if result.get("sufficiency") == "insufficient":
        return ""
    return ""


def _heuristic_prompt_sufficient(text: str) -> bool:
    cleaned = (text or "").strip()
    if len(cleaned) < 40 or len(cleaned.split()) < 8:
        return False
    if cleaned.lower() in {"write a story", "write me a story", "tell me a tale", "story"}:
        return False
    return True


def _generate_clarification_questions(initial_prompt: str) -> Optional[str]:
    try:
        reply = complete(
            build_messages(system=PROMPT_CLARIFICATION_2Q, user=initial_prompt),
            temperature=0.4,
        )
        reply = (reply or "").strip()
        return reply or None
    except Exception:
        traceback.print_exc()
        return None


# ---------------------------------------------------------------------------
# Phase 1 — clarification answers merged into the working narrative
# ---------------------------------------------------------------------------

@log_call()
def _phase_one_answers(
    user_content: str, state: Dict[str, Any], enriched_content: str
) -> Tuple[str, str, str, Dict[str, Any]]:
    initial_prompt = state.get("initial_prompt") or enriched_content or ""
    questions = state.get("clarification_questions") or ""

    merged = _synthesize_narrative(initial_prompt, questions, user_content)
    if not merged:
        # Spec fallback: answers are concatenated with the initial prompt context.
        merged = _join_text(initial_prompt, user_content)

    state["awaiting_clarifications"] = False
    state["clarification_questions"] = ""
    state["active_scope"] = "story"
    state_sync.set_narrative(state, merged, "phase1_clarification_answers")
    _log("Phase 1 complete -> Phase 2 (interactive story chat)")

    return merged, ENRICHED_CONTENT, merged, state


def _synthesize_narrative(initial_prompt: str, questions: str, answers: str) -> Optional[str]:
    payload = (
        f"INITIAL STORY PROMPT:\n{initial_prompt}\n\n"
        f"CLARIFICATION QUESTIONS ASKED:\n{questions or '(none)'}\n\n"
        f"USER'S ANSWERS / ADDITIONAL DETAILS:\n{answers}"
    )
    try:
        reply = complete(
            build_messages(system=SYNTHESIS_SYSTEM_PROMPT, user=payload), temperature=0.3
        )
        return (reply or "").strip() or None
    except Exception:
        traceback.print_exc()
        return None


# ---------------------------------------------------------------------------
# Phase 2 — interactive story generation chat
# ---------------------------------------------------------------------------

@log_call()
def _phase_two(
    user_content: str, state: Dict[str, Any], enriched_content: str
) -> Tuple[str, str, str, Dict[str, Any]]:
    state["active_scope"] = "story"

    if enriched_content.strip() and scope_router.is_revision(user_content):
        refined = _refine_narrative(enriched_content, user_content)
        if refined:
            _log("Phase 2 revision applied to the working narrative")
            state_sync.set_narrative(state, refined, "phase2_revision")
            return refined, ENRICHED_CONTENT, refined, state

    reply = _story_chat(user_content, enriched_content)
    if reply is None:
        return MODEL_ERROR, ENRICHED_CONTENT, enriched_content, state

    enriched_content = _append_narrative(enriched_content, reply)
    state_sync.set_narrative(state, enriched_content, "phase2_story_turn")
    _log(
        "Phase 2 story turn appended to the working narrative "
        f"(narrative v{state.get('narrative_version')}, master JSON stale="
        f"{state.get('master_json_stale')})"
    )
    return reply, ENRICHED_CONTENT, enriched_content, state


def _story_chat(user_content: str, enriched_content: str) -> Optional[str]:
    context = (enriched_content or "").strip()
    if context:
        payload = f"[WORKING STORY SO FAR]\n{context}\n\n[LATEST USER MESSAGE]\n{user_content}"
    else:
        payload = user_content
    try:
        reply = complete(
            build_messages(system=PROMPT_STORY_GENERATION_CHAT, user=payload),
            temperature=0.4,
        )
        return (reply or "").strip() or None
    except Exception:
        traceback.print_exc()
        return None


def _refine_narrative(current_context: str, feedback: str) -> Optional[str]:
    """Delegate to the existing information-gathering agent (modification requests)."""
    try:
        from agents.information_gathering import refine_enriched_context
    except Exception:
        traceback.print_exc()
        return None
    try:
        refined = refine_enriched_context(
            current_context=current_context,
            user_feedback=feedback,
            model_name=ollama_driver.DEFAULT_MODEL,
        )
        return (refined or "").strip() or None
    except Exception:
        traceback.print_exc()
        return None


# ---------------------------------------------------------------------------
# Phase 3 — master JSON extraction
# ---------------------------------------------------------------------------

@log_call()
def _phase_three(
    enriched_content: str,
    state: Dict[str, Any],
    current_stage: str,
    reason: str = "finalize",
) -> Tuple[str, str, str, Dict[str, Any]]:
    narrative = (enriched_content or "").strip()
    if not narrative:
        return (
            "There is no story text to structure yet. Write or refine the draft first, "
            "then finalize it.",
            current_stage,
            enriched_content,
            state,
        )

    master = _extract_master(narrative, state, reason=reason)
    if master is None:
        _log("Phase 3 extraction failed — the previous state was left untouched")
        return INVALID_JSON_ERROR, current_stage, enriched_content, state

    state["awaiting_clarifications"] = False
    state["clarification_questions"] = ""
    state["active_scope"] = "story"
    state["target_id"] = None

    history = state.get("extraction_history")
    if not isinstance(history, list):
        history = []
        state["extraction_history"] = history
    history.append(
        {
            "reason": reason,
            "narrative_version": state.get("narrative_version"),
            "characters": len(master.get("characters") or []),
            "enriched_chars": len(narrative),
        }
    )

    _log("Phase 3 complete -> Phase 4 (enhancement hub)")
    return _describe_extraction(master), JSON_GENERATION, enriched_content, state


@log_call()
def _extract_master(
    narrative: str, state: Dict[str, Any], reason: str = "extraction"
) -> Optional[Dict[str, Any]]:
    """
    Run the Phase 3 extraction and merge the user's Phase 4 edits back in.

    `master_json` is derived from the narrative, so the version it was built from
    is recorded here; that record is what lets `_sync_master_with_narrative`
    decide whether the structured state still matches the story text.
    """
    print("LLm calling for the json generation")
    raw = complete_structured(
        build_messages(system=TURN_EXTRACTION_OUTPUT_PROMPT, user=narrative),
        schema=TurnExtractionOutput,
        temperature=0.1,
        retries=1,
    )
    print("Raw after the llm call for the json:- ", raw)
    if raw is None:
        _log(f"extraction ({reason}) returned no parseable JSON")
        return None

    master = validate_master_state(raw)
    if master is None:
        _log(f"extraction ({reason}) failed TurnExtractionOutput validation")
        return None

    state["master_json"] = master

    applied, skipped, unresolved = state_sync.apply_overrides(master, state)
    if applied or skipped:
        _log(
            "re-applied manual hub edits after extraction: "
            f"applied={applied} skipped={skipped}"
            + (f" (no entity in the new story for {', '.join(unresolved)})" if unresolved else "")
        )

    state_sync.mark_extracted(state, narrative)
    _log(
        f"master JSON rebuilt | reason={reason} "
        f"narrative v{state.get('extracted_version')} "
        f"characters={len(master.get('characters') or [])}"
    )
    return master


@log_call()
def _sync_master_with_narrative(
    state: Dict[str, Any], enriched_content: str, reason: str
) -> Optional[Dict[str, Any]]:
    """
    Re-extract the master JSON when the narrative moved on without it.

    This is the fix for the drifted-state bug: a story edited after it was
    finalised used to keep its old character/background/scene slices forever,
    so "old and new story didn't match". Nothing is re-extracted unless the
    narrative really changed, so unchanged turns cost no extra model call.
    """
    narrative = (enriched_content or "").strip()
    if not narrative or not state.get("master_json"):
        return None
    if not state_sync.is_stale(state, narrative):
        return None

    _log(
        "master JSON is stale — re-extracting "
        f"(extracted v{state.get('extracted_version') or 0} vs narrative "
        f"v{state.get('narrative_version') or 0}, reason={reason})"
    )
    master = _extract_master(narrative, state, reason=reason)
    if master is None:
        _log("re-extraction failed — keeping the previously extracted state")
        return None

    # Keep the hub pointed at a character that still exists.
    target = state.get("target_id")
    if target and not state_sync.has_character(master, target):
        _log(f"target character '{target}' no longer exists — selection cleared")
        state["target_id"] = None
    return master


def _describe_extraction(master: Dict[str, Any]) -> str:
    lines = ["Master JSON extraction complete — the story is now structured."]

    characters = scope_router.list_characters(master)
    if characters:
        names = ", ".join(f"{c['name']} ({c['id']})" for c in characters)
        lines.append(f"Characters ({len(characters)}): {names}")
    else:
        lines.append("Characters: none detected in this scene.")

    background = master.get("background") or {}
    if background.get("location") or background.get("time_of_day"):
        location = background.get("location") or "unspecified location"
        time_of_day = background.get("time_of_day") or "unspecified time"
        lines.append(f"Background: {location} — {time_of_day}")

    scene = master.get("scene") or {}
    if scene.get("summary"):
        lines.append(f"Scene: {scene['summary']}")

    lines.append(
        "You can now jump freely between Background, Scene and any Character to refine them."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Phase 4 — enhancement hub (unrestricted entity switching)
# ---------------------------------------------------------------------------

@log_call()
def _phase_four(
    user_content: str,
    state: Dict[str, Any],
    enriched_content: str,
    action: str,
    scope: Optional[str],
    target_id: Optional[str],
    current_stage: str,
) -> Tuple[str, str, str, Dict[str, Any]]:
    master = state.get("master_json") or {}

    if not isinstance(master, dict) or not master:
        # Recovery path: state says we are in the hub but no master JSON exists.
        if enriched_content.strip():
            reply, new_stage, enriched_content, state = _phase_three(
                enriched_content, state, current_stage
            )
            if state.get("master_json"):
                return _route_enhancement(
                    user_content, state, enriched_content, action, scope, target_id, new_stage
                )
            return reply, new_stage, enriched_content, state
        return (
            "No structured story data exists yet. Finalize your story draft first so the "
            "entities can be extracted.",
            current_stage,
            enriched_content,
            state,
        )

    # The hub must never act on a master JSON that describes an older draft.
    _sync_master_with_narrative(state, enriched_content, "hub_entry")

    return _route_enhancement(
        user_content, state, enriched_content, action, scope, target_id, current_stage
    )


@log_call()
def _route_enhancement(
    user_content: str,
    state: Dict[str, Any],
    enriched_content: str,
    action: str,
    scope: Optional[str],
    target_id: Optional[str],
    current_stage: str,
) -> Tuple[str, str, str, Dict[str, Any]]:
    master = state.get("master_json") or {}
    resolved_scope = scope_router.resolve_scope(
        scope=scope, action=action, message=user_content, master_json=master
    )
    state["active_scope"] = resolved_scope
    _log(f"Phase 4 hub routing -> scope={resolved_scope}")

    if resolved_scope == "character":
        return _handle_character(user_content, state, enriched_content, action, target_id)
    if resolved_scope == "background":
        return _handle_background(user_content, state, enriched_content, action)
    if resolved_scope == "scene":
        return _handle_scene(user_content, state, enriched_content, action)

    # scope == "story": the user went back to writing. The narrative is no
    # longer read-only here — it is updated and re-extracted below, otherwise
    # the story and the structured state drift apart for good.
    return _handle_story_scope(user_content, state, enriched_content, current_stage)


@log_call()
def _handle_story_scope(
    user_content: str,
    state: Dict[str, Any],
    enriched_content: str,
    current_stage: str,
) -> Tuple[str, str, str, Dict[str, Any]]:
    """
    Narrative turn taken while the session is already past Phase 3.

    This used to reply with prose and leave `enriched_content` and `master_json`
    untouched, so changes made after the draft was finalised never reached the
    database nor the entity slices. Now the new narrative is stored and the
    master JSON is re-extracted from it in the same turn.
    """
    state["active_scope"] = "story"
    state["target_id"] = None

    reply = ""
    new_narrative = ""

    if enriched_content.strip() and scope_router.is_revision(user_content):
        refined = _refine_narrative(enriched_content, user_content)
        if refined:
            reply, new_narrative = refined, refined

    # A revision request the refinement agent could not serve (model offline,
    # agent import failure) still has to produce a narrative turn, exactly like
    # Phase 2 does, instead of erroring out and dropping the message.
    if not new_narrative:
        reply = _story_chat(user_content, enriched_content) or ""
        if reply:
            new_narrative = _append_narrative(enriched_content, reply)

    if not new_narrative:
        # Model unavailable: keep the draft, do not touch the derived state.
        return MODEL_ERROR, current_stage, enriched_content, state

    state_sync.set_narrative(state, new_narrative, "phase4_story_change")
    refreshed = _sync_master_with_narrative(state, new_narrative, "phase4_story_change")
    _log(
        "Phase 4 story-scope turn applied | "
        f"narrative v{state.get('narrative_version')} | "
        f"master JSON {'refreshed' if refreshed else 'left unchanged'}"
    )
    return reply, current_stage, new_narrative, state


# --- Character slice --------------------------------------------------------

@log_call()
def _handle_character(
    user_content: str,
    state: Dict[str, Any],
    enriched_content: str,
    action: str,
    target_id: Optional[str],
) -> Tuple[str, str, str, Dict[str, Any]]:
    master = state.get("master_json") or {}
    characters = [c for c in (master.get("characters") or []) if isinstance(c, dict)]
    if not characters:
        return (
            "No characters were extracted from this story, so there is nothing to refine yet.",
            CHARACTER_ENHANCEMENT,
            enriched_content,
            state,
        )

    listed = scope_router.list_characters(master)
    available = ", ".join(f"{c['name']} ({c['id']})" for c in listed)

    # char_id = scope_router.resolve_character_target(target_id, user_content, master)
    #perform changes 
    effective_target_id = target_id or state.get("target_id")

    char_id = scope_router.resolve_character_target(
        effective_target_id,
        user_content,
        master
    )
    if char_id is None:
        state["target_id"] = None
        return (
            f"Which character do you want to work on? Available: {available}.",
            CHARACTER_ENHANCEMENT,
            enriched_content,
            state,
        )

    index = _find_character_index(master, char_id)
    original = characters[index]
    state["target_id"] = char_id

    # Phase 4 selection: present the isolated single-paragraph summary.
    if scope_router.is_select_request(
        action, user_content, [c["name"] for c in listed]
    ) or scope_router.is_selection_only(action, user_content):
        summary = _summarize_character(original)
        if summary is None:
            return MODEL_ERROR, CHARACTER_ENHANCEMENT, enriched_content, state
        return summary, CHARACTER_ENHANCEMENT, enriched_content, state

    updated = _enhance_character(original, user_content)
    if updated is None:
        return INVALID_JSON_ERROR, CHARACTER_ENHANCEMENT, enriched_content, state

    updated = _merge_character(original, updated)
    master["characters"][index] = updated
    state["master_json"] = master
    # Remember exactly which fields the user changed, so re-extracting a
    # revised story later re-applies them instead of dropping the edits.
    state_sync.record_overrides(
        state,
        f"{state_sync.CHARACTER_PREFIX}{char_id}",
        copy.deepcopy(original),
        updated,
        name=(updated.get("canon") or {}).get("name"),
    )

    name = (updated.get("canon") or {}).get("name") or char_id
    summary = _summarize_character(updated)
    reply = summary or f"Updated character \"{name}\"."
    _log(f"Phase 4 character slice merged back for {char_id}")
    return reply, CHARACTER_ENHANCEMENT, enriched_content, state


def _find_character_index(master: Dict[str, Any], char_id: str) -> int:
    for index, character in enumerate(master.get("characters") or []):
        if not isinstance(character, dict):
            continue
        canon_id = (character.get("canon") or {}).get("id")
        if str(canon_id) == str(char_id):
            return index
    return 0


def _enhance_character(
    character_slice: Dict[str, Any], feedback: str
) -> Optional[Dict[str, Any]]:
    payload = (
        "CURRENT CHARACTER DATA (CharacterSceneInfo JSON):\n"
        f"{_json(character_slice)}\n\n"
        "USER FEEDBACK TO APPLY:\n"
        f"{feedback}"
    )
    raw = complete_structured(
        build_messages(system=CHARACTER_EDIT_SYSTEM_PROMPT, user=payload),
        schema=CharacterSceneInfo,
        retries=1,
    )
    if raw is None:
        return None
    try:
        return CharacterSceneInfo.model_validate(raw).model_dump()
    except Exception:
        traceback.print_exc()
        return None


def _merge_character(
    original: Dict[str, Any], updated: Dict[str, Any]
) -> Dict[str, Any]:
    """Guarantee identity fields survive the model round-trip, then merge back."""
    merged = dict(updated)
    merged.setdefault("canon", {})
    merged.setdefault("state", {})

    original_canon = original.get("canon") or {}
    original_id = original_canon.get("id")

    if original_id:
        merged["canon"]["id"] = original_id
        merged["state"]["character_id"] = original_id
    elif merged["canon"].get("id") and not merged["state"].get("character_id"):
        merged["state"]["character_id"] = merged["canon"]["id"]

    if not merged["canon"].get("name") and original_canon.get("name"):
        merged["canon"]["name"] = original_canon["name"]

    return merged


def _summarize_character(character_slice: Dict[str, Any]) -> Optional[str]:
    try:
        reply = complete(
            build_messages(
                system=CHARACTER_SUMMARY_SYSTEM_PROMPT, user=_json(character_slice)
            ),
            temperature=0.3,
        )
        return (reply or "").strip() or None
    except Exception:
        traceback.print_exc()
        return None


# --- Background slice -------------------------------------------------------

@log_call()
def _handle_background(
    user_content: str,
    state: Dict[str, Any],
    enriched_content: str,
    action: str = "chat",
) -> Tuple[str, str, str, Dict[str, Any]]:
    master = state.get("master_json") or {}
    current = master.get("background")
    if not isinstance(current, dict):
        current = {}

    # Phase 4 selection: present the isolated single-paragraph summary.
    if scope_router.is_selection_only(action, user_content):
        state["target_id"] = None
        if not current:
            return (
                "No background has been extracted from this story yet. Describe the "
                "setting you want and I'll apply it.",
                BACKGROUND_ENHANCEMENT,
                enriched_content,
                state,
            )
        summary = _summarize_background(current)
        if summary is None:
            return MODEL_ERROR, BACKGROUND_ENHANCEMENT, enriched_content, state
        return summary, BACKGROUND_ENHANCEMENT, enriched_content, state

    payload = (
        "CURRENT BACKGROUND DATA (BackgroundState JSON):\n"
        f"{_json(current)}\n\n"
        "WORLD / ENVIRONMENT CONTEXT (reference only):\n"
        f"{_json(master.get('environment') or {})}\n\n"
        "USER FEEDBACK TO APPLY:\n"
        f"{user_content}"
    )
    raw = complete_structured(
        build_messages(system=BACKGROUND_EDIT_SYSTEM_PROMPT, user=payload),
        schema=BackgroundState,
        retries=1,
    )
    if raw is None:
        return INVALID_JSON_ERROR, BACKGROUND_ENHANCEMENT, enriched_content, state

    try:
        updated = BackgroundState.model_validate(raw).model_dump()
    except Exception:
        traceback.print_exc()
        return INVALID_JSON_ERROR, BACKGROUND_ENHANCEMENT, enriched_content, state

    state_sync.record_overrides(state, "background", copy.deepcopy(current), updated)

    master["background"] = updated
    state["master_json"] = master
    state["target_id"] = None

    summary = _summarize_background(updated)
    reply = summary or f"Updated background: {updated.get('location') or 'setting adjusted'}."
    _log("Phase 4 background slice merged back")
    return reply, BACKGROUND_ENHANCEMENT, enriched_content, state


def _summarize_background(background: Dict[str, Any]) -> Optional[str]:
    try:
        reply = complete(
            build_messages(system=BACKGROUND_SUMMARY_SYSTEM_PROMPT, user=_json(background)),
            temperature=0.3,
        )
        return (reply or "").strip() or None
    except Exception:
        traceback.print_exc()
        return None


# --- Scene slice ------------------------------------------------------------

@log_call()
def _handle_scene(
    user_content: str,
    state: Dict[str, Any],
    enriched_content: str,
    action: str = "chat",
) -> Tuple[str, str, str, Dict[str, Any]]:
    master = state.get("master_json") or {}
    current = master.get("scene")
    if not isinstance(current, dict):
        current = {"summary": "", "dialogues": []}

    # Phase 4 selection: present the isolated single-paragraph summary.
    if scope_router.is_selection_only(action, user_content):
        state["target_id"] = None
        if not current.get("summary") and not current.get("dialogues"):
            return (
                "No scene has been extracted from this story yet. Describe the beats "
                "or dialogue you want and I'll apply them.",
                SCENE_DIALOGUE_ENHANCEMENT,
                enriched_content,
                state,
            )
        summary = _summarize_scene(current)
        if summary is None:
            return MODEL_ERROR, SCENE_DIALOGUE_ENHANCEMENT, enriched_content, state
        return summary, SCENE_DIALOGUE_ENHANCEMENT, enriched_content, state

    payload = (
        "CURRENT SCENE DATA (SceneState JSON):\n"
        f"{_json(current)}\n\n"
        "USER FEEDBACK TO APPLY:\n"
        f"{user_content}"
    )
    raw = complete_structured(
        build_messages(system=SCENE_EDIT_SYSTEM_PROMPT, user=payload),
        schema=SceneState,
        retries=1,
    )
    if raw is None:
        return INVALID_JSON_ERROR, SCENE_DIALOGUE_ENHANCEMENT, enriched_content, state

    try:
        updated = SceneState.model_validate(raw).model_dump()
    except Exception:
        traceback.print_exc()
        return INVALID_JSON_ERROR, SCENE_DIALOGUE_ENHANCEMENT, enriched_content, state

    state_sync.record_overrides(state, "scene", copy.deepcopy(current), updated)

    master["scene"] = updated
    state["master_json"] = master
    state["target_id"] = None

    summary = _summarize_scene(updated)
    reply = summary or f"Updated scene: {updated.get('summary') or 'scene adjusted'}."
    _log("Phase 4 scene slice merged back")
    return reply, SCENE_DIALOGUE_ENHANCEMENT, enriched_content, state


def _summarize_scene(scene: Dict[str, Any]) -> Optional[str]:
    try:
        reply = complete(
            build_messages(system=SCENE_SUMMARY_SYSTEM_PROMPT, user=_json(scene)),
            temperature=0.3,
        )
        return (reply or "").strip() or None
    except Exception:
        traceback.print_exc()
        return None


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _normalize_state(json_output: Any) -> Dict[str, Any]:
    """Coerce whatever Django persisted into the pipeline state shape."""
    if isinstance(json_output, dict):
        state = dict(json_output)
    elif isinstance(json_output, str):
        try:
            parsed = json.loads(json_output)
            state = parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, ValueError):
            state = {}
    else:
        state = {}

    if not isinstance(state.get("master_json"), dict):
        state["master_json"] = {}
    if not isinstance(state.get("history"), list):
        state["history"] = []
    state.setdefault("initial_prompt", "")
    state.setdefault("clarification_questions", "")
    state.setdefault("awaiting_clarifications", False)
    state.setdefault("active_scope", "story")
    state.setdefault("target_id", None)

    # Narrative <-> master JSON bookkeeping (contract documented in state_sync).
    state.setdefault("narrative_version", 0)
    state.setdefault("extracted_version", 0)
    state.setdefault("narrative_hash", "")
    state.setdefault("narrative_changed_reason", "")
    state.setdefault("master_json_stale", False)
    if not isinstance(state.get("manual_overrides"), dict):
        state["manual_overrides"] = {}

    # State persisted by an older build has a master JSON but no narrative
    # fingerprint: mark it stale so the next hub turn rebuilds it once.
    if state.get("master_json") and not state.get("narrative_hash"):
        state["master_json_stale"] = True
    return state


def _join_text(first: str, second: str) -> str:
    first = (first or "").strip()
    second = (second or "").strip()
    if not first:
        return second
    if not second:
        return first
    return f"{first}\n\n{second}"


def _append_narrative(current: str, addition: str) -> str:
    addition = (addition or "").strip()
    if not addition:
        return current or ""
    current = (current or "").strip()
    if not current:
        return addition
    if addition in current:
        return current
    return f"{current}\n\n{addition}"


def _json(value: Any) -> str:
    try:
        return json.dumps(value, indent=2, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)


def _log(message: str) -> None:
    """Phase-transition line: goes to stdout (and the log file, if configured)."""
    LOG.info(message)
