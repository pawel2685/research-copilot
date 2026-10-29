"""The public entry point: `answer(question, cfg) -> Report`.

Runs the ADK pipeline (`agents/runner.py`) and converts its result into a `Report`.
The evaluation harness and `main.py` call this function.
"""
from __future__ import annotations

import asyncio
import re

from google.adk.agents import LlmAgent

from agents.critic import create_critic_agent
from agents.orchestrator import notes_keys
from agents.runner import PipelineResult, run_pipeline
from contracts import Report, RunConfig, SearchFn

# TODO(B): replace the stub with B's search function from `retrieval/` once it is
# merged, and pass B's Planner agent as the default `planner` of `answer`.
from stubs.search import search as default_search

# A paper id in square brackets, as the Reader writes it: `[2005.11401]`.
_CITED_ID = re.compile(r"\[(\d{4}\.\d{4,5})(?:v\d+)?\]")


def cited_paper_ids(result: PipelineResult) -> list[str]:
    """Unique paper ids cited in the notes of the branches, in order of appearance."""
    ids: list[str] = []
    for key in notes_keys():
        for paper_id in _CITED_ID.findall(str(result.state.get(key) or "")):
            if paper_id not in ids:
                ids.append(paper_id)
    return ids


def to_report(question: str, result: PipelineResult) -> Report:
    """Convert a pipeline result into a `Report`."""
    return Report(
        question=question,
        markdown=result.report_markdown,
        sources=cited_paper_ids(result),
        verified=result.verified,
    )


def answer(
    question: str,
    cfg: RunConfig | None = None,
    *,
    search_fn: SearchFn = default_search,
    planner: LlmAgent | None = None,
    critic: LlmAgent | None = None,
) -> Report:
    """Answer a research question with the whole pipeline.

    The Critic is C's agent unless another one is given. The Planner and the Critic are
    left out when `cfg` switches them off, and skipped when time runs short.
    `Report.verified` is true only when the Critic ran and approved the report.
    """
    cfg = cfg or RunConfig()
    if critic is None and cfg.use_critic:
        critic = create_critic_agent()
    result = asyncio.run(
        run_pipeline(question, cfg, search_fn=search_fn, planner=planner, critic=critic)
    )
    return to_report(question, result)
