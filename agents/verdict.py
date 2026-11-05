"""Show the end of the chat of the web demo as readable text: the report and the verdict.

The Critic answers in a fixed JSON format (`CriticResult`), and `adk web` prints the answer
of every agent as it is, so the chat ended with raw JSON. `ReadableSequentialAgent` is a
`SequentialAgent` that replaces the text of the Critic's message with the report of the
Writer and, under it, a one-line verdict. The details of a claim are shown only for a
claim that is not supported. The result in the session state (`critic_result`) is not
touched, it is saved before the message is sent on, and has all the details.

The messages of the other agents (Planner, Searchers, Readers) stay in the chat on purpose:
the Critic gets its evidence from the conversation, so hiding them would blind it.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from google.adk.agents import SequentialAgent
from google.adk.events import Event
from pydantic import ValidationError

from agents.critic import CriticResult

CRITIC_AUTHOR = "critic"
_SCOPE = "checked against titles and abstracts only"


def format_critic_result(result: CriticResult) -> str:
    """The verdict of the Critic as a short Markdown text.

    One line: verified or not, and how many claims are supported. Only the claims that are
    not supported are listed, with the reason, and then the corrections for the Writer.
    """
    if result.approved is None:
        reason = result.message or "the report was not checked"
        return f"**Not verified** · Critic skipped: {reason}"

    supported = sum(1 for item in result.assessments if item.status == "supported")
    total = len(result.assessments)
    state = "Verified" if result.approved else "Not verified"
    lines = [f"**{state}** · {supported} of {total} claims supported ({_SCOPE})"]

    problems = [item for item in result.assessments if item.status != "supported"]
    if problems:
        lines.append("")
        for item in problems:
            sources = f" [{', '.join(item.source_ids)}]" if item.source_ids else ""
            lines.append(f"- **{item.status}**{sources}: {item.claim}")
            if item.rationale:
                lines.append(f"  - Why: {item.rationale}")

    if result.revision_instructions:
        lines += ["", "**Corrections for the Writer:**", ""]
        lines += [f"- {text}" for text in result.revision_instructions]
    return "\n".join(lines)


def format_final_message(report: str | None, result: CriticResult) -> str:
    """The last message of the chat: the report, and under it the verdict of the Critic.

    The chat ends with the Critic's message, so the answer is repeated there. Without it the
    last thing on the screen would be the verification and not the answer.
    """
    verdict = format_critic_result(result)
    if not report or not report.strip():
        return verdict
    return f"{report.strip()}\n\n---\n\n{verdict}"


def readable_event(event: Event, report: str | None = None) -> Event:
    """Replace the JSON text of the Critic's message with the report and the verdict.

    Any other message, a partial one, or a Critic message that is not a valid
    `CriticResult` is returned unchanged. Without a `report` only the verdict is shown.
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
    parts[0].text = format_final_message(report, result)
    return event


class ReadableSequentialAgent(SequentialAgent):
    """A `SequentialAgent` whose chat ends with the report and the verdict as text, not JSON."""

    async def _run_async_impl(self, ctx: Any) -> AsyncGenerator[Event, None]:
        async for event in super()._run_async_impl(ctx):
            # The Writer's report is in the state by the time the Critic's message comes.
            yield readable_event(event, ctx.session.state.get("report_markdown"))
