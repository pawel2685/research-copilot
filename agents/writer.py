"""Writer agent: writes the report from the notes."""
from __future__ import annotations

from google.adk.agents import LlmAgent

from agents.config import load_models

WRITER_INSTRUCTION = """
You are the Writer in a research assistant system.

Write a short report in Markdown that answers the user's question using only the notes
below. Put the paper_id in square brackets after each claim. Never invent sources. If
the notes say that nothing was found, say that plainly.

Notes:
{reading_notes}
"""


def create_writer_agent(model: str | None = None) -> LlmAgent:
    """Create the Writer without making an API request."""
    return LlmAgent(
        name="writer",
        model=model or load_models()[1],
        description="Writes a short report with sources from the notes.",
        instruction=WRITER_INSTRUCTION,
        output_key="report_markdown",
    )
