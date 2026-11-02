import pytest

from agents.critic import CriticResult
from agents.deadline import Deadline
from agents.skipping import (
    CRITIC_MIN_LEFT_S,
    PLANNER_MIN_LEFT_S,
    critique,
    is_verified,
    plan_questions,
)
from contracts import Report, RunConfig


def _deadline(left_s: float) -> Deadline:
    return Deadline.after(left_s, clock=lambda: 0.0)


def _fail_planner(question):
    raise AssertionError("planner must not be called")


def _fail_critic(report, chunks):
    raise AssertionError("critic must not be called")


REPORT = Report(question="q", markdown="# q")
PLENTY = 1000.0


def test_plan_skipped_without_planner_fn():
    assert plan_questions("q", None, _deadline(PLENTY), RunConfig()) == ["q"]


def test_plan_skipped_when_switched_off():
    cfg = RunConfig(use_planner=False)
    assert plan_questions("q", _fail_planner, _deadline(PLENTY), cfg) == ["q"]


def test_plan_skipped_when_time_is_short():
    deadline = _deadline(PLANNER_MIN_LEFT_S - 1)
    assert plan_questions("q", _fail_planner, deadline, RunConfig()) == ["q"]


def test_plan_empty_result_falls_back_to_the_question():
    assert plan_questions("q", lambda q: [], _deadline(PLENTY), RunConfig()) == ["q"]


def test_plan_returns_the_planner_list():
    planner = lambda q: [f"{q} a", f"{q} b"]
    result = plan_questions("q", planner, _deadline(PLENTY), RunConfig())
    assert result == ["q a", "q b"]


@pytest.mark.parametrize(
    "critic_fn, cfg, left_s",
    [
        (None, RunConfig(), PLENTY),
        (_fail_critic, RunConfig(use_critic=False), PLENTY),
        (_fail_critic, RunConfig(), CRITIC_MIN_LEFT_S - 1),
    ],
    ids=["no-critic", "switched-off", "short-deadline"],
)
def test_critique_skipped(critic_fn, cfg, left_s):
    result = critique(REPORT, [], critic_fn, _deadline(left_s), cfg)
    assert result.approved is None
    assert result.unverified is True
    assert result.message


def test_critique_skip_reasons_differ():
    messages = {
        critique(REPORT, [], None, _deadline(PLENTY), RunConfig()).message,
        critique(
            REPORT, [], _fail_critic, _deadline(PLENTY), RunConfig(use_critic=False)
        ).message,
        critique(
            REPORT, [], _fail_critic, _deadline(CRITIC_MIN_LEFT_S - 1), RunConfig()
        ).message,
    }
    assert len(messages) == 3


def test_critique_returns_the_critic_result():
    expected = CriticResult(approved=True)
    seen = []

    def critic_fn(report, chunks):
        seen.append((report, chunks))
        return expected

    result = critique(REPORT, [], critic_fn, _deadline(PLENTY), RunConfig())
    assert result is expected
    assert seen == [(REPORT, [])]


@pytest.mark.parametrize("approved, expected", [(True, True), (False, False), (None, False)])
def test_is_verified_only_for_approved_true(approved, expected):
    assert is_verified(CriticResult(approved=approved)) is expected
