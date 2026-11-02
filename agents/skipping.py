"""Rules for skipping the Planner and the Critic when time runs short.

Plain Python, so the rules are testable without ADK. The callbacks at the end plug the
same rules into ADK. The core always returns a report: a skipped Planner means the
original question is used, and a skipped Critic means the report stays unverified.
"""
from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

from google.genai import types

from agents.critic import CriticResult, critic_skipped_result
from agents.deadline import Deadline
from contracts import Chunk, Report, RunConfig

# Example values (the time an agent needs). Tune them after the first real runs.
PLANNER_MIN_LEFT_S = 40.0
CRITIC_MIN_LEFT_S = 30.0

MAX_SUB_QUESTIONS = 4

PlannerFn = Callable[[str], list[str]]
CriticFn = Callable[[Report, list[Chunk]], CriticResult]


def plan_questions(
    question: str,
    planner_fn: PlannerFn | None,
    deadline: Deadline,
    cfg: RunConfig,
) -> list[str]:
    """Split the question into sub-questions, or return `[question]` when skipped."""
    if (
        planner_fn is None
        or not cfg.use_planner
        or deadline.should_skip(PLANNER_MIN_LEFT_S)
    ):
        return [question]
    return planner_fn(question) or [question]


def critique(
    report: Report,
    chunks: list[Chunk],
    critic_fn: CriticFn | None,
    deadline: Deadline,
    cfg: RunConfig,
) -> CriticResult:
    """Check the report with the Critic, or return a skipped result."""
    if critic_fn is None:
        return critic_skipped_result("Critic skipped because no critic is available.")
    if not cfg.use_critic:
        return critic_skipped_result("Critic skipped because it is switched off.")
    if deadline.should_skip(CRITIC_MIN_LEFT_S):
        return critic_skipped_result(
            "Critic skipped because the time budget was insufficient."
        )
    return critic_fn(report, chunks)


def is_verified(result: CriticResult) -> bool:
    """A report is verified only when the Critic ran and approved it."""
    return result.approved is True


def _skip_content(text: str = "skipped") -> types.Content:
    return types.Content(role="model", parts=[types.Part(text=text)])


def make_deadline_callback(
    min_left_s: float,
    skip_text: str | Callable[[Any], str] = "skipped",
    clock: Callable[[], float] = time.time,
) -> Callable[[Any], types.Content | None]:
    """Build a `before_agent_callback` that skips an agent when time runs short.

    It reads `deadline_at` (a `time.time()` value) from the session state.
    Returning `Content` makes ADK skip the agent. `None` lets it run.

    ADK also saves the text of that `Content` under the `output_key` of the agent and
    checks it against its `output_schema`. So `skip_text` (a string, or a function of
    the context) must be a valid output of the agent that is skipped.
    """

    def callback(ctx: Any) -> types.Content | None:
        if ctx.state["deadline_at"] - clock() < min_left_s:
            text = skip_text(ctx) if callable(skip_text) else skip_text
            return _skip_content(text)
        return None

    return callback


def normalize_sub_questions(value: Any, question: str) -> list[str]:
    """Turn the Planner output into at most four non-empty sub-questions.

    Accepts `None`, a list of strings, a dict with a `questions` list, or a JSON
    string of either. Returns `[question]` when nothing usable is given.
    """
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return [question]
    if isinstance(value, dict):
        value = value.get("questions")
    if not isinstance(value, list):
        return [question]
    cleaned = [
        item.strip() for item in value if isinstance(item, str) and item.strip()
    ]
    return cleaned[:MAX_SUB_QUESTIONS] or [question]


def make_branch_callback(index: int) -> Callable[[Any], types.Content | None]:
    """Build a `before_agent_callback` for the search branch number `index` (from 0).

    The branch is skipped when there is no sub-question for it. Otherwise the
    sub-question is stored in the state as `sub_question_<index + 1>`.
    """

    def callback(ctx: Any) -> types.Content | None:
        question = ctx.state.get("question", "")
        items = [
            item
            for item in normalize_sub_questions(ctx.state.get("sub_questions"), question)
            if item
        ]
        if index >= len(items):
            return _skip_content()
        ctx.state[f"sub_question_{index + 1}"] = items[index]
        return None

    return callback
