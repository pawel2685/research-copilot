"""Baseline pipeline: search, compress, write. Plain Python, no ADK, no network.

The writer is a plain template on purpose. The real writing comes with the ADK
agents.
"""
from __future__ import annotations

from collections.abc import Sequence

from agents.passages import compress_chunks
from contracts import Chunk, Report, RunConfig, SearchFn
from stubs.search import search as stub_search

NO_SOURCES_MESSAGE = "No sources were found for this question."


def build_report(question: str, chunks: Sequence[Chunk]) -> Report:
    """Write a report from the passages. `verified` is False: no Critic ran."""
    if not chunks:
        return Report(
            question=question,
            markdown=f"# {question}\n\n{NO_SOURCES_MESSAGE}\n",
            sources=[],
            verified=False,
        )

    sources: list[str] = []
    source_lines: list[str] = []
    for chunk in chunks:
        if chunk.paper_id not in sources:
            sources.append(chunk.paper_id)
            source_lines.append(f"- {chunk.source_url or chunk.paper_id}")

    findings = [f"- {chunk.text} [{chunk.paper_id}]" for chunk in chunks]
    markdown = "\n".join(
        [f"# {question}", "", "## Findings", *findings, "", "## Sources", *source_lines]
    )
    return Report(question=question, markdown=markdown + "\n", sources=sources, verified=False)


def answer(
    question: str,
    cfg: RunConfig | None = None,
    *,
    search_fn: SearchFn = stub_search,
) -> Report:
    """Answer a question: search, compress to the word budget, write the report."""
    cfg = cfg or RunConfig()
    chunks = search_fn(question, hybrid=cfg.hybrid)
    kept = compress_chunks(chunks, cfg.compress_budget_words)
    return build_report(question, kept)
