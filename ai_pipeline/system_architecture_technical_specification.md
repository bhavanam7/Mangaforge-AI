# System Architecture & Technical Specification

**Project:** Dynamic AI Storytelling & Entity Enhancement Engine
**Target Environment:** Django Backend, React Frontend, Ollama (`llama3.2:3b`), Laya Model
**Deployment Platform:** Agent-First Environment / Google Antigravity
   
## 1. System Overview & Core Architecture
The system is a Hub-and-Spoke State-Driven AI Engine that provides a unified, chat-based interface for interactive story generation and multi-entity enhancement.   Rather than relying on a static, linear pipeline, a central Django orchestrator maintains state integrity, dynamically routes user messages, and applies Context Slicing. Context Slicing ensures that llama3.2:3b receives only the isolated sub-schema required for a specific task, eliminating hallucination and JSON schema corruption.                           ```text
┌──────────────────────────────────┐
                           │      React Chat Component        │
                           │  (Sends user input & scope tag)  │
                           └────────────────┬─────────────────┘
                                            │
                                            ▼
                           ┌──────────────────────────────────┐
                           │   Django Central Orchestrator    │
                           │     (Intent Router & State)      │
                           └────────────────┬─────────────────┘
                                            │
         ┌──────────────────┬───────────────┼───────────────┬──────────────────┐
         ▼                  ▼               ▼               ▼                  ▼
  ┌─────────────┐    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐    ┌─────────────┐
  │ Phase 0:    │    │ Phase 1:    │ │ Phase 2:    │ │ Phase 3:    │    │ Phase 4:    │
  │ Laya Prompt │    │ 2-Question  │ │ Interactive │ │ Master JSON │    │ Enhancement │
  │ Validation  │    │ Engine      │ │ Story Chat  │ │ Extraction  │    │ Hub         │
  └─────────────┘    └─────────────┘ └─────────────┘ └─────────────┘    └──────┬──────┘
                                                                               │
                                                   ┌───────────────────────────┴───────────────────────────┐
                                                   ▼                                                       ▼
                                       ┌───────────────────────┐                               ┌───────────────────────┐
                                       │ Character Selection & │                               │ Background / Scene    │
                                       │ Summary Sub-Engine    │                               │ Summary Sub-Engine    │
                                       └───────────────────────┘
```
                               └───────────────────────┘

## 2. Complete Data Schemas (Pydantic & State Models)

### Pydantic Data Contract

```python
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
    knowledge_gained: List[str] = []  # e.g., "Learned Orochimaru's weakness"
    
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
```

## 3. Prompt Catalog & Usage Specifications

| Prompt Key | Target Model | Format | Usage Context |
|---|---|---|---|
| `PROMPT_VALIDATION_LAYA` | Laya | Boolean / Quality Score | Evaluates if the user's initial prompt has sufficient detail. |
| `PROMPT_CLARIFICATION_2Q` | `llama3.2:3b` | Text | Generates exactly 2 targeted clarification questions. |
| `PROMPT_STORY_GENERATION_CHAT` | `llama3.2:3b` | Plain Text | Interactive multi-turn story generation and text refinement. |
| `PROMPT_MASTER_JSON_EXTRACTION` | `llama3.2:3b` | JSON (`TurnExtractionOutput`) | Converts finalized narrative text into structured state. |
| `CHARACTER_SUMMARY_SYSTEM_PROMPT` | `llama3.2:3b` | Single Paragraph | Generates isolated character profile summary. |
| `BACKGROUND_SUMMARY_SYSTEM_PROMPT` | `llama3.2:3b` | Single Paragraph | Generates isolated environmental summary. |
| `SCENE_SUMMARY_SYSTEM_PROMPT` | `llama3.2:3b` | Single Paragraph | Generates isolated scene and dialogue summary. |

### System Prompt Definitions

#### 1. Laya Initial Prompt Validation

```text
SYSTEM: You are a prompt quality classifier. Analyze the user's initial story idea.
Determine if it provides enough core context (setting, character, or theme) to begin a story.
Return JSON: {"is_sufficient": boolean, "feedback": "Brief feedback if insufficient"}
```

#### 2. Two-Question Clarification Prompt

```text
SYSTEM: You are an expert story planner. Based on the user's initial prompt, ask EXACTLY TWO concise questions to clarify important narrative details (e.g., tone, main conflict, or world setting).
Rule: Output strictly the two questions, numbered 1 and 2, with no intro or commentary.
```

#### 3. Character Summary Prompt

```text
CHARACTER_SUMMARY_SYSTEM_PROMPT = """You are an expert manga story analyst.
Summarize the provided character's canonical traits and immediate scene state into a concise, well-written single paragraph.
Cover their role, relationship to the main character, base appearance, outfit, current emotion, current action, goal, injuries, knowledge, and any extra details.
Output ONLY the summary paragraph without conversational filler."""
```
```

#### 4. Background Summary Prompt

```text
BACKGROUND_SUMMARY_SYSTEM_PROMPT = """You are a scene visualizer.
Summarize the environmental setting into a single descriptive paragraph covering location, category, time of day, visual details, and immediate world events.
Output ONLY the summary paragraph without preamble."""
```

#### 5. Scene Summary Prompt

```text
SCENE_SUMMARY_SYSTEM_PROMPT = """You are a narrative editor.
Summarize the current scene dynamics and dialogue interactions into a single cohesive paragraph.
Highlight primary character interactions, action flow, and dramatic beats.
Output ONLY the summary paragraph without conversational filler."""
```
```

