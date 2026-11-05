import csv
import json
import pytest

from types import SimpleNamespace
from evals.score_time_budget import score_time_budget_reports


def create_experiment_files(tmp_path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()

    records = []

    for budget, question_id in (
        (30, "q001-rag"),
        (60, "q001-rag"),
    ):
        report_path = reports_dir / f"budget_{budget}s_{question_id}.md"
        report_path.write_text(
            f"# Report generated with {budget}s budget",
            encoding="utf-8",
        )

        records.append(
            {
                "configuration": "E4",
                "budget_seconds": budget,
                "question_id": question_id,
                "report_file": str(report_path),
                "retrieved_source_ids": ["2005.11401"],
                "llm_calls": 4,
                "input_tokens": 300,
                "output_tokens": 100,
                "total_tokens": 400,
                "latency_seconds": budget / 2,
                "planner_skipped_by_deadline": budget == 30,
                "critic_skipped_by_deadline": budget < 60,
                "verified": budget == 60,
            }
        )

    results_path = tmp_path / "time_budget_results.jsonl"
    results_path.write_text(
        "".join(
            json.dumps(record) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )

    return records


def fake_judge(question, report_markdown, retrieved_source_ids):
    assert question.id == "q001-rag"
    assert report_markdown.startswith("# Report generated")
    assert retrieved_source_ids == ("2005.11401",)

    judgement = SimpleNamespace(
        relevance=4,
        coverage=5,
        factual_support=4,
        citation_quality=3,
        overall_score=4.0,
        rationale="The report addresses the question.",
        warnings=[],
    )

    usage = SimpleNamespace(
        llm_calls=1,
        input_tokens=200,
        output_tokens=50,
        latency_seconds=1.2,
    )

    return judgement, usage


def test_score_time_budget_reports_respects_limit_and_saves_results(
    tmp_path,
):
    create_experiment_files(tmp_path)
    calls = []

    def recording_judge(question, report_markdown, source_ids):
        calls.append(report_markdown)
        return fake_judge(question, report_markdown, source_ids)

    result = score_time_budget_reports(
        output_dir=tmp_path,
        limit=1,
        delay_seconds=0,
        judge_fn=recording_judge,
    )

    assert result == {
        "experiment_runs": 2,
        "judged": 1,
        "new_requests": 1,
        "errors": 0,
        "missing": 1,
    }

    assert len(calls) == 1

    judgement_path = tmp_path / "quality_judgements.jsonl"
    judgements = [
        json.loads(line)
        for line in judgement_path.read_text(
            encoding="utf-8"
        ).splitlines()
    ]

    assert len(judgements) == 1
    assert judgements[0]["judgement"]["overall_score"] == 4.0
    assert judgements[0]["judge_usage"]["llm_calls"] == 1

    assert (tmp_path / "time_budget_quality_summary.csv").exists()
    assert (tmp_path / "time_budget_quality_summary.md").exists()
    assert (tmp_path / "quality_vs_time_budget.png").exists()
    assert (tmp_path / "skips_vs_time_budget.png").exists()


def test_score_time_budget_reports_resumes_without_rejudging(
    tmp_path,
):
    create_experiment_files(tmp_path)

    first = score_time_budget_reports(
        output_dir=tmp_path,
        limit=1,
        delay_seconds=0,
        judge_fn=fake_judge,
    )

    assert first["judged"] == 1
    assert first["new_requests"] == 1

    calls = []

    def recording_judge(question, report_markdown, source_ids):
        calls.append(report_markdown)
        return fake_judge(question, report_markdown, source_ids)

    second = score_time_budget_reports(
        output_dir=tmp_path,
        delay_seconds=0,
        judge_fn=recording_judge,
    )

    assert second["judged"] == 2
    assert second["new_requests"] == 1
    assert second["missing"] == 0
    assert len(calls) == 1


def test_score_time_budget_reports_records_judge_errors(tmp_path):
    create_experiment_files(tmp_path)

    def failing_judge(question, report_markdown, source_ids):
        raise RuntimeError("Simulated API error")

    result = score_time_budget_reports(
        output_dir=tmp_path,
        limit=1,
        delay_seconds=0,
        judge_fn=failing_judge,
    )

    assert result["new_requests"] == 1
    assert result["errors"] == 1
    assert result["judged"] == 0
    assert result["missing"] == 2

    failures_path = tmp_path / "quality_failures.jsonl"
    failures = [
        json.loads(line)
        for line in failures_path.read_text(
            encoding="utf-8"
        ).splitlines()
    ]

    assert len(failures) == 1
    assert failures[0]["error_type"] == "RuntimeError"


def test_score_time_budget_reports_rejects_missing_results(tmp_path):
    import pytest

    with pytest.raises(ValueError, match="No experiment results"):
        score_time_budget_reports(
            output_dir=tmp_path,
            delay_seconds=0,
            judge_fn=fake_judge,
        )


def test_quality_summary_contains_skip_rates(tmp_path):
    create_experiment_files(tmp_path)

    score_time_budget_reports(
        output_dir=tmp_path,
        delay_seconds=0,
        judge_fn=fake_judge,
    )

    summary_path = tmp_path / "time_budget_quality_summary.csv"

    with summary_path.open(
        encoding="utf-8",
        newline="",
    ) as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 2

    budget_30 = next(
        row for row in rows
        if row["budget_seconds"] == "30"
    )

    assert budget_30["planner_skip_rate"] == "1.0"
    assert budget_30["critic_skip_rate"] == "1.0"
    assert budget_30["mean_quality_score"] == "4.0"


def test_score_time_budget_rejects_duplicate_experiment_results(tmp_path):
    records = create_experiment_files(tmp_path)

    results_path = tmp_path / "time_budget_results.jsonl"

    with results_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(records[0]) + "\n")

    with pytest.raises(
        ValueError,
        match="Duplicate time-budget experiment result",
    ):
        score_time_budget_reports(
            output_dir=tmp_path,
            delay_seconds=0,
            judge_fn=fake_judge,
        )


def test_score_time_budget_rejects_duplicate_judgements(tmp_path):
    create_experiment_files(tmp_path)

    judgement = {
        "budget_seconds": 30,
        "question_id": "q001-rag",
        "judgement": {"overall_score": 4.0},
    }

    judgements_path = tmp_path / "quality_judgements.jsonl"
    judgements_path.write_text(
        json.dumps(judgement) + "\n"
        + json.dumps(judgement) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Duplicate time-budget judgement",
    ):
        score_time_budget_reports(
            output_dir=tmp_path,
            delay_seconds=0,
            judge_fn=fake_judge,
        )
