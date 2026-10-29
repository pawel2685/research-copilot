"""Baseline pipeline: plan, search, compress, write, check. No ADK, no network.

The writer is a plain template on purpose. The real writing comes with the ADK
agents.
"""
from __future__ import annotations

from collections.abc import Sequence

from agents.deadline import Deadline
from agents.passages import compress_chunks
from agents.skipping import CriticFn, PlannerFn, critique, is_verified, plan_questions
from contracts import Chunk, Report, RunConfig, SearchFn
from stubs.search import search as stub_search

NO_SOURCES_MESSAGE = "No sources were found for this question."


def merge_chunks(results: Sequence[Sequence[Chunk]]) -> list[Chunk]:
    """Merge search results, drop duplicates (same paper and text), best score first."""
    ordered = sorted(
        (chunk for chunks in results for chunk in chunks),
        key=lambda chunk: chunk.score,
        reverse=True,
    )
    seen: set[tuple[str, str]] = set()
    merged: list[Chunk] = []
    for chunk in ordered:
        key = (chunk.paper_id, chunk.text)
        if key not in seen:
            seen.add(key)
            merged.append(chunk)
    return merged


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
    planner_fn: PlannerFn | None = None,
    critic_fn: CriticFn | None = None,
    deadline: Deadline | None = None,
) -> Report:
    """Answer a question: plan, search, compress, write, check.

    The Planner and the Critic are skipped when they are missing, switched off in
    `cfg` or short of time. A report is always returned.
    """
    cfg = cfg or RunConfig()
    deadline = deadline or Deadline.after(cfg.time_budget_s)
    sub_questions = plan_questions(question, planner_fn, deadline, cfg)
    chunks = merge_chunks(
        [search_fn(sub_question, hybrid=cfg.hybrid) for sub_question in sub_questions]
    )
    kept = compress_chunks(chunks, cfg.compress_budget_words)
    report = build_report(question, kept)
    result = critique(report, kept, critic_fn, deadline, cfg)
    return report.model_copy(update={"verified": is_verified(result)})
