"""Show the verdict of the Critic as readable text in the chat of the web demo.

The Critic answers in a fixed JSON format (`CriticResult`), and `adk web` prints the answer
of every agent as it is, so the chat ended with raw JSON. `ReadableSequentialAgent` is a
`SequentialAgent` that replaces the text of the Critic's message with a short Markdown
summary. The result in the session state (`critic_result`) is not touched, it is saved
before the message is sent on.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from google.adk.agents import SequentialAgent
from google.adk.events import Event
from pydantic import ValidationError

from agents.critic import CriticResult

CRITIC_AUTHOR = "critic"
_NOTE = "_The Critic checked the claims against the titles and abstracts of the retrieved papers only._"


def format_critic_result(result: CriticResult) -> str:
    """The verdict of the Critic as a short Markdown text."""
    if result.approved is None:
        reason = result.message or "The report was not checked."
        return f"### Critic: skipped\n\n{reason}\n\nThe report is **not verified**."

    supported = sum(1 for item in result.assessments if item.status == "supported")
    total = len(result.assessments)
    if result.approved:
        lines = [
            "### Critic: approved",
            "",
            f"{supported} of {total} claims are supported by the sources. The report is **verified**.",
        ]
    else:
        lines = [
            "### Critic: changes needed",
            "",
            f"{supported} of {total} claims are supported by the sources. The report is **not verified**.",
        ]

    if result.assessments:
        lines.append("")
        for item in result.assessments:
            sources = f" [{', '.join(item.source_ids)}]" if item.source_ids else ""
            lines.append(f"- **{item.status}**{sources}: {item.claim}")
            if item.status != "supported" and item.rationale:
                lines.append(f"  - Why: {item.rationale}")

    if result.revision_instructions:
        lines += ["", "**Corrections for the Writer:**", ""]
        lines += [f"- {text}" for text in result.revision_instructions]

    lines += ["", _NOTE]
    return "\n".join(lines)


def readable_event(event: Event) -> Event:
    """Replace the JSON text of the Critic's message with its Markdown summary.

    Any other message, a partial one, or a Critic message that is not a valid
    `CriticResult` is returned unchanged.
    """
    if event.author != CRITIC_AUTHOR or event.partial:
        return event
    parts = event.content.parts if event.content and event.content.parts else []
    if len(parts) != 1 or not parts[0].text:
        return event
    try:
        result = CriticResult.model_validate_json(parts[0].text)
    except ValidationError:
        return event
    parts[0].text = format_critic_result(result)
    return event


class ReadableSequentialAgent(SequentialAgent):
    """A `SequentialAgent` whose chat shows the Critic's verdict as text, not JSON."""

    async def _run_async_impl(self, ctx: Any) -> AsyncGenerator[Event, None]:
        async for event in super()._run_async_impl(ctx):
            yield readable_event(event)
