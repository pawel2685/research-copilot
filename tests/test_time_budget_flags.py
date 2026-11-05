
import json
from types import SimpleNamespace

from agents.critic import CriticResult
from agents.orchestrator import (
    _critic_skip_text,
    _planner_skip_text,
)


def test_planner_skip_is_recorded_in_session_state():
    ctx = SimpleNamespace(
        state={"question": "What is RAG?"}
    )

    output = _planner_skip_text(ctx)

    assert ctx.state["planner_skipped_by_deadline"] is True
    assert json.loads(output) == ["What is RAG?"]


def test_critic_skip_is_recorded_in_session_state():
    ctx = SimpleNamespace(state={})

    output = _critic_skip_text(ctx)
    result = CriticResult.model_validate_json(output)

    assert ctx.state["critic_skipped_by_deadline"] is True
    assert result.approved is None
    assert result.unverified is True
    assert "time budget" in result.message.lower()
