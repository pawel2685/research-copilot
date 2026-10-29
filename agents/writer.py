"""Writer agent: writes the report from the notes."""
from __future__ import annotations

from collections.abc import Sequence

from google.adk.agents import LlmAgent

from agents.config import load_models

WRITER_INSTRUCTION = """
You are the Writer in a research assistant system.

Write a short report in Markdown that answers the user's question using only the notes
below. Put the paper_id in square brackets after each claim. Never invent sources. If
the notes say that nothing was found, say that plainly.
"""

REVISION_INSTRUCTION = """
A reviewer checked your draft and asked for corrections. Rewrite the draft so that it
follows the corrections. Keep only claims that the notes support.

Draft:
{draft_report}

Corrections:
{revision_instructions}
"""


def create_writer_agent(
    model: str | None = None,
    *,
    notes_keys: Sequence[str] = ("reading_notes",),
    optional_notes: bool = False,
    revision: bool = False,
) -> LlmAgent:
    """Create the Writer without making an API request.

    The notes are read from the session state keys `notes_keys`. With
    `optional_notes` a missing key counts as empty notes, which is needed when only
    some of the parallel branches ran. With `revision` the Writer also gets the
    previous draft (`draft_report`) and the corrections (`revision_instructions`)
    from the session state.
    """
    suffix = "?" if optional_notes else ""
    notes = "\n".join(f"{{{key}{suffix}}}" for key in notes_keys)
    instruction = f"{WRITER_INSTRUCTION}\nNotes:\n{notes}\n"
    if revision:
        instruction += REVISION_INSTRUCTION
    return LlmAgent(
        name="writer",
        model=model or load_models()[1],
        description="Writes a short report with sources from the notes.",
        instruction=instruction,
        output_key="report_markdown",
    )
