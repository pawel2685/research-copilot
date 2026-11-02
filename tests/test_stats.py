import asyncio
import logging
from types import SimpleNamespace

import pytest
from google.adk.events import Event, EventActions
from google.genai import types

from agents import pipeline, runner
from agents.critic import CriticResult, critic_skipped_result
from agents.runner import PipelineResult, run_pipeline
from agents.stats import RecordingSearch, RunStats, UsageCounter
from contracts import Chunk, Report, RunConfig
from tests.fake_llm import FakeLlm


def _usage(prompt=None, candidates=None, thoughts=None):
    return types.GenerateContentResponseUsageMetadata(
        prompt_token_count=prompt,
        candidates_token_count=candidates,
        thoughts_token_count=thoughts,
    )


def _event(usage=None, partial=None, delta=None):
    return Event(
        author="a",
        usage_metadata=usage,
        partial=partial,
        actions=EventActions(state_delta=delta or {}),
    )


# --- UsageCounter -------------------------------------------------------------


def test_usage_adds_up_over_events():
    counter = UsageCounter()
    for event in (_event(_usage(100, 20)), _event(_usage(50, 5)), _event(_usage(10, 1))):
        counter.add(event)
    assert (counter.llm_calls, counter.input_tokens, counter.output_tokens) == (3, 160, 26)


def test_events_without_usage_data_count_as_zero():
    counter = UsageCounter()
    counter.add(_event())
    counter.add(SimpleNamespace())  # not even the attribute
    assert (counter.llm_calls, counter.input_tokens, counter.output_tokens) == (0, 0, 0)


def test_missing_token_counts_inside_usage_data_count_as_zero():
    counter = UsageCounter()
    counter.add(_event(_usage(prompt=7)))
    assert (counter.llm_calls, counter.input_tokens, counter.output_tokens) == (1, 7, 0)


def test_thinking_tokens_count_as_output():
    counter = UsageCounter()
    counter.add(_event(_usage(10, 5, 30)))
    assert counter.output_tokens == 35


def test_partial_chunks_are_not_counted():
    counter = UsageCounter()
    counter.add(_event(_usage(10, 5), partial=True))
    assert counter.llm_calls == 0


# --- RecordingSearch ----------------------------------------------------------


def test_recording_search_remembers_papers_in_order_without_duplicates():
    calls = []
    results = {
        "a": [Chunk(paper_id="2", text="x"), Chunk(paper_id="1", text="y")],
        "b": [Chunk(paper_id="1", text="z"), Chunk(paper_id="3", text="w")],
    }

    def search_fn(query, k=8, hybrid=True):
        calls.append((query, k, hybrid))
        return results[query]

    recorder = RecordingSearch(search_fn)
    assert recorder("a", k=3, hybrid=False) == results["a"]
    recorder("b")
    assert recorder.source_ids == ["2", "1", "3"]
    assert calls == [("a", 3, False), ("b", 8, True)]


# --- the runner collects the stats -------------------------------------------


class UsageRunner:
    """Fake ADK Runner: every run yields events with usage data and a scripted state."""

    runs = 0
    script = {}

    def __init__(self, *, app_name, agent, session_service):
        self.app_name, self.agent, self.service = app_name, agent, session_service

    async def run_async(self, *, user_id, session_id, new_message):
        UsageRunner.runs += 1
        session = await self.service.get_session(
            app_name=self.app_name, user_id=user_id, session_id=session_id
        )
        delta = UsageRunner.script.get(self.agent.name, {})
        for event in (
            _event(_usage(100, 10)),
            _event(),  # a tool result: no usage data
            _event(_usage(200, 20), delta=delta),
        ):
            await self.service.append_event(session, event)
            yield event


@pytest.fixture
def usage_runner(monkeypatch):
    UsageRunner.runs = 0
    UsageRunner.script = {}
    monkeypatch.setattr(runner, "Runner", UsageRunner)
    return UsageRunner


def _run(cfg=None, **kwargs):
    return asyncio.run(run_pipeline("q", cfg, models=("l", "h"), **kwargs))


def test_result_has_the_usage_of_the_events(usage_runner):
    result = _run()
    assert (result.llm_calls, result.input_tokens, result.output_tokens) == (2, 300, 30)


def test_events_without_usage_data_give_zero_counts(monkeypatch):
    class Silent(UsageRunner):
        async def run_async(self, *, user_id, session_id, new_message):
            yield _event()

    monkeypatch.setattr(runner, "Runner", Silent)
    result = _run()
    assert (result.llm_calls, result.input_tokens, result.output_tokens) == (0, 0, 0)


def test_the_revision_run_is_counted_too(usage_runner):
    usage_runner.script = {
        "research_pipeline": {
            "report_markdown": "draft",
            "critic_result": {"approved": False, "revision_instructions": ["fix"]},
        },
        "writer": {"report_markdown": "revised"},
    }
    result = _run()
    assert usage_runner.runs == 2
    assert (result.llm_calls, result.input_tokens, result.output_tokens) == (4, 600, 60)


def test_the_result_lists_the_retrieved_papers_in_rank_order(usage_runner, monkeypatch):
    def search_fn(query, k=8, hybrid=True):
        return [Chunk(paper_id="2", text="a"), Chunk(paper_id="1", text="b")]

    # The fake runner runs no agent, so call the tool the pipeline would have built.
    class Searching(UsageRunner):
        async def run_async(self, *, user_id, session_id, new_message):
            tool = self.agent.sub_agents[0].sub_agents[0].sub_agents[0].tools[0]
            tool("q")
            async for event in super().run_async(
                user_id=user_id, session_id=session_id, new_message=new_message
            ):
                yield event

    monkeypatch.setattr(runner, "Runner", Searching)
    result = _run(search_fn=search_fn)
    assert result.retrieved_source_ids == ("2", "1")


