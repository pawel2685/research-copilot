
import json

import pytest

from agents.stats import RunStats
from contracts import Report
from evals.time_budget_experiment import run_time_budget_experiment


def fake_answer(question, cfg):
    budget = int(cfg.time_budget_s)

    report = Report(
        question=question,
        markdown=f"# Report with {budget}s budget",
        sources=["2005.11401"],
        verified=budget == 120,
    )

    stats = RunStats(
        retrieved_source_ids=("2005.11401",),
        llm_calls=4,
        input_tokens=300,
        output_tokens=100,
        latency_seconds=budget / 2,
        planner_skipped_by_deadline=budget == 30,
        critic_skipped_by_deadline=budget < 120,
    )

    return report, stats


def test_time_budget_experiment_saves_results_and_reports(tmp_path):
    calls = []

    def recording_answer(question, cfg):
        calls.append((question, cfg.time_budget_s))
        return fake_answer(question, cfg)

    result = run_time_budget_experiment(
        budgets=(30, 60),
        question_ids=("q001-rag", "q002-transformer"),
        output_dir=tmp_path,
        delay_seconds=0,
        answer_fn=recording_answer,
    )

    assert result == {
        "successful": 4,
        "new_successful": 4,
        "errors": 0,
        "missing": 0,
    }
    assert len(calls) == 4

    results_path = tmp_path / "time_budget_results.jsonl"
    records = [
        json.loads(line)
        for line in results_path.read_text(encoding="utf-8").splitlines()
    ]

    assert len(records) == 4
    assert {record["budget_seconds"] for record in records} == {30, 60}
    assert all(record["configuration"] == "E4" for record in records)

    low_budget = next(
        record for record in records
        if record["budget_seconds"] == 30
    )

    assert low_budget["planner_skipped_by_deadline"] is True
    assert low_budget["critic_skipped_by_deadline"] is True
    assert low_budget["total_tokens"] == 400

    assert (tmp_path / "time_budget_summary.csv").exists()
    assert (tmp_path / "time_budget_summary.md").exists()

    report_files = list((tmp_path / "reports").glob("*.md"))
    assert len(report_files) == 4


def test_time_budget_experiment_resumes_without_repeating_runs(tmp_path):
    first = run_time_budget_experiment(
        budgets=(30,),
        question_ids=("q001-rag",),
        output_dir=tmp_path,
        delay_seconds=0,
        answer_fn=fake_answer,
    )

    assert first["new_successful"] == 1

    def should_not_run(question, cfg):
        raise AssertionError("Completed run should not be repeated.")

    second = run_time_budget_experiment(
        budgets=(30,),
        question_ids=("q001-rag",),
        output_dir=tmp_path,
        delay_seconds=0,
        answer_fn=should_not_run,
    )

    assert second["successful"] == 1
    assert second["new_successful"] == 0
    assert second["missing"] == 0


def test_time_budget_experiment_rejects_invalid_budgets(tmp_path):
    with pytest.raises(ValueError, match="positive"):
        run_time_budget_experiment(
            budgets=(30, 0),
            output_dir=tmp_path,
            delay_seconds=0,
            answer_fn=fake_answer,
        )


def test_time_budget_experiment_rejects_duplicate_budgets(tmp_path):
    with pytest.raises(ValueError, match="unique"):
        run_time_budget_experiment(
            budgets=(30, 30),
            output_dir=tmp_path,
            delay_seconds=0,
            answer_fn=fake_answer,
        )


def test_time_budget_experiment_rejects_unknown_question(tmp_path):
    with pytest.raises(ValueError, match="Unknown question IDs"):
        run_time_budget_experiment(
            budgets=(30,),
            question_ids=("unknown-question",),
            output_dir=tmp_path,
            delay_seconds=0,
            answer_fn=fake_answer,
        )

def test_stops_after_rate_limit_and_preserves_failure(tmp_path):
    from evals.time_budget_experiment import run_time_budget_experiment

    class _ResourceExhaustedError(Exception):
        pass

    calls = []

    def fake_answer(question, config):
        calls.append(question)
        raise _ResourceExhaustedError(
            "429 RESOURCE_EXHAUSTED: quota exceeded"
        )

    result = run_time_budget_experiment(
        budgets=(30, 60),
        question_ids=("q001-rag", "q002-transformer"),
        output_dir=tmp_path,
        delay_seconds=0,
        answer_fn=fake_answer,
    )

    assert len(calls) == 1
    assert result["successful"] == 0
    assert result["new_successful"] == 0
    assert result["errors"] == 1
    assert result["missing"] == 4

    failures_path = tmp_path / "time_budget_failures.jsonl"
    failures = failures_path.read_text(encoding="utf-8").splitlines()

    assert len(failures) == 1
    assert "RESOURCE_EXHAUSTED" in failures[0]

    assert (tmp_path / "time_budget_summary.csv").exists()