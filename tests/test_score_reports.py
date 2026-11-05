
import csv
import json
import pytest

from pathlib import Path

from agents.stats import RunStats
from evals.quality_judge import QualityJudgement
from evals.score_reports import score_results
from evals.metrics import EXPERIMENT_CONFIGS
from evals.questions import EVALUATION_QUESTIONS

FIELDNAMES = [
    "configuration",
    "question_id",
    "recall_at_k",
    "k",
    "report_quality_score",
    "llm_calls",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "latency_seconds",
    "retrieved_source_ids",
    "expected_source_ids",
]


def create_results_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def make_result_row(
    question_id="q001-rag",
    configuration="E0",
    quality_score="",
):
    return {
        "configuration": configuration,
        "question_id": question_id,
        "recall_at_k": "1.0",
        "k": "5",
        "report_quality_score": quality_score,
        "llm_calls": "3",
        "input_tokens": "1000",
        "output_tokens": "500",
        "total_tokens": "1500",
        "latency_seconds": "12.5",
        "retrieved_source_ids": '["2005.11401"]',
        "expected_source_ids": '["2005.11401"]',
    }


def test_score_results_saves_score_and_separate_judge_usage(tmp_path):
    results_path = tmp_path / "results.csv"
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()

    judgements_path = tmp_path / "quality_judgements.jsonl"
    failures_path = tmp_path / "quality_failures.jsonl"
    manual_path = tmp_path / "manual_review.csv"

    create_results_csv(results_path, [make_result_row()])

    report_text = "# RAG report\n\nRAG combines two types of memory."
    (reports_dir / "E0_q001-rag.md").write_text(
        report_text,
        encoding="utf-8",
    )

    def fake_judge(question, report, retrieved_source_ids=()):
        assert question.id == "q001-rag"
        assert report == report_text
        assert retrieved_source_ids == ("2005.11401",)

        judgement = QualityJudgement(
            relevance=5,
            coverage=4,
            factual_support=4,
            citation_quality=3,
            rationale="The report is relevant but citations need improvement.",
            warnings=["Citation details could be more precise."],
        )

        stats = RunStats(
            retrieved_source_ids=(),
            llm_calls=1,
            input_tokens=400,
            output_tokens=80,
            latency_seconds=1.5,
        )

        return judgement, stats

    counts = score_results(
        results_path=results_path,
        reports_dir=reports_dir,
        judgements_path=judgements_path,
        failures_path=failures_path,
        manual_review_path=manual_path,
        limit=5,
        delay_seconds=0,
        judge_fn=fake_judge,
    )

    with results_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert rows[0]["report_quality_score"] == "4.0"

    # The original pipeline cost must remain unchanged.
    assert rows[0]["llm_calls"] == "3"
    assert rows[0]["input_tokens"] == "1000"
    assert rows[0]["output_tokens"] == "500"
    assert rows[0]["latency_seconds"] == "12.5"

    assert counts["newly_scored"] == 1
    assert counts["failed"] == 0

    with judgements_path.open(encoding="utf-8") as file:
        saved = json.loads(file.readline())

    assert saved["key"] == "E0::q001-rag"
    assert saved["overall_score"] == 4.0
    assert saved["judge_usage"]["llm_calls"] == 1
    assert saved["judge_usage"]["total_tokens"] == 480

    with manual_path.open(encoding="utf-8", newline="") as file:
        manual_rows = list(csv.DictReader(file))

    assert len(manual_rows) == 25


