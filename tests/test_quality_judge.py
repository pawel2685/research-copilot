
import pytest

from evals.questions import EVALUATION_QUESTIONS
from evals.quality_judge import QualityJudgement, judge_report


def test_judge_report_returns_structured_score_and_separate_usage(
    monkeypatch,
):
    import evals.quality_judge as judge_module

    question = EVALUATION_QUESTIONS[0]

    expected_output = {
        "relevance": 5,
        "coverage": 4,
        "factual_support": 4,
        "citation_quality": 3,
        "rationale": "The report answers the question but has some citation gaps.",
        "warnings": ["Some claims need more precise citations."],
    }

    async def fake_run(agent, prompt, state, usage):
        assert agent.name == "quality_judge"
        assert agent.output_key == "quality_judgement"
        assert agent.output_schema is QualityJudgement
        assert question.question in prompt
        assert question.reference_title in prompt
        assert "2005.11401" in prompt
        assert "REPORT START" in prompt

        usage.llm_calls = 1
        usage.input_tokens = 500
        usage.output_tokens = 100

        return {"quality_judgement": expected_output}

    monkeypatch.setattr(
        judge_module,
        "load_models",
        lambda: ("light-model", "heavy-model"),
    )
    monkeypatch.setattr(
        judge_module,
        "harden_agent",
        lambda agent: agent,
    )
    monkeypatch.setattr(
        judge_module,
        "_run_agent",
        fake_run,
    )

    judgement, stats = judge_report(
        question,
        "# RAG report\n\nRAG combines two types of memory. [2005.11401]",
        retrieved_source_ids=("2005.11401",),
    )

    assert judgement.overall_score == 4.0
    assert judgement.relevance == 5
    assert judgement.coverage == 4
    assert judgement.factual_support == 4
    assert judgement.citation_quality == 3
    assert len(judgement.warnings) == 1

    assert stats.llm_calls == 1
    assert stats.input_tokens == 500
    assert stats.output_tokens == 100
    assert stats.latency_seconds >= 0


def test_judge_report_accepts_json_output(monkeypatch):
    import evals.quality_judge as judge_module

    output = QualityJudgement(
        relevance=4,
        coverage=4,
        factual_support=3,
        citation_quality=5,
        rationale="Clear answer with relevant citations.",
    ).model_dump_json()

    async def fake_run(agent, prompt, state, usage):
        usage.llm_calls = 1
        return {"quality_judgement": output}

    monkeypatch.setattr(
        judge_module,
        "load_models",
        lambda: ("light-model", "heavy-model"),
    )
    monkeypatch.setattr(
        judge_module,
        "harden_agent",
        lambda agent: agent,
    )
    monkeypatch.setattr(
        judge_module,
        "_run_agent",
        fake_run,
    )

    judgement, _ = judge_report(
        EVALUATION_QUESTIONS[3],
        "# LoRA report",
    )

    assert judgement.overall_score == 4.0


def test_judge_report_rejects_empty_report():
    with pytest.raises(ValueError, match="must not be empty"):
        judge_report(
            EVALUATION_QUESTIONS[0],
            "",
        )


def test_quality_judgement_rejects_scores_outside_range():
    with pytest.raises(ValueError):
        QualityJudgement(
            relevance=6,
            coverage=4,
            factual_support=4,
            citation_quality=4,
            rationale="Invalid score.",
        )
