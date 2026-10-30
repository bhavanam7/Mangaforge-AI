"""
Ollama Driver
=============
Wrapper module required by the technical specification (Section 6):

    "Ollama Driver: Implement a wrapper module calling ollama.chat()
     with format=Schema.model_json_schema()."

Every LLM call in the pipeline goes through this module so that:

* The model name is configured in exactly one place
  (``AI_PIPELINE_MODEL`` env var, default ``llama3.2:3b``).
* Structured outputs are requested with JSON-schema constrained decoding
  (``format=<schema>``) instead of relying on the model obeying the prompt.
* The backend (official ``ollama`` package, or ``langchain_ollama`` which is
  already used elsewhere in this project) is chosen at call time, so the
  pipeline still imports cleanly when one of them is missing.

Public API:
    complete(messages, schema=None, model=None, temperature=0.2) -> str
    complete_structured(messages, schema, ...) -> Optional[dict]
    extract_json(text) -> Optional[dict]
"""

import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Sequence, Union

from pydantic import BaseModel

import pipeline_log

LOG = pipeline_log.get_logger("ollama")

DEFAULT_MODEL = os.environ.get("AI_PIPELINE_MODEL", "llama3.2:3b")
DEFAULT_BASE_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

Message = Dict[str, str]  # {"role": "system" | "user" | "assistant", "content": str}

# Minimum number of characters before we trust a model to have emitted JSON.
_MIN_JSON_CHARS = 2


# ---------------------------------------------------------------------------
# Schema formatting
# ---------------------------------------------------------------------------

def resolve_format(schema: Any) -> Optional[Union[str, Dict[str, Any]]]:
    """Turn a pydantic model / dict / literal into the Ollama ``format`` value."""
    if schema is None:
        return None
    if isinstance(schema, dict):
        return schema
    if isinstance(schema, str):
        return schema
    if isinstance(schema, type) and issubclass(schema, BaseModel):
        return schema.model_json_schema()
    # e.g. an already-instantiated pydantic model
    model_cls = type(schema)
    if issubclass(model_cls, BaseModel):
        return model_cls.model_json_schema()
    return None


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------

def _has_module(name: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _content_from_ollama(response: Any) -> str:
    """ollama.chat() returns a ChatResponse supporting both attr and item access."""
    try:
        content = response["message"]["content"]
    except (TypeError, KeyError, IndexError):
        content = getattr(getattr(response, "message", None), "content", None)
    if content is None:
        raise RuntimeError(f"Ollama returned no message content: {response!r}")
    return str(content)


def _chat_with_ollama(
    model: str,
    messages: Sequence[Message],
    fmt: Optional[Union[str, Dict[str, Any]]],
    temperature: float,
) -> str:
    import ollama  # official SDK -> ollama.chat()

    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": list(messages),
        "options": {"temperature": temperature},
    }
    if fmt is not None:
        kwargs["format"] = fmt
    response = ollama.chat(**kwargs)
    return _content_from_ollama(response)


