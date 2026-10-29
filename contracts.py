"""Shared contracts for Research Copilot.

Owned by the whole team. Change this file only in a separate pull request
that every team member approves: all modules depend on these names.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    """A passage from a paper."""

    paper_id: str  # arXiv id, e.g. "2005.11401" (evals compare these ids)
    text: str
    score: float = 0.0
    source_url: str = ""


class Report(BaseModel):
    """What the system returns for one question."""

    question: str
    markdown: str
    sources: list[str] = Field(default_factory=list)
    # True only if the Critic ran and approved (CriticResult.approved is True)
    verified: bool = False


class RunConfig(BaseModel):
    """Switches for one run. The same switches drive the ablation (E0..E4)."""

    use_planner: bool = True
    use_critic: bool = True
    hybrid: bool = True
    # Word budget for context compression (whitespace-separated words, not
    # model tokens). None means no compression.
    compress_budget_words: int | None = 3000
    time_budget_s: float = 90.0  # example value, tune later


class SearchFn(Protocol):
    """Provided by retrieval/."""

    def __call__(self, query: str, k: int = 8, hybrid: bool = True) -> list[Chunk]: ...


class CompressFn(Protocol):
    """Implemented by context.compression.compress.

    Takes plain chunk texts and a word budget, returns the trimmed texts.
    Empty chunks are dropped, so do not rely on result[i] matching chunks[i].
    """

    def __call__(self, chunks: Sequence[str], budget: int) -> list[str]: ...