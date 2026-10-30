"""
Narrative <-> Master JSON Synchronisation
=========================================
`master_json` (the Phase 3 ``TurnExtractionOutput``) is **derived** state: it is
only valid for the exact narrative text stored in
``StorySession.enriched_content``. As soon as that text changes — a revision in
the Phase 2 chat, a clarification answer, or a story turn taken from inside the
Phase 4 hub — the structured state describes the *previous* version of the
story and the two silently disagree (the "old and new story don't match" bug).

This module owns the bookkeeping for that contract:

``narrative_version``
    Bumped every time the narrative text actually changes.
``narrative_hash``
    Short hash of the normalised narrative text (whitespace-insensitive).
``extracted_version``
    The ``narrative_version`` the current master JSON was extracted from.
``master_json_stale``
    Convenience flag: ``extracted_version != narrative_version``.
``manual_overrides``
    Leaf-level patches recorded when the user edits a character / background /
    scene slice in the Phase 4 hub. A re-extraction re-applies them, so
    refreshing the state never silently throws away the user's work.

Everything here is plain-dict/JSON friendly: it is all persisted inside
``StorySession.json_output`` and therefore survives between HTTP requests.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Tuple

_MISSING = object()

CHARACTER_PREFIX = "characters:"
SLICE_KEYS = ("background", "scene")


# ---------------------------------------------------------------------------
# Narrative versioning
# ---------------------------------------------------------------------------

def narrative_hash(text: Optional[str]) -> str:
    """Whitespace-insensitive fingerprint of the narrative text."""
    normalized = " ".join((text or "").split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def set_narrative(state: Dict[str, Any], text: Optional[str], reason: str = "") -> bool:
    """
    Record that the narrative text is now ``text``.

    Bumps ``narrative_version`` (and flags the master JSON as stale) only when
    the text really changed, so repeated saves of the same draft are free.
    Returns True when a change was recorded.
    """
    digest = narrative_hash(text)
    if digest == state.get("narrative_hash"):
        return False

    state["narrative_hash"] = digest
    state["narrative_version"] = int(state.get("narrative_version") or 0) + 1
    state["narrative_changed_reason"] = reason or "unknown"
    state["master_json_stale"] = bool(state.get("master_json"))
    return True


def mark_extracted(state: Dict[str, Any], text: Optional[str]) -> None:
    """Record that ``master_json`` now corresponds to ``text``."""
    set_narrative(state, text, reason="extraction")
    state["extracted_version"] = int(state.get("narrative_version") or 0)
    state["master_json_stale"] = False


def is_stale(state: Dict[str, Any], text: Optional[str]) -> bool:
    """
    True when a master JSON exists but does not match ``text``.

    Handles both cases: a narrative that changed after the last extraction, and
    legacy state persisted before this bookkeeping existed (no hash recorded).
    """
    if not state.get("master_json"):
        return False
    if narrative_hash(text) != state.get("narrative_hash"):
        return True
    return int(state.get("extracted_version") or 0) != int(state.get("narrative_version") or 0)


# ---------------------------------------------------------------------------
# Field-level patches (used to preserve manual hub edits)
# ---------------------------------------------------------------------------

def diff_fields(
    before: Any, after: Any, _path: Tuple[str, ...] = ()
) -> List[List[Any]]:
    """
    Return ``[[path, value], ...]`` for every leaf that differs.

    Lists are replaced as a whole (a dialogue list is only meaningful whole);
    dicts are walked key by key. Removed keys are intentionally ignored: the
    pydantic models always re-emit their fields, so a "missing" key means the
    model dropped an optional value rather than the user deleting it.
    """
    changes: List[List[Any]] = []

    if isinstance(before, dict) and isinstance(after, dict):
        for key, new_value in after.items():
            key_path = _path + (str(key),)
            if key not in before:
                changes.append([list(key_path), new_value])
            else:
                changes.extend(diff_fields(before[key], new_value, key_path))
        return changes

    if isinstance(before, list) and isinstance(after, list):
        if before != after:
            changes.append([list(_path), after])
        return changes

    if before != after:
        changes.append([list(_path), after])
    return changes


def apply_fields(target: Any, patches: Optional[List[Any]]) -> int:
    """Apply patches produced by :func:`diff_fields`; returns how many landed."""
    if not patches:
        return 0

    applied = 0
    for patch in patches:
        if not isinstance(patch, (list, tuple)) or len(patch) != 2:
            continue
        path, value = patch
        if not isinstance(path, (list, tuple)) or not path:
            continue

        node: Any = target
        for key in path[:-1]:
            node = _step(node, key)
            if node is _MISSING:
                break
        if node is _MISSING:
            continue

        last = path[-1]
        if isinstance(node, dict):
            node[str(last)] = value
            applied += 1
        elif isinstance(node, list) and _is_index(last) and 0 <= int(last) < len(node):
            node[int(last)] = value
            applied += 1
    return applied


def _step(node: Any, key: Any) -> Any:
    if isinstance(node, dict):
        return node.get(str(key), _MISSING)
    if isinstance(node, list) and _is_index(key):
        index = int(key)
        return node[index] if 0 <= index < len(node) else _MISSING
    return _MISSING


def _is_index(value: Any) -> bool:
    return isinstance(value, int) or (isinstance(value, str) and value.isdigit())


# ---------------------------------------------------------------------------
# Manual overrides
# ---------------------------------------------------------------------------

def record_overrides(
    state: Dict[str, Any],
    key: str,
    before: Any,
    after: Any,
    name: Optional[str] = None,
) -> List[List[Any]]:
    """
    Remember which fields the user changed for one hub slice.

    ``key`` is ``background`` / ``scene`` or ``characters:<canon id>``. ``name``
    lets a later re-extraction find the character again even if the model
    renumbered its id.
    """
    patches = diff_fields(before, after)

    overrides = state.get("manual_overrides")
    if not isinstance(overrides, dict):
        overrides = {}
        state["manual_overrides"] = overrides

    if patches:
        overrides[key] = {"name": name or "", "patch": patches}
    else:
        overrides.pop(key, None)
    return patches


def apply_overrides(master: Dict[str, Any], state: Dict[str, Any]) -> Tuple[int, int, List[str]]:
    """
    Re-apply recorded manual edits onto a freshly extracted ``master``.

    Returns ``(applied_slices, skipped_slices, unresolved_keys)``. Unresolved
    overrides are kept so an entity that temporarily disappears from the story
    keeps its edits if it comes back.
    """
    overrides = state.get("manual_overrides")
    if not isinstance(overrides, dict) or not overrides:
        return 0, 0, []

    applied = skipped = 0
    unresolved: List[str] = []
    rekeyed: Dict[str, Any] = {}

    for key, record in overrides.items():
        if isinstance(record, dict):
            patches = record.get("patch")
            name = record.get("name") or ""
        else:  # tolerate the flat {"key": patch} shape
            patches, name = record, ""

        target = resolve_override_target(master, key, name)
        if target is None:
            rekeyed[key] = record
            unresolved.append(key)
            skipped += 1
            continue

        if apply_fields(target, patches):
            applied += 1
        else:
            skipped += 1
        rekeyed[rekey_target(key, target)] = record

    state["manual_overrides"] = rekeyed
    return applied, skipped, unresolved


def resolve_override_target(master: Dict[str, Any], key: str, name: str = "") -> Optional[Dict[str, Any]]:
    """Find the dict an override key refers to inside ``master``."""
    if key in SLICE_KEYS:
        value = master.get(key)
        if isinstance(value, dict):
            return value
        value = {}
        master[key] = value
        return value

    if not key.startswith(CHARACTER_PREFIX):
        return None

    char_id = key[len(CHARACTER_PREFIX):]
    characters = [c for c in master.get("characters") or [] if isinstance(c, dict)]

    for character in characters:
        if str((character.get("canon") or {}).get("id")) == char_id:
            return character

    wanted = {char_id.strip().lower(), (name or "").strip().lower()}
    wanted.discard("")
    for character in characters:
        candidate = str((character.get("canon") or {}).get("name") or "").strip().lower()
        if candidate and candidate in wanted:
            return character
    return None


def rekey_target(key: str, target: Dict[str, Any]) -> str:
    """Point a character override at the id the new extraction assigned."""
    if not key.startswith(CHARACTER_PREFIX):
        return key
    new_id = (target.get("canon") or {}).get("id")
    return f"{CHARACTER_PREFIX}{new_id}" if new_id else key


def has_character(master: Dict[str, Any], character_id: Any) -> bool:
    """True when ``character_id`` still exists in ``master.characters``."""
    if not character_id:
        return False
    return any(
        str((character.get("canon") or {}).get("id")) == str(character_id)
        for character in master.get("characters") or []
        if isinstance(character, dict)
    )
