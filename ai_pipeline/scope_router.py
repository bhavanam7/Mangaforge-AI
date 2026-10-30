"""
Intent & Scope Router
=====================
Implements the routing half of the specification (Section 5):

    scope = "auto"        -> lightweight intent classification on the message
    scope = "character"   -> master_json.characters[target_id] (CharacterSceneInfo)
    scope = "background"  -> master_json.background + environment (BackgroundState)
    scope = "scene"       -> master_json.scene (SceneState)
    scope = "story"       -> standard narrative chat generation

The router is deliberately dependency-free keyword/heuristic classification:
it runs on every turn, so it must never cost an LLM round-trip. The heavy
interpretation is always done by the model itself downstream.
"""

import re
from typing import Any, Dict, List, Optional

# Order matters only for tie-breaking; the first scope whose keywords hit wins.
_SCOPE_KEYWORDS = {
    "character": (
        "character", "characters", "protagonist", "antagonist", "hero", "villain",
        "outfit", "costume", "appearance", "look", "looks", "hair", "eyes",
        "emotion", "emotional", "injur", "scar", "wound", "canon", "relationship",
        "age", "goal", "knowledge", "his ", "her ", "he ", "she ",
    ),
    "background": (
        "background", "setting", "location", "place", "location", "environment",
        "world", "scenery", "scene layout", "time of day", "time", "dusk", "dawn",
        "night", "morning", "weather", "lighting", "sky", "forest", "city", "room",
    ),
    "scene": (
        "dialogue", "dialog", "line", "lines", "says", "say", "speak", "speech",
        "conversation", "conversation flow", "scene summary", "beat", "pacing",
        "interaction", "exchange",
    ),
}

# Explicit, non-LLM signals for finalizing the draft (Phase 2 -> Phase 3).
_FINALIZE_ACTIONS = {"finalize_stage", "finalize", "finalize_story", "extract_json"}
_FINALIZE_MESSAGES = {
    "finalize",
    "finalize story",
    "finalize story draft",
    "finalize draft",
    "done",
    "i'm ready",
    "im ready",
    "finish",
}

# Signals that the user is *selecting* an entity rather than editing it.
_SELECT_ACTIONS = {"select", "select_character", "summarize", "summary", "show"}

_REVISION_PATTERNS = (
    r"^\s*(make|change|rewrite|revise|edit|rework|re-write|re-write)\b",
    r"^\s*add\s+(more|a|the|another)\b",
    r"^\s*(remove|delete|drop|cut)\b",
    r"\bmore (action|drama|tension|detail|descriptive)\b",
    r"\bmake (it|the|this)\b",
    r"\bdarker|lighter|funnier|scarier|slower|faster\b",
    r"\binstead\b|\balso add\b|\btoo (long|short)\b",
)


def _normalize(text: Optional[str]) -> str:
    return (text or "").strip().lower()


SELECT_SCOPES = tuple(_SCOPE_KEYWORDS)  # ("character", "background", "scene")
ALL_SCOPES = SELECT_SCOPES + ("story", "auto")


def is_scope(value: Optional[str]) -> bool:
    return isinstance(value, str) and value.strip().lower() in ALL_SCOPES


