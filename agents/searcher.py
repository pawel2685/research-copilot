"""Searcher agent: finds passages with the search tool."""
from __future__ import annotations

from collections.abc import Callable

from google.adk.agents import LlmAgent

from agents.config import load_models

SEARCHER_INSTRUCTION = """
You are the Searcher in a research assistant system.

Call the search tool for the question. Return the passages exactly as the tool gave
them, each with its paper_id. Do not summarise them and do not invent passages. If the
tool returns nothing, say that no passages were found.
"""


def create_searcher_agent(
    search_tool: Callable[[str], list[dict]],
    model: str | None = None,
    *,
    name: str = "searcher",
    output_key: str = "search_results",
    question_key: str | None = None,
) -> LlmAgent:
    """Create the Searcher without making an API request.

    `question_key` is a session state key that holds the question to search for.
    Without it the Searcher uses the question from the user message.
    """
    instruction = SEARCHER_INSTRUCTION
    if question_key:
        instruction += f"\nQuestion to search for:\n{{{question_key}}}\n"
    return LlmAgent(
        name=name,
        model=model or load_models()[0],
        description="Finds passages in the paper corpus.",
        instruction=instruction,
        tools=[search_tool],
        output_key=output_key,
    )
