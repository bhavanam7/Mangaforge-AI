"""
AI Pipeline Logging
===================
Single place that configures logging for every module inside `ai_pipeline/`.

Why a dedicated module
----------------------
Django's `runserver` does not configure a root logging handler, so plain
``logging.info(...)`` calls from the pipeline would be dropped. This module
attaches a **stdout** handler (the same stream the pipeline's ``print()`` calls
already use), which means every record shows up in the terminal next to the
backend output.

Configuration (all optional, read from the environment)
-------------------------------------------------------
    AI_PIPELINE_LOG_LEVEL    DEBUG | INFO | WARNING | ERROR   (default INFO)
    AI_PIPELINE_LOG_FILE     path to also append records to a file
    AI_PIPELINE_LOG_PREVIEW  max characters per value preview   (default 300)

Usage
-----
    from pipeline_log import get_logger, log_call, banner, short

    LOG = get_logger("orchestrator")

    @log_call()                      # logs args -> result + duration
    def _phase_two(...): ...

    banner("TURN RESULT", stage=..., reply=...)
    LOG.debug("raw payload: %s", short(payload))
"""

from __future__ import annotations

import functools
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

LOGGER_NAME = "ai_pipeline"

DEFAULT_LEVEL = os.environ.get("AI_PIPELINE_LOG_LEVEL", "INFO").upper()
LOG_FILE = os.environ.get("AI_PIPELINE_LOG_FILE", "").strip()


def _env_int(name: str, fallback: int) -> int:
    try:
        return int(os.environ.get(name, "") or fallback)
    except (TypeError, ValueError):
        return fallback


PREVIEW_CHARS = _env_int("AI_PIPELINE_LOG_PREVIEW", 300)

_configured = False


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def _configure() -> None:
    """Idempotently install the stdout (and optional file) handler."""
    global _configured
    if _configured:
        return

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(getattr(logging, DEFAULT_LEVEL, logging.INFO))
    logger.propagate = False

    if not logger.handlers:
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-7s | %(name)-22s | %(message)s",
            datefmt="%H:%M:%S",
        )
        stream = logging.StreamHandler(sys.stdout)
        stream.setFormatter(formatter)
        logger.addHandler(stream)

        if LOG_FILE:
            try:
                Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
                file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)
            except OSError as exc:  # never let logging break the pipeline
                logger.warning("could not open log file %s: %s", LOG_FILE, exc)

    _configured = True


def get_logger(name: str = "pipeline") -> logging.Logger:
    """Return a namespaced logger (``ai_pipeline.<name>``) with handlers installed."""
    _configure()
    if not name or name == LOGGER_NAME:
        return logging.getLogger(LOGGER_NAME)
    return logging.getLogger(f"{LOGGER_NAME}.{name}")


# ---------------------------------------------------------------------------
# Value previews
# ---------------------------------------------------------------------------

def short(value: Any, limit: Optional[int] = None) -> str:
    """Compact, single-line, length-limited representation of any value."""
    limit = limit or PREVIEW_CHARS
    try:
        if isinstance(value, (dict, list, tuple)):
            text = json.dumps(value, ensure_ascii=False, default=str)
        else:
            text = str(value)
    except (TypeError, ValueError):
        text = repr(value)
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return f"{text[:limit]}… ({len(text)} chars)"


def state_snapshot(state: Any) -> Dict[str, Any]:
    """Small, log-safe summary of a pipeline state dict (never dumps master_json)."""
    if not isinstance(state, dict):
        return {"type": type(state).__name__}

    master = state.get("master_json")
    master = master if isinstance(master, dict) else {}
    characters = master.get("characters")
    overrides = state.get("manual_overrides")

    return {
        "narrative_version": state.get("narrative_version"),
        "extracted_version": state.get("extracted_version"),
        "master_json_stale": state.get("master_json_stale"),
        "active_scope": state.get("active_scope"),
        "target_id": state.get("target_id"),
        "characters": len(characters) if isinstance(characters, list) else 0,
        "has_background": bool(master.get("background")),
        "has_scene": bool(master.get("scene")),
        "override_slices": len(overrides) if isinstance(overrides, dict) else 0,
        "awaiting_clarifications": state.get("awaiting_clarifications"),
    }


# ---------------------------------------------------------------------------
# Terminal banners
# ---------------------------------------------------------------------------

def banner(title: str, level: int = logging.INFO, **fields: Any) -> None:
    """
    Log a boxed block of key/value pairs.

    Records go through the logger, whose handler writes to stdout, so the block
    appears in the terminal exactly where the pipeline is executing (Django
    ``runserver`` output, ``python main.py``, or a test run).
    """
    lines = [f"{'=' * 72}", f" {title}"]
    for key, value in fields.items():
        lines.append(f"   • {key:<18}: {short(value)}")
    lines.append("=" * 72)
    get_logger("event").log(level, "\n".join(lines))


# ---------------------------------------------------------------------------
# Call tracing
# ---------------------------------------------------------------------------

def _args_preview(args: tuple, kwargs: Dict[str, Any], limit: int) -> str:
    parts = [short(arg, limit) for arg in args]
    parts.extend(f"{key}={short(value, limit)}" for key, value in kwargs.items())
    return ", ".join(parts)


def _result_preview(result: Any, limit: int) -> str:
    if isinstance(result, tuple):
        return "(" + ", ".join(short(part, limit) for part in result) + ")"
    return short(result, limit)


def log_call(
    name: Optional[str] = None,
    level: int = logging.INFO,
    preview: Optional[int] = None,
) -> Callable:
    """
    Decorator that logs every call of a state function: its arguments, its
    return value and how long it took (plus a full traceback on failure).

    This is what makes each state-machine transition traceable end to end:

        → _phase_two(user_content, state, enriched_content)
        ← _phase_two [812.4 ms] (reply, 'ENRICHED_CONTENT', ...)
    """
    limit = preview or PREVIEW_CHARS

    def decorator(func: Callable) -> Callable:
        logger = get_logger(func.__module__.rsplit(".", 1)[-1])
        label = name or func.__name__

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            started = time.perf_counter()
            logger.log(level, "→ %s(%s)", label, _args_preview(args, kwargs, limit))
            try:
                result = func(*args, **kwargs)
            except Exception:
                logger.exception(
                    "✗ %s raised after %.1f ms", label, (time.perf_counter() - started) * 1000
                )
                raise
            logger.log(
                level,
                "← %s [%.1f ms] %s",
                label,
                (time.perf_counter() - started) * 1000,
                _result_preview(result, limit),
            )
            return result

        return wrapper

    return decorator
