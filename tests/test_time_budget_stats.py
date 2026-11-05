
from agents import pipeline
from agents.critic import critic_skipped_result
from agents.runner import PipelineResult
from agents.stats import RunStats
from contracts import RunConfig


def test_answer_with_stats_exposes_deadline_skip_flags(monkeypatch):
    planner = object()
    critic = object()

    async def fake_run_pipeline(question, cfg, **kwargs):
        assert question == "Test question"
        assert cfg.use_planner is True
        assert cfg.use_critic is True
        assert kwargs["planner"] is planner
        assert kwargs["critic"] is critic

        return PipelineResult(
            report_markdown="# Test report",
            sub_questions=["Test question"],
            critic_result=critic_skipped_result(
                "Critic skipped because the time budget was insufficient."
            ),
            state={
                "planner_skipped_by_deadline": True,
                "critic_skipped_by_deadline": True,
            },
            retrieved_source_ids=("2005.11401",),
            llm_calls=3,
            input_tokens=400,
            output_tokens=120,
        )

    monkeypatch.setattr(
        pipeline,
        "run_pipeline",
        fake_run_pipeline,
    )
    monkeypatch.setattr(
        pipeline,
        "cache_enabled",
        lambda: False,
    )

    report, stats = pipeline.answer_with_stats(
        "Test question",
        RunConfig(use_planner=True, use_critic=True),
        planner=planner,
        critic=critic,
    )

    assert report.markdown == "# Test report"
    assert stats.llm_calls == 3
    assert stats.input_tokens == 400
    assert stats.output_tokens == 120

    assert stats.planner_skipped_by_deadline is True
    assert stats.critic_skipped_by_deadline is True


def test_run_stats_skip_flags_default_to_false():
    stats = RunStats(
        retrieved_source_ids=(),
        llm_calls=0,
        input_tokens=0,
        output_tokens=0,
        latency_seconds=0.0,
    )

    assert stats.planner_skipped_by_deadline is False
    assert stats.critic_skipped_by_deadline is False