def test_score_results_restores_judgement_without_api_call(tmp_path):
    results_path = tmp_path / "results.csv"
    reports_dir = tmp_path / "reports"

    judgements_path = tmp_path / "quality_judgements.jsonl"
    failures_path = tmp_path / "quality_failures.jsonl"
    manual_path = tmp_path / "manual_review.csv"

    create_results_csv(results_path, [make_result_row()])

    judgement = QualityJudgement(
        relevance=4,
        coverage=4,
        factual_support=4,
        citation_quality=4,
        rationale="Consistent quality.",
    )

    saved = {
        "key": "E0::q001-rag",
        "configuration": "E0",
        "question_id": "q001-rag",
        "judgement": judgement.model_dump(),
        "overall_score": 4.0,
        "judge_usage": {
            "llm_calls": 1,
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "latency_seconds": 1.0,
        },
    }

    judgements_path.write_text(
        json.dumps(saved) + "\n",
        encoding="utf-8",
    )

    def should_not_call_judge(*args, **kwargs):
        raise AssertionError("Saved judgement should be restored.")

    counts = score_results(
        results_path=results_path,
        reports_dir=reports_dir,
        judgements_path=judgements_path,
        failures_path=failures_path,
        manual_review_path=manual_path,
        limit=5,
        delay_seconds=0,
        judge_fn=should_not_call_judge,
    )

    with results_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert rows[0]["report_quality_score"] == "4.0"
    assert counts["restored_from_log"] == 1
    assert counts["newly_scored"] == 0


def test_score_results_records_missing_report(tmp_path):
    results_path = tmp_path / "results.csv"
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()

    judgements_path = tmp_path / "quality_judgements.jsonl"
    failures_path = tmp_path / "quality_failures.jsonl"
    manual_path = tmp_path / "manual_review.csv"

    create_results_csv(results_path, [make_result_row()])

    counts = score_results(
        results_path=results_path,
        reports_dir=reports_dir,
        judgements_path=judgements_path,
        failures_path=failures_path,
        manual_review_path=manual_path,
        limit=5,
        delay_seconds=0,
        judge_fn=lambda *args, **kwargs: None,
    )

    assert counts["failed"] == 1
    assert failures_path.exists()

    failure = json.loads(
        failures_path.read_text(encoding="utf-8").splitlines()[0]
    )

    assert failure["key"] == "E0::q001-rag"
    assert failure["error_type"] == "FileNotFoundError"


def test_score_results_respects_limit_after_api_failure(tmp_path):
    results_path = tmp_path / "results.csv"
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()

    for question_id in ("q001-rag", "q002-transformer"):
        (reports_dir / f"E0_{question_id}.md").write_text(
            "# Test report",
            encoding="utf-8",
        )

    create_results_csv(
        results_path,
        [
            make_result_row(question_id="q001-rag"),
            make_result_row(question_id="q002-transformer"),
        ],
    )

    calls = []

    def failing_judge(question, report, retrieved_source_ids=()):
        calls.append(question.id)
        raise RuntimeError("Simulated API failure")

    counts = score_results(
        results_path=results_path,
        reports_dir=reports_dir,
        judgements_path=tmp_path / "quality_judgements.jsonl",
        failures_path=tmp_path / "quality_failures.jsonl",
        manual_review_path=tmp_path / "manual_review.csv",
        limit=1,
        delay_seconds=0,
        judge_fn=failing_judge,
    )

    assert calls == ["q001-rag"]
    assert counts["failed"] == 1
    assert counts["newly_scored"] == 0


def test_score_results_rejects_unexpected_benchmark_combination(tmp_path):
    results_path = tmp_path / "results.csv"

    rows = []

    for configuration in EXPERIMENT_CONFIGS:
        for question in EVALUATION_QUESTIONS:
            current_configuration = configuration

            # Replace one valid combination with an invalid configuration.
            if configuration == "E0" and question.id == "q001-rag":
                current_configuration = "E5"

            rows.append(
                make_result_row(
                    question_id=question.id,
                    configuration=current_configuration,
                    quality_score="4.0",
                )
            )

    create_results_csv(results_path, rows)

    with pytest.raises(
        ValueError,
        match="Unexpected benchmark result: E5::q001-rag",
    ):
        score_results(
            results_path=results_path,
            reports_dir=tmp_path / "reports",
            judgements_path=tmp_path / "quality_judgements.jsonl",
            failures_path=tmp_path / "quality_failures.jsonl",
            manual_review_path=tmp_path / "manual_review.csv",
            limit=1,
            delay_seconds=0,
        )