def _chat_with_langchain(
    model: str,
    messages: Sequence[Message],
    fmt: Optional[Union[str, Dict[str, Any]]],
    temperature: float,
) -> str:
    """Fallback backend: langchain_ollama.ChatOllama (already a project dependency)."""
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    from langchain_ollama import ChatOllama

    mapping = {
        "system": SystemMessage,
        "user": HumanMessage,
        "assistant": AIMessage,
    }
    lc_messages = []
    for message in messages:
        cls = mapping.get(message.get("role", "user"), HumanMessage)
        lc_messages.append(cls(content=str(message.get("content", ""))))

    llm_kwargs: Dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "base_url": DEFAULT_BASE_URL,
    }
    if fmt is not None:
        llm_kwargs["format"] = fmt
    llm = ChatOllama(**llm_kwargs)
    response = llm.invoke(lc_messages)
    content = getattr(response, "content", response)
    if isinstance(content, list):  # multimodal content blocks
        content = "".join(
            part if isinstance(part, str) else str(part.get("text", ""))
            for part in content
        )
    return str(content)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def complete(
    messages: Sequence[Message],
    schema: Any = None,
    model: Optional[str] = None,
    temperature: float = 0.2,
) -> str:
    """
    Run one chat completion and return the raw text.

    ``messages`` is a list of {"role": ..., "content": ...} dicts.
    When ``schema`` is provided the request uses constrained JSON decoding
    (``format=Schema.model_json_schema()``).
    """
    model = model or DEFAULT_MODEL
    fmt = resolve_format(schema)
    prompt_chars = sum(len(str(message.get("content", ""))) for message in messages)

    LOG.info(
        "llm call | model=%s temperature=%s constrained_json=%s messages=%s prompt_chars=%s",
        model,
        temperature,
        fmt is not None,
        len(messages),
        prompt_chars,
    )
    LOG.debug(
        "llm prompt | %s",
        [(m.get("role"), pipeline_log.short(m.get("content"), 400)) for m in messages],
    )

    started = time.perf_counter()
    try:
        print("LLM calling stage finally for the json")
        if _has_module("ollama"):
            text, backend = _chat_with_ollama(model, messages, fmt, temperature), "ollama"
        elif _has_module("langchain_ollama"):
            text, backend = (
                _chat_with_langchain(model, messages, fmt, temperature),
                "langchain_ollama",
            )
        else:
            raise RuntimeError(
                "No Ollama backend available. Install the 'ollama' package "
                "(pip install ollama) or 'langchain_ollama', and make sure the "
                "Ollama server is running with the model pulled."
            )
    except Exception:
        LOG.exception(
            "llm call failed | model=%s after %.1f ms",
            model,
            (time.perf_counter() - started) * 1000,
        )
        raise

    LOG.info(
        "llm reply | backend=%s model=%s reply_chars=%s elapsed_ms=%.1f",
        backend,
        model,
        len(text),
        (time.perf_counter() - started) * 1000,
    )
    LOG.debug("llm reply preview | %s", pipeline_log.short(text, 600))
    return text


def build_messages(
    system: Optional[str] = None,
    user: Optional[str] = None,
    history: Optional[Sequence[Message]] = None,
) -> List[Message]:
    """Assemble a message list from an optional system prompt, history and user turn."""
    messages: List[Message] = []
    if system:
        messages.append({"role": "system", "content": system})
    if history:
        messages.extend(dict(m) for m in history)
    if user:
        messages.append({"role": "user", "content": user})
    return messages


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Best-effort extraction of the first JSON object from model output."""
    if not text or len(text.strip()) < _MIN_JSON_CHARS:
        return None
    candidate = text.strip()

    fence = re.search(r"```(?:json|JSON)?\s*(.*?)```", candidate, re.S)
    if fence:
        candidate = fence.group(1).strip()

    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None
    except (json.JSONDecodeError, ValueError):
        pass

    start, end = candidate.find("{"), candidate.rfind("}")
    if start != -1 and end > start:
        try:
            parsed = json.loads(candidate[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except (json.JSONDecodeError, ValueError):
            return None
    return None


def complete_structured(
    messages: Sequence[Message],
    schema: Any,
    model: Optional[str] = None,
    temperature: float = 0.1,
    retries: int = 1,
) -> Optional[Dict[str, Any]]:
    """
    Run a schema-constrained completion and return the parsed JSON dict.

    Returns ``None`` when the model could not be coerced into valid JSON after
    ``retries`` repair attempts. The schema itself is enforced by the caller
    (pydantic validation), so the returned dict is only *probably* conformant.
    """
    fmt = resolve_format(schema)
    if fmt is None:
        raise ValueError("complete_structured requires a pydantic schema or dict schema")

    attempt_messages = list(messages)
    for _ in range(max(1, retries) + 1):
        raw = complete(
            attempt_messages, schema=fmt, model=model, temperature=temperature
        )
        parsed = extract_json(raw)
        if parsed is not None:
            return parsed
        # Repair attempt: remind the model about the required shape.
        print("LLm didnt generated the json.. and gave parsed:- ", parsed)
        attempt_messages = attempt_messages + [
            {"role": "assistant", "content": raw or ""},
            {
                "role": "user",
                "content": "That was not valid JSON. Reply with ONLY a single valid "
                "JSON object matching the required schema. No prose, no code fences.",
            },
        ]
    return None
