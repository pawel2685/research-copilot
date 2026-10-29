from types import SimpleNamespace

import pytest

from agents.skipping import (
    make_branch_callback,
    make_deadline_callback,
    normalize_sub_questions,
)


def _ctx(**state):
    return SimpleNamespace(state=dict(state))


def test_deadline_callback_skips_below_the_threshold():
    callback = make_deadline_callback(40, clock=lambda: 100.0)
    content = callback(_ctx(deadline_at=130.0))
    assert content is not None
    assert content.parts[0].text == "skipped"


def test_deadline_callback_lets_the_agent_run_above_the_threshold():
    callback = make_deadline_callback(40, clock=lambda: 100.0)
    assert callback(_ctx(deadline_at=140.0)) is None
    assert callback(_ctx(deadline_at=500.0)) is None


def test_deadline_callback_skip_text_can_be_a_string_or_a_function_of_the_context():
    fixed = make_deadline_callback(40, "nothing", clock=lambda: 100.0)
    assert fixed(_ctx(deadline_at=0.0)).parts[0].text == "nothing"
    computed = make_deadline_callback(40, lambda ctx: ctx.state["question"], clock=lambda: 100.0)
    assert computed(_ctx(deadline_at=0.0, question="q")).parts[0].text == "q"


def test_deadline_callback_uses_the_wall_clock_by_default():
    callback = make_deadline_callback(40)
    assert callback(_ctx(deadline_at=0.0)) is not None


def test_branch_callback_skips_a_branch_without_a_sub_question():
    ctx = _ctx(question="q", sub_questions=["only one"])
    assert make_branch_callback(1)(ctx) is not None
    assert "sub_question_2" not in ctx.state


def test_branch_callback_stores_the_sub_question():
    ctx = _ctx(question="q", sub_questions=["first", "second"])
    assert make_branch_callback(0)(ctx) is None
    assert make_branch_callback(1)(ctx) is None
    assert ctx.state["sub_question_1"] == "first"
    assert ctx.state["sub_question_2"] == "second"


def test_branch_callback_falls_back_to_the_question():
    ctx = _ctx(question="q")
    assert make_branch_callback(0)(ctx) is None
    assert ctx.state["sub_question_1"] == "q"
    assert make_branch_callback(1)(ctx) is not None


def test_branch_callback_reads_planner_json_output():
    ctx = _ctx(question="q", sub_questions='{"questions": ["a", "b"]}')
    assert make_branch_callback(1)(ctx) is None
    assert ctx.state["sub_question_2"] == "b"


def test_branch_callback_skips_everything_when_there_is_no_question_at_all():
    assert make_branch_callback(0)(_ctx()) is not None


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, ["q"]),
        (["a", "b"], ["a", "b"]),
        ({"questions": ["a", "b"]}, ["a", "b"]),
        ('["a", "b"]', ["a", "b"]),
        ('{"questions": ["a"]}', ["a"]),
        (["a", "b", "c", "d", "e", "f"], ["a", "b", "c", "d"]),
        (["a", "", "  ", "b"], ["a", "b"]),
        ([], ["q"]),
        (["", " "], ["q"]),
        ([1, None, "a"], ["a"]),
        ("not json at all", ["q"]),
        ("42", ["q"]),
        ({"other": 1}, ["q"]),
        ({"questions": "a"}, ["q"]),
        (42, ["q"]),
    ],
)
def test_normalize_sub_questions(value, expected):
    assert normalize_sub_questions(value, "q") == expected
