
from collections.abc import Sequence


def compress(chunks: Sequence[str], budget: int) -> list[str]:
    """Trim text chunks to a deterministic whitespace-token budget.

    Complete chunks are preserved when they fit. If the budget ends
    inside a chunk, only the fitting prefix of that chunk is retained.

    Note:
        Whitespace-separated words are used as a lightweight token
        estimate. They are not exact Gemini model token counts.
    """
    if isinstance(budget, bool) or not isinstance(budget, int):
        raise TypeError("budget must be an integer")

    if budget < 0:
        raise ValueError("budget must not be negative")

    if isinstance(chunks, (str, bytes)):
            raise TypeError("chunks must be a sequence of strings")

    result: list[str] = []
    remaining = budget

    for chunk in chunks:
        if not isinstance(chunk, str):
            raise TypeError("every chunk must be a string")

        words = chunk.split()

        if not words:
            continue

        if len(words) <= remaining:
            result.append(chunk)
            remaining -= len(words)
            continue

        if remaining > 0:
            result.append(" ".join(words[:remaining]))

        break

    return result
