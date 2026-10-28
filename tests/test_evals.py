import csv

import pytest

from evals.metrics import (
    EvaluationRecord,
    recall_at_k,
    summarize_results,
    write_results_csv,
    write_summary_csv,
)
from evals.questions import EVALUATION_QUESTIONS, validate_question_set


def test_question_ids_are_unique():
    validate_question_set()
    ids = [question.id for question in EVALUATION_QUESTIONS]

    assert len(ids) == len(set(ids))


def test_all_questions_have_expected_sources_and_criteria():
    for question in EVALUATION_QUESTIONS:
        assert question.expected_source_ids
        assert question.evaluation_criteria


def test_recall_at_k_normalizes_arxiv_ids():
    retrieved = [
        "https://arxiv.org/abs/1706.03762v7",
        "arxiv:2005.11401",
    ]
    expected = ["1706.03762"]

    assert recall_at_k(retrieved, expected, k=1) == 1.0


def test_recall_at_k_returns_zero_when_source_is_missing():
    assert recall_at_k(["other-paper"], ["1706.03762"], k=5) == 0.0


def test_recall_at_k_rejects_empty_expected_sources():
    with pytest.raises(ValueError, match="expected source"):
        recall_at_k(["1706.03762"], [], k=5)


def test_recall_at_k_rejects_invalid_k():
    with pytest.raises(ValueError, match="at least 1"):
        recall_at_k(["1706.03762"], ["1706.03762"], k=0)


def test_quality_score_must_be_between_one_and_five():
    with pytest.raises(ValueError, match="between 1 and 5"):
        EvaluationRecord(
            configuration="E0",
            question_id="q001-rag",
            retrieved_source_ids=("2005.11401",),
            expected_source_ids=("2005.11401",),
            report_quality_score=6,
        )


def test_summary_aggregates_metrics_by_configuration():
    records = [
        EvaluationRecord(
            configuration="E0",
            question_id="q001-rag",
            retrieved_source_ids=("2005.11401",),
            expected_source_ids=("2005.11401",),
            report_quality_score=4,
            llm_calls=2,
            input_tokens=100,
            output_tokens=50,
            latency_seconds=1.0,
        ),
        EvaluationRecord(
            configuration="E0",
            question_id="q002-transformer",
            retrieved_source_ids=("wrong-paper",),
            expected_source_ids=("1706.03762",),
            report_quality_score=2,
            llm_calls=1,
            input_tokens=10,
            output_tokens=5,
            latency_seconds=3.0,
        ),
        EvaluationRecord(
            configuration="E1",
            question_id="q001-rag",
            retrieved_source_ids=("2005.11401",),
            expected_source_ids=("2005.11401",),
            report_quality_score=5,
            llm_calls=3,
            input_tokens=200,
            output_tokens=100,
            latency_seconds=2.0,
        ),
    ]

    summaries = summarize_results(records, k=5)
    e0 = summaries[0]
    e1 = summaries[1]

    assert e0.configuration == "E0"
    assert e0.question_count == 2
    assert e0.mean_recall_at_k == 0.5
    assert e0.mean_report_quality_score == 3.0
    assert e0.total_llm_calls == 3
    assert e0.total_tokens == 165
    assert e0.mean_latency_seconds == 2.0

    assert e1.configuration == "E1"
    assert e1.mean_recall_at_k == 1.0


def test_quality_average_ignores_unrated_reports():
    records = [
        EvaluationRecord(
            configuration="E0",
            question_id="q001-rag",
            retrieved_source_ids=("2005.11401",),
            expected_source_ids=("2005.11401",),
            report_quality_score=None,
        ),
    ]

    summary = summarize_results(records)[0]

    assert summary.mean_report_quality_score is None


def test_result_csv_contains_per_question_metrics(tmp_path):
    records = [
        EvaluationRecord(
            configuration="E0",
            question_id="q001-rag",
            retrieved_source_ids=("2005.11401",),
            expected_source_ids=("2005.11401",),
            report_quality_score=4,
            llm_calls=2,
            input_tokens=100,
            output_tokens=50,
            latency_seconds=1.25,
        )
    ]
    output = tmp_path / "results" / "runs.csv"

    write_results_csv(records, output)

    with output.open(encoding="utf-8", newline="") as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert len(rows) == 1
    assert rows[0]["configuration"] == "E0"
    assert rows[0]["question_id"] == "q001-rag"
    assert float(rows[0]["recall_at_k"]) == 1.0
    assert rows[0]["total_tokens"] == "150"


def test_summary_csv_contains_aggregated_metrics(tmp_path):
    records = [
        EvaluationRecord(
            configuration="E0",
            question_id="q001-rag",
            retrieved_source_ids=("2005.11401",),
            expected_source_ids=("2005.11401",),
        )
    ]
    summaries = summarize_results(records)
    output = tmp_path / "summary.csv"

    write_summary_csv(summaries, output)

    with output.open(encoding="utf-8", newline="") as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert len(rows) == 1
    assert rows[0]["configuration"] == "E0"
    assert rows[0]["question_count"] == "1"