## 4. Execution Workflow & Lifecycle Phases
```text
[Phase 0: Prompt Validation] ──(Pass)──> [Phase 1: 2-Question Clarification]
         │                                               │
      (Fail)                                             ▼
         │                                  [Phase 2: Story Chat]
         ▼                                               │
[Request Re-entry]                             (User Finalizes)
                                                         │
                                                         ▼
                                            [Phase 3: JSON Extraction]
                                                         │
                                                         ▼
                                            [Phase 4: Enhancement Hub]
                                           ┌─────────────┼─────────────┐
                                           ▼             ▼             ▼
                                      [Background]  [Character]     [Scene]
```


### Phase Details

#### Phase 0: Initial Prompt Validation (Laya Gatekeeper)
- User inputs an initial story prompt.
- Sent to the Laya Model for fast classification.
- If invalid: Return a message asking for more details; state remains `INITIAL_PROMPT`.
- If valid: Proceed to Phase 1.
#### Phase 1: Clarification Q&A (`llama3.2:3b`)
- The model produces 2 targeted questions based on the validated initial prompt.
- User answers the questions in the chat window.
- Answers are concatenated with the initial prompt context. State advances to `STORY_GENERATION`.
#### Phase 2: Interactive Story Generation Chat
- Conversational turn-taking between user and `llama3.2:3b` in narrative prose.
- User can ask for modifications (e.g., “Add more action to the opening” or “Make the tone darker”).
- Continues until the user clicks “Finalize Story Draft” or states readiness. State advances to `JSON_EXTRACTION`.
#### Phase 3: Master JSON Extraction
- Orchestrator sends the finalized narrative text to `llama3.2:3b` with schema `TurnExtractionOutput.model_json_schema()`.
- Extracted JSON is stored in the Django backend database as `master_json`.
- State advances to `ENHANCEMENT_HUB`.
#### Phase 4: Enhancement Hub (Unrestricted Entity Switching)
- User can jump freely between Background, Scene, or Character modifications.
- **Dynamic Character Handling:**
  - Frontend inspects `master_json.characters`.
  - UI displays selectable character buttons/chips (e.g., `[Naruto]`, `[Sasuke]`).
  - When a character is selected, Django runs the isolated `CHARACTER_SUMMARY_SYSTEM_PROMPT` on `CharacterSceneInfo` to present a single-paragraph summary.
  - User edits are applied directly to that character's schema slice and merged back into `master_json`.
## 5. Unified API Specification & Payload Structure

### Endpoint Definition
- **URL:** `/api/story/chat/`
- **Method:** `POST`
- **Content-Type:** `application/json`
### Request Payload Structure

```json
{
  "session_id": "uuid-v4-string",
  "message": "User text input",
  "phase": "ENHANCEMENT_HUB",
  "scope": "character",
  "target_id": "char_02"
}
```

### Scope & Routing Logic
- `scope = "auto"`: Django runs lightweight intent classification on the message.
- `scope = "character"`: Target slice is `master_json.characters[target_id]`. Uses the `CharacterSceneInfo` schema.
- `scope = "background"`: Target slice is `master_json.background` and `environment`. Uses the `BackgroundState` schema.
- `scope = "scene"`: Target slice is `master_json.scene`. Uses the `SceneState` schema.
- `scope = "story"`: Standard narrative chat generation.
### Response Payload Structure

```json
{
  "session_id": "uuid-v4-string",
  "reply": "Assistant text response or generated summary",
  "active_phase": "ENHANCEMENT_HUB",
  "active_scope": "character",
  "target_id": "char_02",
  "character_list": [
    {"id": "char_01", "name": "Naruto"},
    {"id": "char_02", "name": "Sasuke"}
  ],
  "updated_state": { /* Full TurnExtractionOutput JSON */ }
}
```

## 6. Implementation Task Blueprint for AI Agents (Antigravity)
Use the following breakdown to delegate sub-tasks when executing with AI agents:   
### Backend Tasks (Django REST Framework)
- **Database Models:** Create a `StorySession` model storing `session_id`, `current_phase`, `narrative_history` (JSON), and `master_state` (JSON).
- **Pydantic Schemas:** Place all state schemas in `schemas.py`.
- **Ollama Driver:** Implement a wrapper module calling `ollama.chat()` with `format=Schema.model_json_schema()`.
- **Intent & Scope Router:** Implement logic to slice context depending on incoming `scope` and `target_id`.
- **Orchestrator Endpoint:** Implement unified `POST /api/story/chat/` handling state transition gates (Phases 0 through 4).
### Frontend Tasks (React)
- **Chat UI Base:** Implement chat message feed with input bar and send trigger.
- **Phase Indicators:** Top status bar indicating active lifecycle phase (Prompt Entry → Clarification → Story Draft → Enhancement Hub).
- **Enhancement Hub Navigation Bar:**
  - Context selector tabs: `[Background] | [Scene] | [Characters]`
  - **Dynamic Character Chips:** Display buttons rendered from `response.character_list`.
- **Payload Injection:** Ensure outgoing API requests attach the current active context scope and target ID.
