"""Rules for skipping the Planner and the Critic when time runs short.

Plain Python, so the rules are testable without ADK. The core always returns a
report: a skipped Planner means the original question is used, and a skipped Critic
means the report stays unverified.
"""
from __future__ import annotations

from collections.abc import Callable

from agents.critic import CriticResult, critic_skipped_result
from agents.deadline import Deadline
from contracts import Chunk, Report, RunConfig

# Example values (the time an agent needs). Tune them after the first real runs.
PLANNER_MIN_LEFT_S = 40.0
CRITIC_MIN_LEFT_S = 30.0

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
