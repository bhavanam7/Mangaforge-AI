"""
Pydantic Data Contract
======================
Complete state schemas defined in
`system_architecture_technical_specification.md` (Section 2).

These models are the single source of truth for:
  * Phase 3 Master JSON Extraction (format = TurnExtractionOutput.model_json_schema())
  * Phase 4 Enhancement Hub context slicing (CharacterSceneInfo / BackgroundState / SceneState)
  * Validation of everything persisted into the Django `StorySession.json_output`
    (master_json) field.

Imported by the Django orchestrator as `schemas` (the ai_pipeline directory is
placed on `sys.path` by `main.py`).
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class CharacterCanon(BaseModel):
    """Permanent/Canonical character profile (persisted across scenes in DB)."""
    id: str
    name: Optional[str] = None
    role: Optional[str] = None  # e.g., "Protagonist", "Antagonist", "Supporting", "Narrator"
    relationship_to_main_character: Optional[str] = None  # e.g., "Self", "Mentor", "Enemy", "Ally"
    age: Optional[int] = None
    base_appearance: Optional[str] = None  # Static physical features (hair, eyes, height)
    default_outfit: Optional[str] = None
    permanent_physical_changes: List[str] = []  # e.g., ["Lost left arm", "Scar on right eye"]
    extra: Dict[str, Any] = {}


class CharacterState(BaseModel):
    """Transient state of a character in the immediate scene/turn."""
    character_id: str  # Maps directly to CharacterCanon.id
    emotion: Optional[str] = None  # e.g., "Enraged", "Terrified"
    current_goal: Optional[str] = None  # e.g., "Escape the falling rocks"
    injuries_sustained_this_turn: List[str] = []  # e.g., ["Cut on left hand", "Severed left arm"]
    current_action: Optional[str] = None  # e.g., "Dodging Orochimaru's strike"
    knowledge_gained: List[str] = []  # e.g., ["Learned Orochimaru's weakness"]

    # Flag to indicate if current turn injuries/events alter permanent canonical state
    causes_permanent_canon_change: bool = False
    permanent_change_description: Optional[str] = None  # e.g., "Left arm cut off permanently"

    extra: Dict[str, Any] = {}


class CharacterSceneInfo(BaseModel):
    """Combines canonical profile extraction and current turn state."""
    canon: CharacterCanon
    state: CharacterState


class EnvironmentState(BaseModel):
    category: Optional[str] = None
    world_description: Optional[str] = None


class BackgroundState(BaseModel):
    location: Optional[str] = None
    time_of_day: Optional[str] = None
    visual_details: Optional[str] = None
    event_details: Optional[str] = None


class DialogueState(BaseModel):
    character_id_or_name: str
    line: str


class SceneState(BaseModel):
    summary: str
    dialogues: List[DialogueState] = []


class TurnExtractionOutput(BaseModel):
    environment: Optional[EnvironmentState] = None
    characters: List[CharacterSceneInfo] = []  # Contains both Canon profile and Turn State
    background: Optional[BackgroundState] = None
    scene: SceneState


TurnExtractionOutput.model_rebuild()


# ---------------------------------------------------------------------------
# Helpers used by the orchestrator (state initialization / validation)
# ---------------------------------------------------------------------------

def empty_master_state() -> Dict[str, Any]:
    """Return an empty but schema-valid `master_json` payload."""
    return TurnExtractionOutput(scene=SceneState(summary="")).model_dump()


def validate_master_state(data: Any) -> Optional[Dict[str, Any]]:
    """Validate arbitrary data against TurnExtractionOutput; returns dict or None."""
    if not isinstance(data, dict):
        return None
    try:
        return TurnExtractionOutput.model_validate(data).model_dump()
    except Exception:
        return None
