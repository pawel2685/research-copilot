"""Stub of the search function: ranks saved passages by word overlap.

Stands in for the real retrieval (B) so the pipeline and the evaluation can run
without it. The passages cover the five papers used in evals/questions.py.
"""
from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path

from contracts import Chunk

_FIXTURE = Path(__file__).with_name("sample_chunks.json")
_STOPWORDS = frozenset(
    {"a", "an", "and", "are", "as", "by", "do", "does", "for", "how", "in", "is",
     "it", "its", "of", "on", "or", "that", "the", "this", "to", "what", "with"}
)


@cache
def _load_chunks() -> tuple[Chunk, ...]:
    raw = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return tuple(Chunk(**item) for item in raw)


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower())) - _STOPWORDS


def search(query: str, k: int = 8, hybrid: bool = True) -> list[Chunk]:
    """Return up to k passages that share words with the query, best first.

    `hybrid` is accepted to match the contract and is ignored by the stub.
    """
    query_words = _words(query)
    scored = []
    for chunk in _load_chunks():
        score = len(query_words & _words(chunk.text))
        if score > 0:
            scored.append(chunk.model_copy(update={"score": float(score)}))
    scored.sort(key=lambda chunk: chunk.score, reverse=True)
    return scored[:k]
