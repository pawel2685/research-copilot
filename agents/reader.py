"""Reader agent: turns the passages into short notes."""
from __future__ import annotations

from google.adk.agents import LlmAgent

from agents.config import load_models

READER_INSTRUCTION = """
You are the Reader in a research assistant system.

Summarise the passages below as short factual notes. Every note ends with the paper_id
it comes from in square brackets, for example [2005.11401]. Use only the given
passages. If there are no passages, say so.

Passages:
{search_results}
"""


def create_reader_agent(model: str | None = None) -> LlmAgent:
    """Create the Reader without making an API request."""
    return LlmAgent(
        name="reader",
        model=model or load_models()[0],
        description="Summarises the passages as short notes with paper ids.",
        instruction=READER_INSTRUCTION,
        output_key="reading_notes",
    )