def test_full_flow_with_a_fake_model_reports_calls_tokens_and_papers():
    fake = FakeLlm(prompt_tokens=10, completion_tokens=5)
    result = asyncio.run(
        run_pipeline(
            "low-rank matrices",
            RunConfig(use_planner=False, use_critic=False),
            models=(fake, fake),
        )
    )
    # searcher (tool call + answer), reader, writer
    assert result.llm_calls == 4
    assert (result.input_tokens, result.output_tokens) == (40, 20)
    assert result.retrieved_source_ids[0] == "2106.09685"
    assert len(result.retrieved_source_ids) == len(set(result.retrieved_source_ids))


def test_retrieval_is_recorded_before_compression():
    def search_fn(query, k=8, hybrid=True):
        return [Chunk(paper_id=str(n), text="one two three") for n in range(1, 4)]

    fake = FakeLlm()
    cfg = RunConfig(use_planner=False, use_critic=False, compress_budget_words=3)
    result = asyncio.run(run_pipeline("q", cfg, search_fn=search_fn, models=(fake, fake)))
    assert result.retrieved_source_ids == ("1", "2", "3")
    assert '"2"' not in result.state["search_results_1"]  # compression dropped it


# --- answer_with_stats --------------------------------------------------------


def _result(**kwargs):
    return PipelineResult(
        report_markdown="# R",
        sub_questions=["q"],
        critic_result=kwargs.pop("critic_result", critic_skipped_result()),
        state={"reading_notes_1": "[2106.09685]"},
        **kwargs,
    )


@pytest.fixture
def fake_pipeline(monkeypatch):
    calls = []

    async def fake_run(question, cfg, **kwargs):
        calls.append(kwargs)
        return _result(
            critic_result=CriticResult(approved=True),
            retrieved_source_ids=("2106.09685", "1706.03762"),
            llm_calls=5,
            input_tokens=900,
            output_tokens=80,
        )

    monkeypatch.setattr(pipeline, "run_pipeline", fake_run)
    monkeypatch.setattr(pipeline, "create_critic_agent", lambda: "critic")
    return calls


def test_answer_with_stats_returns_the_report_and_the_stats(fake_pipeline, monkeypatch):
    monkeypatch.setenv("LLM_CACHE", "off")
    report, stats = pipeline.answer_with_stats("q", RunConfig())
    assert isinstance(report, Report)
    assert report.sources == ["2106.09685"]
    assert report.verified is True
    assert isinstance(stats, RunStats)
    assert stats.retrieved_source_ids == ("2106.09685", "1706.03762")
    assert (stats.llm_calls, stats.input_tokens, stats.output_tokens) == (5, 900, 80)
    assert stats.latency_seconds >= 0


def test_latency_is_the_wall_clock_time_of_the_run(monkeypatch):
    monkeypatch.setenv("LLM_CACHE", "off")
    ticks = iter([100.0, 102.5])
    monkeypatch.setattr(pipeline.time, "perf_counter", lambda: next(ticks))

    async def fake_run(question, cfg, **kwargs):
        return _result()

    monkeypatch.setattr(pipeline, "run_pipeline", fake_run)
    _, stats = pipeline.answer_with_stats("q", RunConfig(use_critic=False))
    assert stats.latency_seconds == 2.5


def test_stats_without_usage_data_are_zero(monkeypatch):
    monkeypatch.setenv("LLM_CACHE", "off")

    async def fake_run(question, cfg, **kwargs):
        return _result()

    monkeypatch.setattr(pipeline, "run_pipeline", fake_run)
    _, stats = pipeline.answer_with_stats("q", RunConfig(use_critic=False))
    assert (stats.llm_calls, stats.input_tokens, stats.output_tokens) == (0, 0, 0)
    assert stats.retrieved_source_ids == ()


def test_warns_when_the_cache_is_on(fake_pipeline, monkeypatch, caplog):
    monkeypatch.setenv("LLM_CACHE", "on")
    with caplog.at_level(logging.WARNING, logger="agents.pipeline"):
        pipeline.answer_with_stats("q", RunConfig())
    assert "LLM_CACHE" in caplog.text


def test_does_not_warn_when_the_cache_is_off(fake_pipeline, monkeypatch, caplog):
    monkeypatch.setenv("LLM_CACHE", "off")
    with caplog.at_level(logging.WARNING, logger="agents.pipeline"):
        pipeline.answer_with_stats("q", RunConfig())
    assert caplog.text == ""


def test_plain_answer_does_not_warn_and_returns_only_the_report(
    fake_pipeline, monkeypatch, caplog
):
    monkeypatch.setenv("LLM_CACHE", "on")
    with caplog.at_level(logging.WARNING, logger="agents.pipeline"):
        report = pipeline.answer("q", RunConfig())
    assert isinstance(report, Report)
    assert caplog.text == ""


def test_the_search_function_the_caller_gave_is_passed_on(fake_pipeline, monkeypatch):
    monkeypatch.setenv("LLM_CACHE", "off")

    def search_fn(query, k=8, hybrid=True):
        return []

    pipeline.answer_with_stats("q", RunConfig(), search_fn=search_fn)
    assert fake_pipeline[0]["search_fn"] is search_fn
