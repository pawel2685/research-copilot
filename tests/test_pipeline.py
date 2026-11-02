import functools

import pytest

from agents import pipeline
from agents.critic import CriticResult, critic_skipped_result
from agents.runner import PipelineResult
from contracts import Chunk, Report, RunConfig
from tests.fake_llm import FakeLlm


def _result(state=None, critic_result=None, report="# Report", revised=False):
    return PipelineResult(
        report_markdown=report,
        sub_questions=["q"],
        critic_result=critic_result or critic_skipped_result(),
        revised=revised,
        state=state or {},
    )


class FakeRun:
    """Replaces `run_pipeline`: records its arguments and returns a prepared result."""

    def __init__(self, result):
        self.result = result
        self.calls = []

    async def __call__(self, question, cfg, **kwargs):
        self.calls.append({"question": question, "cfg": cfg, **kwargs})
        return self.result


@pytest.fixture
def fake_run(monkeypatch):
    run = FakeRun(_result())
    monkeypatch.setattr(pipeline, "run_pipeline", run)
    monkeypatch.setattr(pipeline, "create_critic_agent", lambda: "critic-agent")
    return run


def test_sources_are_unique_and_in_order_of_appearance():
    state = {
        "reading_notes_1": "A [2106.09685] and B [1706.03762].",
        "reading_notes_2": "C [1706.03762] and D [2005.11401].",
        "reading_notes_3": "E [2106.09685].",
    }
    assert pipeline.cited_paper_ids(_result(state)) == ["2106.09685", "1706.03762", "2005.11401"]


def test_sources_ignore_other_brackets_and_strip_the_version():
    state = {"reading_notes_1": "See [1], [note], [2106.09685v2] and (2005.11401)."}
    assert pipeline.cited_paper_ids(_result(state)) == ["2106.09685"]


def test_no_notes_means_no_sources():
    assert pipeline.cited_paper_ids(_result({"reading_notes_2": None})) == []


def test_only_the_notes_of_the_branches_count():
    state = {"search_results_1": "[2106.09685]", "reading_notes_1": "[1706.03762]"}
    assert pipeline.cited_paper_ids(_result(state)) == ["1706.03762"]


def test_to_report_copies_question_markdown_and_sources():
    report = pipeline.to_report("q?", _result({"reading_notes_1": "[2106.09685]"}, report="# R"))
    assert report == Report(question="q?", markdown="# R", sources=["2106.09685"], verified=False)


def test_verified_only_for_an_approving_critic():
    approved = _result(critic_result=CriticResult(approved=True))
    rejected = _result(critic_result=CriticResult(approved=False))
    assert pipeline.to_report("q", approved).verified is True
    assert pipeline.to_report("q", rejected).verified is False


def test_skipped_critic_gives_an_unverified_report():
    assert pipeline.to_report("q", _result(critic_result=critic_skipped_result())).verified is False


def test_revised_report_is_not_verified():
    result = _result(critic_result=CriticResult(approved=True), revised=True)
    assert pipeline.to_report("q", result).verified is False


def test_answer_returns_a_report_and_passes_the_config_on(fake_run):
    cfg = RunConfig(hybrid=False)
    report = pipeline.answer("my question", cfg)
    assert isinstance(report, Report)
    assert report.question == "my question"
    call = fake_run.calls[0]
    assert (call["question"], call["cfg"]) == ("my question", cfg)
    assert call["search_fn"] is pipeline.default_search
    assert call["planner"] is None


def test_answer_uses_the_default_config(fake_run):
    pipeline.answer("q")
    assert fake_run.calls[0]["cfg"] == RunConfig()


def test_answer_wires_c_critic_when_the_critic_is_on(fake_run):
    pipeline.answer("q", RunConfig(use_critic=True))
    assert fake_run.calls[0]["critic"] == "critic-agent"


def test_answer_leaves_the_critic_out_when_it_is_off(fake_run, monkeypatch):
    def fail():
        raise AssertionError("the critic must not be created")

    monkeypatch.setattr(pipeline, "create_critic_agent", fail)
    pipeline.answer("q", RunConfig(use_critic=False))
    assert fake_run.calls[0]["critic"] is None


def test_answer_accepts_own_search_function_planner_and_critic(fake_run):
    def search_fn(query, k=8, hybrid=True):
        return []

    pipeline.answer("q", search_fn=search_fn, planner="my-planner", critic="my-critic")
    call = fake_run.calls[0]
    assert (call["search_fn"], call["planner"], call["critic"]) == (
        search_fn,
        "my-planner",
        "my-critic",
    )


def test_answer_runs_the_whole_flow_with_a_fake_model(monkeypatch):
    fake = FakeLlm(critic_json='{"approved": true}')
    monkeypatch.setattr(pipeline, "create_critic_agent", lambda: _critic(fake))
    monkeypatch.setattr(
        pipeline, "run_pipeline", functools.partial(pipeline.run_pipeline, models=(fake, fake))
    )
    report = pipeline.answer("low-rank matrices", RunConfig(use_planner=False))
    assert report.question == "low-rank matrices"
    assert "2106.09685" in report.markdown
    assert report.verified is True


def test_answer_with_a_tiny_time_budget_still_returns_an_unverified_report(monkeypatch):
    fake = FakeLlm()
    monkeypatch.setattr(pipeline, "create_critic_agent", lambda: _critic(fake))
    monkeypatch.setattr(
        pipeline, "run_pipeline", functools.partial(pipeline.run_pipeline, models=(fake, fake))
    )

    def search_fn(query, k=8, hybrid=True):
        return [Chunk(paper_id="2106.09685", text="LoRA freezes weights", source_url="u")]

    report = pipeline.answer("q", RunConfig(time_budget_s=0), search_fn=search_fn)
    assert "LoRA freezes weights" in report.markdown
    assert report.verified is False
    assert "Critic" not in fake.instructions


def _critic(fake):
    from agents.critic import create_critic_agent

    return create_critic_agent(fake)
