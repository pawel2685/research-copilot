"""Disk cache of model responses, to protect the free-tier limits.

Attached to an agent as `before_model_callback` and `after_model_callback`. On a hit
the stored response is returned, so the model is not called. One JSON file per key.

- `LLM_CACHE_DIR`: the cache directory, `.cache/llm` by default.
- `LLM_CACHE=off`: disables reading and writing.

Caching distorts measurements: a cached answer comes back at once and costs no tokens.
Use the cache while developing and repeating runs, and set `LLM_CACHE=off` for the
measured experiment runs.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse

DEFAULT_CACHE_DIR = ".cache/llm"

# Key of a request that was a miss, waiting for its response: (invocation, agent).
_pending: dict[tuple[str, str], str] = {}


def cache_enabled() -> bool:
    """False when `LLM_CACHE=off`. Read at every call, so it can change at run time."""
    return os.getenv("LLM_CACHE", "on").strip().lower() != "off"


def cache_dir() -> Path:
    return Path(os.getenv("LLM_CACHE_DIR") or DEFAULT_CACHE_DIR)


def cache_key(llm_request: LlmRequest) -> str:
    """SHA-256 of the model name and everything that goes into the request.

    That is the contents (the conversation), and the config with the system
    instruction, the tools and the output schema.
    """
    payload: dict[str, Any] = {
        "model": llm_request.model or "",
        "contents": [
            content.model_dump(mode="json", exclude_none=True)
            for content in llm_request.contents
        ],
        "config": llm_request.config.model_dump(mode="json", exclude_none=True),
    }
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _path(key: str) -> Path:
    return cache_dir() / f"{key}.json"


def _load(key: str) -> LlmResponse | None:
    """The stored response, or None when there is none or the file is unreadable."""
    try:
        return LlmResponse.model_validate(json.loads(_path(key).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None


def _store(key: str, response: LlmResponse) -> None:
    path = _path(key)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(
            json.dumps(response.model_dump(mode="json", exclude_none=True)),
            encoding="utf-8",
        )
        os.replace(temp, path)
    except OSError:
        pass  # a cache that cannot be written is only slower, never wrong


def before_model(ctx: CallbackContext, llm_request: LlmRequest) -> LlmResponse | None:
    """Return the stored response on a hit, so ADK skips the model call."""
    if not cache_enabled():
        return None
    key = cache_key(llm_request)
    cached = _load(key)
    if cached is not None:
        return cached
    _pending[(ctx.invocation_id, ctx.agent_name)] = key
    return None


def after_model(ctx: CallbackContext, llm_response: LlmResponse) -> LlmResponse | None:
    """Store the response of a miss. Always returns None, the response is unchanged."""
    key = _pending.pop((ctx.invocation_id, ctx.agent_name), None)
    if (
        key is not None
        and cache_enabled()
        and llm_response.content is not None
        and not llm_response.partial
        and not llm_response.error_code
    ):
        _store(key, llm_response)
    return None


def _as_list(callbacks: Any) -> list:
    if callbacks is None:
        return []
    return list(callbacks) if isinstance(callbacks, Sequence) else [callbacks]


def with_cache(agent: LlmAgent) -> LlmAgent:
    """Copy of `agent` with the cache in front of its model callbacks.

    Both cache callbacks run first, so a hit skips the rest, and a miss is stored as
    the model returned it. The agent that was passed in is not modified.
    """
    return agent.model_copy(
        update={
            "before_model_callback": [before_model, *_as_list(agent.before_model_callback)],
            "after_model_callback": [after_model, *_as_list(agent.after_model_callback)],
        }
    )
