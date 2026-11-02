"""The public entry points: `answer(question, cfg) -> Report` and `answer_with_stats`.

Run the ADK pipeline (`agents/runner.py`) and convert its result into a `Report`.
`main.py` calls `answer`, the evaluation harness calls `answer_with_stats`.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time

from google.adk.agents import LlmAgent

from agents.cache import cache_enabled
from agents.critic import create_critic_agent
from agents.orchestrator import notes_keys
from agents.runner import PipelineResult, run_pipeline
from agents.stats import RunStats
from contracts import Report, RunConfig, SearchFn

# TODO(B): replace the stub with B's search function from `retrieval/` once it is
# merged, and pass B's Planner agent as the default `planner` of `answer`.
from stubs.search import search as default_search

logger = logging.getLogger(__name__)

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


def _run(
    question: str,
    cfg: RunConfig | None,
    search_fn: SearchFn,
    planner: LlmAgent | None,
    critic: LlmAgent | None,
) -> tuple[Report, RunStats]:
    cfg = cfg or RunConfig()
    if critic is None and cfg.use_critic:
        critic = create_critic_agent()
    start = time.perf_counter()
    result = asyncio.run(
        run_pipeline(question, cfg, search_fn=search_fn, planner=planner, critic=critic)
    )
    stats = RunStats(
        retrieved_source_ids=result.retrieved_source_ids,
        llm_calls=result.llm_calls,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_seconds=time.perf_counter() - start,
    )
    return to_report(question, result), stats


def answer_with_stats(
    question: str,
    cfg: RunConfig | None = None,
    *,
    search_fn: SearchFn = default_search,
    planner: LlmAgent | None = None,
    critic: LlmAgent | None = None,
) -> tuple[Report, RunStats]:
    """Answer a research question with the whole pipeline, and measure the run.

    The Critic is C's agent unless another one is given. The Planner and the Critic are
    left out when `cfg` switches them off, and skipped when time runs short.
    `Report.verified` is true only when the Critic ran and approved the report.

    This is the entry point for the evaluation. Set `LLM_CACHE=off` for measured runs:
    a cached answer comes back at once and costs no tokens, so a warning is logged
    when the cache is on.
    """
    if cache_enabled():
        logger.warning(
            "LLM_CACHE is not 'off': cached answers distort latency and token counts."
        )
    return _run(question, cfg, search_fn, planner, critic)


def answer(
    question: str,
    cfg: RunConfig | None = None,
    *,
    search_fn: SearchFn = default_search,
    planner: LlmAgent | None = None,
    critic: LlmAgent | None = None,
) -> Report:
    """Answer a research question. Like `answer_with_stats`, but only the report.

    The cache stays on here, it is meant for development and for the app.
    """
    return _run(question, cfg, search_fn, planner, critic)[0]
