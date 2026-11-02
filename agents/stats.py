"""Measurements of one run, for the evaluation (C fills its records from them)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contracts import Chunk, SearchFn


@dataclass(frozen=True)
class RunStats:
    """What one run cost. The fields match `EvaluationRecord` of the evaluation."""

    # Papers the search returned, best first, each once. This is the retrieval
    # output before compression, which is what Recall@k is computed on.
    retrieved_source_ids: tuple[str, ...]
    llm_calls: int
    input_tokens: int
    output_tokens: int
    latency_seconds: float


@dataclass
class UsageCounter:
    """Adds up the model usage of the ADK events of a run."""

    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, event: Any) -> None:
        """Count one model call for an event that carries usage data.

        Events without usage data (tool results, skipped agents) and partial
        streaming chunks are not counted. Thinking tokens count as output.
        """
        usage = getattr(event, "usage_metadata", None)
        if usage is None or getattr(event, "partial", None):
            return
        self.llm_calls += 1
        self.input_tokens += usage.prompt_token_count or 0
        self.output_tokens += (usage.candidates_token_count or 0) + (
            usage.thoughts_token_count or 0
        )


class RecordingSearch:
    """Wraps a search function and remembers which papers it returned."""

    def __init__(self, search_fn: SearchFn) -> None:
        self.search_fn = search_fn
        self.source_ids: list[str] = []

    def __call__(self, query: str, k: int = 8, hybrid: bool = True) -> list[Chunk]:
        chunks = self.search_fn(query, k=k, hybrid=hybrid)
        for chunk in chunks:
            if chunk.paper_id not in self.source_ids:
                self.source_ids.append(chunk.paper_id)
        return chunks