def resolve_scope(
    scope: Optional[str] = None,
    action: Optional[str] = None,
    message: str = "",
    master_json: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Decide which schema slice this turn targets.

    Precedence: explicit ``scope`` > scope carried in ``action`` > a message that
    is exactly a character's name (entity selection) > keyword intent
    classification. Enhancement scopes only apply once a master JSON exists;
    before that the turn is always narrative (``story``).
    """
    if scope:
        normalized = scope.strip().lower()
        if normalized in SELECT_SCOPES or normalized == "story":
            return normalized
        # "auto" (or anything unknown) falls through to action/intent.

    if action:
        normalized_action = action.strip().lower()
        if normalized_action in SELECT_SCOPES:
            return normalized_action
        # "chat" is the default action and carries no scope information, so it
        # must fall through to entity/intent classification below.
        if normalized_action in ("story", "generate", "narrative"):
            return "story"

    has_master_json = isinstance(master_json, dict) and bool(master_json.get("characters") or master_json.get("scene"))
    if not has_master_json:
        return "story"

    # A bare entity name (e.g. "Naruto") is a selection of that entity.
    text = (message or "").strip()
    if text and len(text) <= 40:
        lowered = text.lower()
        if any(
            str((c.get("canon") or {}).get("name", "")).strip().lower() == lowered
            for c in master_json.get("characters") or []
            if isinstance(c, dict)
        ):
            return "character"

    return classify_intent(message) or "story"


def classify_intent(message: str) -> Optional[str]:
    """Lightweight keyword classifier -> 'character' | 'background' | 'scene' | None."""
    text = _normalize(message)
    if not text:
        return None

    scores: Dict[str, int] = {}
    for scope, keywords in _SCOPE_KEYWORDS.items():
        hits = 0
        for keyword in keywords:
            if keyword.endswith(" "):
                # Pronoun keywords ("he ", "her ") must be word-anchored too,
                # otherwise "the tone" counts as a hit for "he ".
                hits += len(re.findall(r"\b" + re.escape(keyword), text + " "))
            else:
                hits += len(re.findall(r"\b" + re.escape(keyword), text))
        scores[scope] = hits

    best = max(scores, key=lambda key: scores[key])
    return best if scores[best] > 0 else None


def is_revision(message: str) -> bool:
    """True when the user is asking to modify the existing narrative (Phase 2)."""
    text = _normalize(message)
    if not text:
        return False
    return any(re.search(pattern, text) for pattern in _REVISION_PATTERNS)


def wants_finalize(action: Optional[str], message: str) -> bool:
    if action and action.strip().lower() in _FINALIZE_ACTIONS:
        return True
    print("Finally in the starting of the phase 3")
    return _normalize(message) in _FINALIZE_MESSAGES


def is_select_request(action: Optional[str], message: str, names: List[str]) -> bool:
    """
    True when the turn is an entity *selection* (show me X) instead of an edit.

    Recognized forms: explicit select/summary actions, or a bare message that is
    exactly a character's name (e.g. "Naruto").
    """
    if action and action.strip().lower() in _SELECT_ACTIONS:
        return True
    text = (message or "").strip()
    if not text or len(text) > 40:
        return False
    return text.lower() in {name.strip().lower() for name in names if name}


def list_characters(master_json: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Build the [{id, name}] character list used in replies / UI chips."""
    characters = (master_json or {}).get("characters") or []
    result: List[Dict[str, str]] = []
    for index, character in enumerate(characters):
        if not isinstance(character, dict):
            continue
        canon = character.get("canon") or {}
        char_id = str(canon.get("id") or character.get("id") or f"char_{index + 1:02d}")
        result.append({"id": char_id, "name": str(canon.get("name") or char_id)})
    return result


def resolve_character_target(
    target_id: Optional[str],
    message: str,
    master_json: Optional[Dict[str, Any]],
) -> Optional[str]:
    """
    Map an incoming ``target_id`` (or an unambiguous message) onto a canonical
    character id present in ``master_json.characters``.

    Accepts: exact canon id, 0-based/1-based index ("0", "1", "char_02"), or a
    message that exactly matches a character name.
    """
    characters = list_characters(master_json)
    if not characters:
        return None

    if target_id:
        needle = str(target_id).strip().lower()
        for character in characters:
            if character["id"].lower() == needle or character["name"].lower() == needle:
                return character["id"]
        if needle.isdigit():
            index = int(needle)
            if index < len(characters):
                return characters[index]["id"]
            if index - 1 >= 0 and index - 1 < len(characters):
                return characters[index - 1]["id"]

    text = (message or "").strip().lower()
    if text:
        for character in characters:
            if character["name"].lower() == text:
                return character["id"]

    # A single-character story never needs disambiguation.
    if len(characters) == 1:
        return characters[0]["id"]
    return None


def character_slice(
    master_json: Optional[Dict[str, Any]], target_id: Optional[str]
) -> Optional[Dict[str, Any]]:
    """Return the isolated CharacterSceneInfo slice for ``target_id``."""
    for index, character in enumerate((master_json or {}).get("characters") or []):
        if isinstance(character, dict) and str((character.get("canon") or {}).get("id")) == str(target_id):
            return character
        if isinstance(character, dict) and index == _coerce_index(target_id):
            return character
    return None


def _coerce_index(value: Any) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return -1
