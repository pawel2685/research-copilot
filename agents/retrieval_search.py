"""Adapter: B's retrieval as a `SearchFn`.

`retrieval.Retriever.search` returns dictionaries and takes `top_k` and `mode`. The
pipeline expects `search(query, k, hybrid) -> list[Chunk]` (see `contracts.SearchFn`).
This module converts between the two and does not change B's code.
"""
from __future__ import annotations

import re
from functools import cache
from pathlib import Path

from contracts import Chunk
from retrieval import Retriever, load_corpus
from retrieval.search import DEFAULT_DATA

# B keeps versioned ids (`2005.11401v4`), but `Chunk.paper_id` is the plain arXiv id,
# because the evaluation metrics compare plain ids.
_VERSION_SUFFIX = re.compile(r"v\d+$")


@cache
def _retriever(data_dir: Path) -> Retriever:
    """Load the corpus once per data directory. Building the index is slow."""
    corpus_path = data_dir / "corpus.jsonl"
    if not corpus_path.exists():
        raise RuntimeError(
            f"No paper corpus at {corpus_path}. Build it first: "
            "python -m retrieval fetch --query '<arXiv query>' && python -m retrieval index"
        )
    return Retriever(load_corpus(corpus_path), data_dir / "chroma")


def to_chunk(item: dict) -> Chunk:
    """Convert one result of `Retriever.search` into a `Chunk`."""
    return Chunk(
        paper_id=_VERSION_SUFFIX.sub("", item["arxiv_id"]),
        text=item["text"],
        score=float(item["score"]),
        source_url=item["url"],
    )


def search(
    query: str, k: int = 8, hybrid: bool = True, *, data_dir: Path = DEFAULT_DATA
) -> list[Chunk]:
    """Search B's paper corpus and return up to k passages, best first.

    `hybrid=True` fuses BM25 and vector search. `hybrid=False` uses vector search only,
    which is the baseline E0 (see `evals/experiment_configs.py`).
    """
    mode = "hybrid" if hybrid else "vector"
    return [to_chunk(item) for item in _retriever(Path(data_dir)).search(query, k, mode)]
