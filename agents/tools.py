"""Tools for the ADK agents."""
from __future__ import annotations

from collections.abc import Callable

from agents.passages import compress_chunks
from contracts import SearchFn


def make_search_tool(
    search_fn: SearchFn,
    *,
    hybrid: bool = True,
    budget_words: int | None = None,
    k: int = 8,
) -> Callable[[str], list[dict]]:
    """Build the search tool for the Searcher.

    Compression happens inside the tool, so the Reader only ever sees passages within
    the word budget.
    """

    def search_papers(query: str) -> list[dict]:
        """Search the paper corpus and return the best matching passages.

        Args:
            query: What to look for, in plain English, for example a research
                question or a few key terms.

        Returns:
            A list of passages. Each has the arXiv `paper_id`, the passage `text` and
            the `source_url` of the paper.
        """
        chunks = compress_chunks(search_fn(query, k=k, hybrid=hybrid), budget_words)
        return [
            {"paper_id": c.paper_id, "text": c.text, "source_url": c.source_url}
            for c in chunks
        ]

    return search_papers
