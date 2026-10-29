"""Runs the ADK flow in a session and returns the report."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from google.adk.agents import BaseAgent, LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agents.config import load_models
from agents.critic import CriticResult, critic_skipped_result
from agents.orchestrator import build_pipeline, notes_keys
from agents.skipping import is_verified, normalize_sub_questions
from agents.tools import make_search_tool
from agents.writer import create_writer_agent
from contracts import RunConfig, SearchFn
from stubs.search import search as stub_search

APP_NAME = "research_copilot"
USER_ID = "user"


@dataclass
class PipelineResult:
    """What one run of the flow produced."""

    report_markdown: str
    sub_questions: list[str]
    critic_result: CriticResult
    # True when the report was rewritten after the Critic rejected it. The new
    # version was not checked.
    revised: bool = False
    state: dict[str, Any] = field(default_factory=dict)

    @property
    def verified(self) -> bool:
        """True only when the Critic approved the report that is returned."""
        return is_verified(self.critic_result) and not self.revised


async def _run_agent(agent: BaseAgent, question: str, state: dict[str, Any]) -> dict:
    """Run `agent` once in a new session and return the final session state."""
    session_service = InMemorySessionService()
    session_id = uuid.uuid4().hex
    await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session_id, state=state
    )
    runner = Runner(app_name=APP_NAME, agent=agent, session_service=session_service)
    message = types.Content(role="user", parts=[types.Part(text=question)])
    async for _ in runner.run_async(
        user_id=USER_ID, session_id=session_id, new_message=message
    ):
        pass
    session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session_id
    )
    return dict(session.state) if session is not None else dict(state)


def _read_critic_result(value: Any) -> CriticResult:
    if value is None:
        return critic_skipped_result("Critic did not run.")
    try:
        if isinstance(value, str):
            return CriticResult.model_validate_json(value)
        return CriticResult.model_validate(value)
    except ValueError:
        return critic_skipped_result("Critic output could not be read.")


async def run_pipeline(
    question: str,
    cfg: RunConfig | None = None,
    *,
    search_fn: SearchFn = stub_search,
    planner: LlmAgent | None = None,
    critic: LlmAgent | None = None,
    models: tuple[str, str] | None = None,
) -> PipelineResult:
    """Run the flow for one question. At most one revision after the Critic."""
    cfg = cfg or RunConfig()
    models = models or load_models()
    deadline_at = time.time() + cfg.time_budget_s
    search_tool = make_search_tool(
        search_fn, hybrid=cfg.hybrid, budget_words=cfg.compress_budget_words
    )
    pipeline = build_pipeline(
        cfg, search_tool=search_tool, planner=planner, critic=critic, models=models
    )
    # The initial sub_questions make branch 1 work even when the Planner is skipped.
    state = await _run_agent(
        pipeline,
        question,
        {"deadline_at": deadline_at, "question": question, "sub_questions": [question]},
    )

    report_markdown = str(state.get("report_markdown") or "")
    critic_result = _read_critic_result(state.get("critic_result"))
    revised = False
    # Skip the revision when the time budget is already used up.
    if (
        critic_result.approved is False
        and critic_result.revision_instructions
        and deadline_at - time.time() > 0
    ):
        writer = create_writer_agent(
            models[1], notes_keys=notes_keys(), optional_notes=True, revision=True
        )
        revision_state = {
            key: value for key, value in state.items() if key in notes_keys()
        } | {
            "draft_report": report_markdown,
            "revision_instructions": "\n".join(
                f"- {text}" for text in critic_result.revision_instructions
            ),
        }
        new_state = await _run_agent(writer, question, revision_state)
        new_markdown = str(new_state.get("report_markdown") or "")
        if new_markdown:
            report_markdown, revised = new_markdown, True

    return PipelineResult(
        report_markdown=report_markdown,
        sub_questions=normalize_sub_questions(state.get("sub_questions"), question),
        critic_result=critic_result,
        revised=revised,
        state=state,
    )
