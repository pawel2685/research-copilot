"""Searcher agent: finds passages with the search tool."""
from __future__ import annotations

from collections.abc import Callable

from google.adk.agents import LlmAgent

from agents.config import load_models

SEARCHER_INSTRUCTION = """
You are the Searcher in a research assistant system.

Call the search tool for the user's question. Return the passages exactly as the tool
gave them, each with its paper_id. Do not summarise them and do not invent passages.
If the tool returns nothing, say that no passages were found.
"""


def create_searcher_agent(
    search_tool: Callable[[str], list[dict]], model: str | None = None
) -> LlmAgent:
    """Create the Searcher without making an API request."""
    return LlmAgent(
        name="searcher",
        model=model or load_models()[0],
        description="Finds passages in the paper corpus.",
        instruction=SEARCHER_INSTRUCTION,
        tools=[search_tool],
        output_key="search_results",
    )
