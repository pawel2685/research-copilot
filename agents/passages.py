"""Helpers for working with passages (`Chunk` objects) in the pipeline."""
from __future__ import annotations

from collections.abc import Sequence

from contracts import Chunk
from context.compression import compress


def compress_chunks(chunks: Sequence[Chunk], budget_words: int | None) -> list[Chunk]:
    """Compress chunks to a word budget while keeping their ids and urls.

    `compress` works on plain texts and drops empty ones, so its result cannot be
    mapped back by index when empty texts are present. Empty chunks are dropped here
    first. The result of `compress` is then a prefix of the remaining texts, the last
    one possibly shortened. `None` means no compression. The input is not modified.
    """
    remaining = [chunk for chunk in chunks if chunk.text.split()]
    if budget_words is None:
        return remaining
    texts = compress([chunk.text for chunk in remaining], budget_words)
    return [
        remaining[i].model_copy(update={"text": text}) for i, text in enumerate(texts)
    ]
