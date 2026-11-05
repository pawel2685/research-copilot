
"""Single-call LLM baseline for experiment E0."""

from __future__ import annotations

import asyncio
import time

from google.adk.agents import LlmAgent

from agents.config import load_models
from agents.orchestrator import harden_agent
from agents.retrieval_search import search as default_search
from agents.runner import _run_agent
from agents.stats import RecordingSearch, RunStats, UsageCounter
from contracts import Report, SearchFn
from google.adk.agents.readonly_context import ReadonlyContext


def answer_baseline_with_stats(
    question: str,
    *,
    search_fn: SearchFn = default_search,
    k: int = 8,
) -> tuple[Report, RunStats]:
    """Answer using vector retrieval and exactly one LLM agent."""

    started = time.perf_counter()

    recorder = RecordingSearch(search_fn)
    chunks = recorder(question, k=k, hybrid=False)

    evidence = "\n\n".join(
        f"Source [{chunk.paper_id}]\n"
        f"URL: {chunk.source_url}\n"
        f"{chunk.text}"
        for chunk in chunks
    )

    if not evidence:
        evidence = "No relevant source passages were retrieved."

    def instruction_provider(_context: ReadonlyContext) -> str:
        return f"""
You are a research assistant running in the E0 baseline configuration.

Answer the user's research question using only the source passages below.

Rules:
1. Write a clear and concise Markdown report.
2. Cite factual claims using the exact paper ID in square brackets.
3. Do not invent sources or citations.
4. Clearly state when the retrieved evidence is insufficient.
5. Do not use external knowledge to fill gaps in the evidence.

Retrieved source passages:

{evidence}
"""

    _, heavy_model = load_models()

    agent = LlmAgent(
        name="single_call_baseline",
        model=heavy_model,
        description="Single LLM call using vector-retrieved research passages.",
        instruction=instruction_provider,
        output_key="baseline_report",
    )

    agent = harden_agent(agent)

    usage = UsageCounter()

    state = asyncio.run(
        _run_agent(agent, question, {}, usage)
    )

    markdown = str(state.get("baseline_report") or "").strip()

    if not markdown:
        raise RuntimeError("The E0 baseline did not produce a report.")

    report = Report(
        question=question,
        markdown=markdown,
        sources=list(recorder.source_ids),
        verified=False,
    )

    stats = RunStats(
        retrieved_source_ids=tuple(recorder.source_ids),
        llm_calls=usage.llm_calls,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        latency_seconds=time.perf_counter() - started,
    )

    return report, stats
