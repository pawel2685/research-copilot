import asyncio
import time

import pytest
from google.adk.events import Event, EventActions

from agents import runner
from agents.runner import PipelineResult, run_pipeline
from contracts import RunConfig

MODELS = ("light-model", "heavy-model")
REJECT = {"approved": False, "revision_instructions": ["Remove claim X.", "Cite [1]."]}


class FakeRunner:
    """Stands in for the ADK Runner: writes a scripted state delta, calls no model."""

    runs: list = []
    script: dict = {}

    def __init__(self, *, app_name, agent, session_service):
        self.app_name = app_name
        self.agent = agent
        self.session_service = session_service

    async def run_async(self, *, user_id, session_id, new_message):
        session = await self.session_service.get_session(
            app_name=self.app_name, user_id=user_id, session_id=session_id
        )
        FakeRunner.runs.append(
            {
                "agent": self.agent,
                "initial_state": dict(session.state),
                "message": new_message.parts[0].text,
            }
        )
        delta = FakeRunner.script.get(self.agent.name, {})
        event = Event(author=self.agent.name, actions=EventActions(state_delta=delta))
        await self.session_service.append_event(session, event)
        yield event


@pytest.fixture
def fake_runner(monkeypatch):
    FakeRunner.runs = []
    FakeRunner.script = {}
    monkeypatch.setattr(runner, "Runner", FakeRunner)
    return FakeRunner


def _run(question="q", cfg=None, **kwargs):
    return asyncio.run(run_pipeline(question, cfg, models=MODELS, **kwargs))


def test_initial_state_has_deadline_question_and_sub_questions(fake_runner):
    fake_runner.script = {"research_pipeline": {"report_markdown": "draft"}}
    before = time.time()
    _run("my question", RunConfig(time_budget_s=60))
    state = fake_runner.runs[0]["initial_state"]
    assert before + 60 <= state["deadline_at"] <= time.time() + 60
    assert state["question"] == "my question"
    assert state["sub_questions"] == ["my question"]
    assert fake_runner.runs[0]["message"] == "my question"


def test_returns_the_final_report_and_state(fake_runner):
    fake_runner.script = {"research_pipeline": {"report_markdown": "draft"}}
    result = _run()
    assert isinstance(result, PipelineResult)
    assert result.report_markdown == "draft"
    assert result.sub_questions == ["q"]
    assert result.state["report_markdown"] == "draft"
    assert result.revised is False


def test_missing_critic_result_means_skipped_and_unverified(fake_runner):
    fake_runner.script = {"research_pipeline": {"report_markdown": "draft"}}
    result = _run()
    assert result.critic_result.approved is None
    assert result.critic_result.unverified is True
    assert result.verified is False
    assert len(fake_runner.runs) == 1


def test_sub_questions_from_the_planner_are_returned(fake_runner):
    fake_runner.script = {
        "research_pipeline": {"report_markdown": "d", "sub_questions": '["a", "b"]'}
    }
    assert _run().sub_questions == ["a", "b"]


def test_approved_report_is_verified_and_not_revised(fake_runner):
    fake_runner.script = {
        "research_pipeline": {"report_markdown": "draft", "critic_result": {"approved": True}}
    }
    result = _run()
    assert result.verified is True
    assert len(fake_runner.runs) == 1


def test_rejected_report_is_revised_exactly_once(fake_runner):
    fake_runner.script = {
        "research_pipeline": {
            "report_markdown": "draft",
            "critic_result": REJECT,
            "reading_notes_1": "note [1]",
            "search_results_1": "not passed on",
        },
        "writer": {"report_markdown": "revised"},
    }
    result = _run()
    assert [run["agent"].name for run in fake_runner.runs] == ["research_pipeline", "writer"]
    assert result.report_markdown == "revised"
    assert result.revised is True
    assert result.critic_result.approved is False
    assert result.verified is False
    revision_state = fake_runner.runs[1]["initial_state"]
    assert revision_state["draft_report"] == "draft"
    assert revision_state["revision_instructions"] == "- Remove claim X.\n- Cite [1]."
    assert revision_state["reading_notes_1"] == "note [1]"
    assert "search_results_1" not in revision_state


def test_empty_revision_keeps_the_original_report(fake_runner):
    fake_runner.script = {
        "research_pipeline": {"report_markdown": "draft", "critic_result": REJECT},
        "writer": {"report_markdown": ""},
    }
    result = _run()
    assert result.report_markdown == "draft"
    assert result.revised is False


def test_rejection_without_instructions_is_not_revised(fake_runner):
    fake_runner.script = {
        "research_pipeline": {"report_markdown": "d", "critic_result": {"approved": False}}
    }
    _run()
    assert len(fake_runner.runs) == 1


def test_no_revision_when_the_time_budget_is_used_up(fake_runner):
    fake_runner.script = {
        "research_pipeline": {"report_markdown": "d", "critic_result": REJECT}
    }
    result = _run(cfg=RunConfig(time_budget_s=0))
    assert len(fake_runner.runs) == 1
    assert result.report_markdown == "d"


def test_unreadable_critic_output_counts_as_skipped(fake_runner):
    fake_runner.script = {
        "research_pipeline": {"report_markdown": "d", "critic_result": {"approved": "maybe"}}
    }
    result = _run()
    assert result.critic_result.unverified is True
    assert result.verified is False


def test_critic_output_as_json_string_is_read(fake_runner):
    fake_runner.script = {
        "research_pipeline": {"report_markdown": "d", "critic_result": '{"approved": true}'}
    }
    assert _run().verified is True


def test_missing_report_gives_an_empty_string(fake_runner):
    assert _run().report_markdown == ""


def test_defaults_to_run_config_and_environment_models(fake_runner, monkeypatch):
    from agents import config

    monkeypatch.setattr(config, "load_dotenv", lambda: False)
    monkeypatch.setenv("MODEL_LIGHT", "l")
    monkeypatch.setenv("MODEL_HEAVY", "h")
    fake_runner.script = {"research_pipeline": {"report_markdown": "d"}}
    result = asyncio.run(run_pipeline("q"))
    assert result.report_markdown == "d"
