"""Reader agent: turns the passages into short notes."""
from __future__ import annotations

from google.adk.agents import LlmAgent

from agents.config import load_models

READER_INSTRUCTION = """
You are the Reader in a research assistant system.

Summarise the passages below as short factual notes. Every note ends with the paper_id
it comes from in square brackets, for example [2005.11401]. Use only the given
passages. If there are no passages, say so.
"""


def create_reader_agent(
    model: str | None = None,
    *,
    name: str = "reader",
    input_key: str = "search_results",
    output_key: str = "reading_notes",
) -> LlmAgent:
    """Create the Reader without making an API request.

    The passages are read from the session state key `input_key`.
    """
    instruction = f"{READER_INSTRUCTION}\nPassages:\n{{{input_key}}}\n"
    return LlmAgent(
        name=name,
        model=model or load_models()[0],
        description="Summarises the passages as short notes with paper ids.",
        instruction=instruction,
        output_key=output_key,
    )
