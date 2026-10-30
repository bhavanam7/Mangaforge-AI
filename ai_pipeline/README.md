# AI Pipeline — Dynamic AI Storytelling Engine

Hub-and-spoke, state-driven story engine that powers the story chat in MangaForge.
It implements [`system_architecture_technical_specification.md`](./system_architecture_technical_specification.md):
a Django orchestrator drives five phases (prompt validation → clarification → interactive
story chat → master JSON extraction → enhancement hub) and calls local models
(`llama3.2:3b` via Ollama, plus the Laya gatekeeper model).

---

## 1. Repository layout

```
Mangaforge-AI/
├── ai_pipeline/                 ← this folder (the AI engine)
│   ├── main.py                  public entry point: run_pipeline(...) — called by Django
│   ├── orchestrator.py          Phase 0–4 state machine, hub routing, state persistence
│   ├── scope_router.py          intent/scope/target routing + character-slice selection
│   ├── state_sync.py            narrative versioning: keeps master_json in step with the story
│   ├── pipeline_log.py          logging setup + log_call tracing for every state function
│   ├── ollama_driver.py         Ollama wrapper (ollama.chat with format=<json schema>)
│   ├── schemas.py               Pydantic data contract (TurnExtractionOutput & friends)
│   ├── prompts/agents_prompt.py prompt catalog (system prompts for every task)
│   ├── agents/laya_agent.py     Phase 0 prompt-quality classifier (local Laya model)
│   ├── agents/information_gathering.py   narrative refinement agent
│   └── ai_models/               local model files (laya_model/, download scripts)
├── backend/                     Django 5.2 + DRF REST API, SQLite by default
│   └── apps/projects/story_views.py   imports ai_pipeline.main.run_pipeline
└── frontend/                    React + Vite + Tailwind chat UI
```

> `ai_pipeline/` is imported **in-process** by Django. There is no separate pipeline
> service or HTTP hop between the backend and the AI code.

---

## 2. Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.11+ | the repo was developed with 3.12/3.13-era libraries; 3.14 works for the pipeline modules themselves |
| Node.js 18+ | for the React frontend |
| [Ollama](https://ollama.com) | serving `llama3.2:3b` locally (required) |
| Laya model (~850 MB) | optional for local dev — used only for Phase 0 validation, and the pipeline falls back to a heuristic when it is unavailable |
| ~4 GB free RAM | `llama3.2:3b` runs on CPU; a CUDA GPU speeds up the Laya model |

---

## 3. One-time setup

### 3.1 Ollama (required)

```bash
# install once, then:
ollama serve                 # keeps running on http://localhost:11434
ollama pull llama3.2:3b      # ~2 GB
```

Check it:

```bash
curl http://localhost:11434/api/tags
```

### 3.2 Python environment (backend + pipeline share one venv)

```bash
cd Mangaforge-AI
python3 -m venv .venv
source .venv/bin/activate

# Django REST backend
pip install -r backend/requirements.txt

# AI pipeline extras (NOT in backend/requirements.txt)
pip install pydantic
pip install ollama                  # preferred backend (spec requirement)
# or, if you already use LangChain:  pip install langchain-ollama langchain-core

pip install torch                    # only needed for the Laya gatekeeper
pip install huggingface_hub          # only needed to download the Laya model
```

> The pipeline is imported by Django in the **same interpreter**, so every package
> above must be installed in the venv you run `manage.py` with.

### 3.3 Laya model (optional)

```bash
python ai_pipeline/ai_models/download_laya.py
```

Two hard-coded paths must point at **this** checkout:

* `ai_pipeline/ai_models/download_laya.py` → `LOCAL_PATH`
  (ships pointing at `…/Manga/ai_pipeline/ai_models/laya_model`, which is missing
  `Mangaforge-AI`)
* `ai_pipeline/agents/laya_agent.py` → `MODEL_DIR`
  (already correct for this repo: `ai_pipeline/ai_models/laya_model`)

If you skip this step, Phase 0 falls back to a length/keyword heuristic and logs
`Laya model unavailable — falling back to heuristic prompt validation`.

### 3.4 Backend environment

```bash
cd backend
cp .env.example .env
```

Then edit `backend/.env` — `DJANGO_SECRET_KEY` is **mandatory** (settings raises at
startup without it):

```dotenv
DJANGO_SECRET_KEY=replace-with-a-long-random-secret
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
FRONTEND_URL=http://localhost:5173
```

Apply migrations and (optionally) create an admin user:

```bash
python manage.py migrate
python manage.py createsuperuser
```

> Database defaults to SQLite (`backend/db.sqlite3`). The PostgreSQL block in
> `backend/config/settings.py` is commented out.

### 3.5 Frontend environment

```bash
cd frontend
cp .env.example .env      # VITE_API_URL=http://localhost:8000/api
npm install
```

---

## 4. Running the whole stack

Three terminals (activate the venv in the ones that need it):

```bash
# Terminal 1 — model server
ollama serve

# Terminal 2 — Django API on :8000
cd Mangaforge-AI
source .venv/bin/activate
cd backend
python manage.py runserver 8000

# Terminal 3 — React app on :5173
cd Mangaforge-AI/frontend
npm run dev
```

Then open <http://localhost:5173>, register/login, create a project, open
**Story chat** for that project (`/projects/<id>/story`).

Startup order: Ollama → Django → frontend. The first chat message can take
10–60 s on CPU while the models load.

### 4.1 Sanity checks

```bash
curl http://localhost:8000/api/health/          # {"status": "ok"}
curl http://localhost:11434/api/tags            # llama3.2:3b must be listed
```

### 4.2 Running the pipeline on its own (no Django, no React)

```bash
source .venv/bin/activate
cd ai_pipeline
python main.py
```

This runs one demo turn through `run_pipeline` and prints the reply, the next
stage, and the pipeline state. It is the fastest way to confirm Ollama and the
prompts are wired correctly.

---

## 5. How a message travels

```
React chat input
      │  POST /api/projects/<project_id>/story/   { "content": "..." }
      ▼
Django  ProjectStoryView.post  (JWT auth, saves the user message)
      │  run_pipeline(user_content, stage, enriched_content, json_output, action)
      ▼
ai_pipeline/main.py  →  orchestrator.handle_turn  →  Phase dispatch
      │                                            ├─ ollama_driver → Ollama (llama3.2:3b)
      │                                            ├─ agents/laya_agent → Laya (Phase 0)
      │                                            └─ schemas (JSON-schema constrained output)
      ▼
reply, new_stage, new_enriched_content, new_json_output
      │
      ▼
StorySession fields updated (stage / enriched_content / json_output) + assistant message saved
      │  JSON response (StorySessionSerializer)
      ▼
React chat renders the assistant reply
```

State lives **in the database**, not in the process: `enriched_content` holds the
working/finalized narrative, `json_output` holds
`{"master_json": {...}, "initial_prompt", "clarification_questions",
"awaiting_clarifications", "active_scope", "target_id", "narrative_version",
"extracted_version", "narrative_hash", "manual_overrides", ...}`.

Every stage function and every model call is logged (`[AI PIPELINE]` lines on
stdout) — see [section 5.2](#52-logging).

### 5.1 Narrative ↔ structured state synchronisation

`master_json` is **derived** state: it describes one exact version of the
narrative text. Editing the story after extraction would otherwise leave the
character / background / scene slices describing the previous draft
("old and new story don't match"). The pipeline now enforces the contract:

| Field in `json_output` | Meaning |
|---|---|
| `narrative_version` | bumped every time `enriched_content` actually changes (phase 1 answers, phase 2 turns/revisions, story-scope turns from the hub) |
| `narrative_hash` | whitespace-insensitive fingerprint of that text |
| `extracted_version` | the `narrative_version` the current `master_json` was extracted from |
| `master_json_stale` | `true` when the two disagree |
| `manual_overrides` | field-level patches of the user's Phase 4 edits |
| `extraction_history` | one entry per extraction (reason, version, character count) |

Behaviour:

* **Finalizing always re-extracts.** `action="finalize_stage"` rebuilds
  `master_json` from the *current* `enriched_content`, even when one already
  exists, so a re-finalized draft never keeps the old entities.
* **Story changes inside the hub re-extract immediately.** A `scope="story"`
  turn now updates `enriched_content` (it used to leave it untouched) and
  refreshes `master_json` in the same turn.
* **Entering the hub refreshes stale state.** Any Phase 4 turn first checks the
  versions and re-extracts if the narrative moved on (including state written by
  older builds, which has no fingerprint yet).
* **Manual edits survive re-extraction.** Each hub edit is diffed against the
  slice it came from and stored as leaf patches; after a re-extraction they are
  re-applied to the same character (matched by id, then by name), background or
  scene. Edits whose entity disappeared from the rewritten story are kept aside
  and reported in the log.
* An unchanged narrative never triggers an extra model call.

### 5.2 Logging

`pipeline_log.py` configures one `ai_pipeline` logger with a **stdout** handler
(Django's `runserver` does not configure root logging, so plain `logging.info`
would be swallowed). What you see per turn:

```
18:02:11 | INFO | ai_pipeline.event        | ========================================
 RECEIVE | state as stored by Django
   • stage             : ENRICHED_CONTENT
   • user_content      : finalize story draft
   • state             : {"narrative_version": 2, "extracted_version": 0, ...}
========================================================================
18:02:11 | INFO | ai_pipeline.orchestrator | → _phase_three(enriched_content=..., state={...})
18:02:11 | INFO | ai_pipeline.ollama       | llm call | model=llama3.2:3b temperature=0.1 constrained_json=True messages=2 prompt_chars=1911
18:02:12 | INFO | ai_pipeline.orchestrator | ← _phase_three [1904.3 ms] (Master JSON extraction complete …)
18:02:12 | INFO | ai_pipeline.event        | RESULT | state to persist on the Django session
```

Key lines to watch while debugging state drift:

```
master JSON is stale — re-extracting (extracted v2 vs narrative v3, reason=hub_entry)
master JSON rebuilt | reason=phase4_story_change narrative v4 characters=3
re-applied manual hub edits after extraction: applied=2 skipped=0
Phase 4 story-scope turn applied | narrative v4 | master JSON refreshed
```

`log_call` (on every phase, hub and slice handler) prints the arguments, the
return value and the duration; `ollama_driver` logs model, temperature, whether
constrained JSON was requested, prompt/response sizes and failures. Levels can be
changed without touching code:

```bash
AI_PIPELINE_LOG_LEVEL=DEBUG python manage.py runserver   # + prompts and replies
AI_PIPELINE_LOG_FILE=/tmp/pipeline.log python manage.py runserver
AI_PIPELINE_LOG_PREVIEW=800 AI_PIPELINE_LOG_LEVEL=DEBUG python manage.py runserver
```

---

## 6. Phases ↔ Django stages

`run_pipeline` returns one of the `StorySession.Stage` values, so the backend needs
no new choices or migrations.

| Spec phase | What happens | Stage returned |
|---|---|---|
| 0 — Prompt validation | Laya classifies the initial prompt; too vague → ask for more detail and stay put | `PROMPT_EVAL` |
| 1 — Clarification | Exactly two targeted questions from `llama3.2:3b`; the prompt is seeded as the working narrative | `ENRICHED_CONTENT` |
| 2 — Story chat | Answers merged into the narrative; then multi-turn prose generation, plus "make it darker"-style revisions | `ENRICHED_CONTENT` |
| 3 — Master JSON extraction | `TurnExtractionOutput` extracted with schema-constrained decoding → `json_output.master_json` | `JSON_GENERATION` |
| 4 — Enhancement hub | Unrestricted switching between Background / Scene / Characters, each edited against its own isolated schema slice and merged back | `CHARACTER_ENHANCEMENT`, `BACKGROUND_ENHANCEMENT`, `SCENE_DIALOGUE_ENHANCEMENT` |

Phase 3 is triggered by `action="finalize_stage"` (or a message like `finalize`), and
re-running it always rebuilds `master_json` from the current narrative.

### 6.1 Scope routing (Phase 4)

| Request | Target slice | Schema sent to the model |
|---|---|---|
| `scope="character"` + `target_id="char_02"` | `master_json.characters[target_id]` | `CharacterSceneInfo` |
| `scope="background"` | `master_json.background` (+ `environment` as context) | `BackgroundState` |
| `scope="scene"` | `master_json.scene` | `SceneState` |
| `scope="story"` | none — narrative chat that *updates* `enriched_content` and re-extracts `master_json` | — |
| `scope="auto"` / omitted | keyword intent classification | derived from the match |

Without an explicit scope the router also recognizes a bare character name
(`"Sasuke"`) as a character selection, and presents the isolated
single-paragraph `CHARACTER_SUMMARY_SYSTEM_PROMPT` summary.

---

## 7. API reference

Auth is JWT (`Authorization: Bearer <access>`).

| Method | Path | Body | Purpose |
|---|---|---|---|
| POST | `/api/auth/register/` | `{"name", "email", "password"}` | create account |
| POST | `/api/auth/login/` | `{"email", "password"}` | returns `access` / `refresh` |
| POST | `/api/auth/refresh/` | `{"refresh"}` | new access token |
| GET/POST | `/api/projects/` | project fields | list/create projects |
| GET | `/api/projects/<project_id>/story/` | — | fetch the session (messages) |
| POST | `/api/projects/<project_id>/story/` | `{"content": "..."}` | **one orchestrated turn** |
| POST | `/api/projects/<project_id>/story/finalize/` | — | finalize the draft: runs Phase 3 extraction and enters the enhancement hub |
| GET | `/api/health/` | — | liveness probe |

Example turn:

```bash
TOKEN=<access token from /api/auth/login/>
PROJECT=<project uuid>

curl -X POST "http://localhost:8000/api/projects/$PROJECT/story/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content": "A young alchemist in a desert city finds an artifact that freezes time."}'
```

The response is the serialized session (`id`, `project`, `status`, timestamps,
`messages`); the assistant reply is the last item in `messages`.

`run_pipeline` also accepts optional `action` (`"chat"`, `"finalize_stage"`,
`"character"`, `"background"`, `"scene"`), `scope` and `target_id` — the current
view forwards `content` and `action` only, so scope routing currently runs from
intent classification. Forwarding `scope`/`target_id` from the frontend requires
changes in `backend/` and `frontend/` (outside this folder).

---

## 8. Configuration

| Variable | Default | Where |
|---|---|---|
| `AI_PIPELINE_MODEL` | `llama3.2:3b` | `ollama_driver.py` — generation model |
| `OLLAMA_HOST` | `http://localhost:11434` | `ollama_driver.py` — Ollama server URL |
| `DJANGO_SECRET_KEY` | — (required) | `backend/.env` |
| `DJANGO_DEBUG` | `False` | `backend/.env` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,testserver` | `backend/.env` |
| `FRONTEND_URL` | `http://localhost:5173,http://localhost:5174` | `backend/.env` → CORS origins |
| `VITE_API_URL` | `http://localhost:8000/api` | `frontend/.env` |
| `AI_PIPELINE_LOG_LEVEL` | `INFO` | `pipeline_log.py` — `DEBUG` adds prompts/replies |
| `AI_PIPELINE_LOG_FILE` | — | `pipeline_log.py` — optional extra file sink |
| `AI_PIPELINE_LOG_PREVIEW` | `300` | `pipeline_log.py` — max chars per logged value |

Model paths inside the pipeline:

| Constant | File | Purpose |
|---|---|---|
| `MODEL_DIR` | `agents/laya_agent.py` | Laya model folder |
| `DEFAULT_MODEL` / `DEFAULT_BASE_URL` | `ollama_driver.py` | overridable via env vars above |
| `AI_PIPELINE_DIR` | `backend/apps/projects/story_views.py` | hard-coded absolute path to this folder |

---

## 9. Troubleshooting

**`Import failed: No module named 'pydantic'`** (printed by Django) — the pipeline
dependencies are missing from the venv running `manage.py`, so the view silently
uses its `Fallback response for stage '…'` stub. Install `pydantic` (plus `ollama`
or `langchain-ollama`) into the same venv and restart `runserver`.

**`FileNotFoundError: Model path not found` / `No module named 'torch'`** — the
Laya gatekeeper is unavailable. Expected if you skipped section 3.3; Phase 0 then
uses its heuristic fallback. Install `torch` + download the model to silence it.

**`No Ollama backend available`** — neither `ollama` nor `langchain_ollama` is
installed in the venv.

**`Connection refused` from the model** — `ollama serve` is not running, or
`OLLAMA_HOST` points elsewhere; verify with `curl http://localhost:11434/api/tags`.

**`The model returned malformed structured data…`** — extraction/enhancement
could not produce valid JSON for the schema. The turn is a no-op: session state is
preserved, just resend. Small models occasionally need a retry.

**The reply says "Your prompt needs a bit more detail…"** — Phase 0 rejected the
prompt. Add a character, setting or conflict, or lengthen it.

**`ValueError: Invalid stage transition…`** — only raised by
`StorySession.transition_to()`, which the story view does not call. Phase 4
deliberately allows jumping between enhancement scopes (per the spec), so the
returned stage follows the active scope rather than `ALLOWED_TRANSITIONS`.

**Path errors after moving the repo** — update the hard-coded `AI_PIPELINE_DIR`
in `backend/apps/projects/story_views.py` and `MODEL_DIR` in
`agents/laya_agent.py`.

**Which folder is the pipeline?** Only `ai_pipeline/` (underscore). The sibling
`AI pipeline/` directory is a legacy empty scaffold and is not imported anywhere.

---

## 10. What has been verified

There is no automated test suite in the repository. The pipeline logic was
validated with stubbed end-to-end runs (fake Laya + fake Ollama) simulating the
exact Django call signature:

* lifecycle + routing: prompt rejection, clarification, story chat,
  finalize → extraction, character selection/editing with identity re-pinning,
  background and scene editing, free scope switching, unresolved character
  targets, model-failure and malformed-JSON recovery, legacy-stage recovery
  — 78 assertions green;
* state synchronisation: finalize re-extraction, story changes made from inside
  the hub, version/hash agreement, manual hub edits surviving re-extraction,
  re-finalizing a changed draft, no redundant extraction for unchanged text, and
  refreshing state written by an older build — 30 assertions green;
* the real HTTP flow (`POST /story/`, `POST /story/finalize/`) with Django 5.2 +
  DRF against a throwaway SQLite DB and the same stubbed models: prompt →
  clarification → finalize/extraction → story change → character edit → story
  change again, asserting the persisted `stage` / `enriched_content` /
  `json_output` after every request — 19 assertions green.

Live model quality and the React round-trip still have to be confirmed on a
machine with Ollama and the real backend dependencies installed (section 4.1).
