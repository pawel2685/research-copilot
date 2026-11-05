
import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import evals.run_benchmark as benchmark
from agents.stats import RunStats
from contracts import Report
from evals.metrics import EXPERIMENT_CONFIGS
from evals.questions import EVALUATION_QUESTIONS


@pytest.fixture(autouse=True)
def disable_cache(monkeypatch):
    monkeypatch.setattr(benchmark, "cache_enabled", lambda: False)


def fake_run_one(configuration, question, time_budget):
    report = Report(
        question=question,
        markdown=f"# {configuration} report\n\n{question}",
        sources=["2005.11401"],
        verified=True,
    )

    stats = RunStats(
        retrieved_source_ids=("2005.11401",),
        llm_calls=2,
        input_tokens=100,
        output_tokens=50,
        latency_seconds=3.0,
    )

    return report, stats


def base_kwargs(tmp_path):
    return {
        "configurations": ["E1"],
        "question_ids": ["q001-rag"],
        "output_dir": tmp_path,
        "time_budget": 90.0,
        "delay_seconds": 0,
    }


def test_run_benchmark_saves_report_and_measurements(
    tmp_path,
    monkeypatch,
):
    calls = []

    def recording_run(configuration, question, time_budget):
        calls.append((configuration, question, time_budget))
        return fake_run_one(configuration, question, time_budget)

    monkeypatch.setattr(benchmark, "_run_one", recording_run)

    result = benchmark.run_benchmark(**base_kwargs(tmp_path))

    assert result == 0
    assert len(calls) == 1

    report_path = tmp_path / "reports" / "E1_q001-rag.md"
    assert report_path.exists()
    assert "# E1 report" in report_path.read_text(encoding="utf-8")

    results_path = tmp_path / "results.csv"

    with results_path.open(
        encoding="utf-8",
        newline="",
    ) as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 1
    assert rows[0]["configuration"] == "E1"
    assert rows[0]["question_id"] == "q001-rag"
    assert rows[0]["llm_calls"] == "2"
    assert rows[0]["input_tokens"] == "100"
    assert rows[0]["output_tokens"] == "50"


def test_run_benchmark_resumes_without_repeating_successful_run(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(benchmark, "_run_one", fake_run_one)

    first = benchmark.run_benchmark(**base_kwargs(tmp_path))
    assert first == 0

    def should_not_run(*args, **kwargs):
        raise AssertionError("Completed benchmark run was repeated.")

    monkeypatch.setattr(benchmark, "_run_one", should_not_run)

    second = benchmark.run_benchmark(**base_kwargs(tmp_path))
    assert second == 0


def test_run_benchmark_retries_when_saved_report_is_missing(
    tmp_path,
    monkeypatch,
):
    calls = []

    def recording_run(configuration, question, time_budget):
        calls.append(question)
        return fake_run_one(configuration, question, time_budget)

    monkeypatch.setattr(benchmark, "_run_one", recording_run)

    benchmark.run_benchmark(**base_kwargs(tmp_path))

    report_path = tmp_path / "reports" / "E1_q001-rag.md"
    report_path.unlink()

    result = benchmark.run_benchmark(**base_kwargs(tmp_path))

    assert result == 0
    assert len(calls) == 2
    assert report_path.exists()

    with (tmp_path / "results.csv").open(
        encoding="utf-8",
        newline="",
    ) as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 1


def test_run_benchmark_does_not_mark_run_complete_if_report_save_fails(
    tmp_path,
    monkeypatch,
):
    original_write_text = Path.write_text

    def failing_write_text(path, content, *args, **kwargs):
        if path.name == "E1_q001-rag.md":
            raise OSError("Simulated report write failure")

        return original_write_text(path, content, *args, **kwargs)

    monkeypatch.setattr(benchmark, "_run_one", fake_run_one)
    monkeypatch.setattr(Path, "write_text", failing_write_text)

    result = benchmark.run_benchmark(**base_kwargs(tmp_path))

    assert result == 1
    assert not (tmp_path / "results.csv").exists()

    failures_path = tmp_path / "failures.jsonl"
    failures = [
        json.loads(line)
        for line in failures_path.read_text(encoding="utf-8").splitlines()
    ]

    assert len(failures) == 1
    assert failures[0]["error_type"] == "OSError"


def test_run_benchmark_records_pipeline_errors(tmp_path, monkeypatch):
    def failing_run(*args, **kwargs):
        raise RuntimeError("Simulated API failure")

    monkeypatch.setattr(benchmark, "_run_one", failing_run)

    result = benchmark.run_benchmark(**base_kwargs(tmp_path))

    assert result == 1

    failures = [
        json.loads(line)
        for line in (tmp_path / "failures.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]

    assert len(failures) == 1
    assert failures[0]["configuration"] == "E1"
    assert failures[0]["question_id"] == "q001-rag"
    assert failures[0]["error_type"] == "RuntimeError"


def test_run_benchmark_generates_summary_only_after_full_matrix(
    tmp_path,
    monkeypatch,
):
    calls = []
    generated = []

    def recording_run(configuration, question, time_budget):
        calls.append((configuration, question))
        return fake_run_one(configuration, question, time_budget)

    def fake_generate(results_path, output_dir, k):
        generated.append((results_path, output_dir, k))
        return {"summary": output_dir / "summary.md"}

    monkeypatch.setattr(benchmark, "_run_one", recording_run)
    monkeypatch.setattr(
        benchmark,
        "generate_evaluation_report",
        fake_generate,
    )

    result = benchmark.run_benchmark(
        configurations=list(EXPERIMENT_CONFIGS),
        question_ids=[
            question.id for question in EVALUATION_QUESTIONS
        ],
        output_dir=tmp_path,
        delay_seconds=0,
    )

    assert result == 0
    assert len(calls) == 25
    assert len(generated) == 1
    assert generated[0][2] == 5


def test_run_benchmark_rejects_invalid_direct_arguments(tmp_path):
    kwargs = base_kwargs(tmp_path)
    kwargs["question_ids"] = ["unknown-question"]

    with pytest.raises(ValueError, match="Unknown question IDs"):
        benchmark.run_benchmark(**kwargs)


def test_run_benchmark_rejects_duplicate_existing_results(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(benchmark, "_run_one", fake_run_one)

    benchmark.run_benchmark(**base_kwargs(tmp_path))

    results_path = tmp_path / "results.csv"
    lines = results_path.read_text(encoding="utf-8").splitlines()
    results_path.write_text(
        "\n".join(lines + [lines[1]]) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate benchmark result"):
        benchmark.run_benchmark(**base_kwargs(tmp_path))


def test_run_benchmark_rejects_enabled_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark, "cache_enabled", lambda: True)

    with pytest.raises(RuntimeError, match="LLM cache is enabled"):
        benchmark.run_benchmark(**base_kwargs(tmp_path))


def test_run_one_uses_separate_single_call_baseline_for_e0(monkeypatch):
    expected = (object(), object())
    calls = []

    def fake_baseline(question, search_fn, k):
        calls.append((question, search_fn, k))
        return expected

    monkeypatch.setattr(
        benchmark,
        "answer_baseline_with_stats",
        fake_baseline,
    )

    result = benchmark._run_one("E0", "Test question", 90.0)

    assert result is expected
    assert calls == [
        ("Test question", benchmark.default_search, 8)
    ]


def test_run_one_uses_pipeline_for_e1(monkeypatch):
    cfg = SimpleNamespace(time_budget_s=0)
    expected = (object(), object())

    monkeypatch.setattr(
        benchmark,
        "get_run_config",
        lambda name: cfg,
    )
    monkeypatch.setattr(
        benchmark,
        "answer_with_stats",
        lambda question, actual_cfg: expected,
    )

    result = benchmark._run_one("E1", "Test question", 75.0)

    assert result is expected
    assert cfg.time_budget_s == 75.0


def test_run_benchmark_stops_after_rate_limit_and_preserves_results(
    tmp_path,
    monkeypatch,
):
    calls = []

    def rate_limited_run(configuration, question, time_budget):
        calls.append(question)

        if question == EVALUATION_QUESTIONS[0].question:
            return fake_run_one(configuration, question, time_budget)

        raise RuntimeError(
            "429 RESOURCE_EXHAUSTED: quota exceeded."
        )

    monkeypatch.setattr(
        benchmark,
        "_run_one",
        rate_limited_run,
    )

    kwargs = {
        "configurations": ["E1"],
        "question_ids": [
            "q001-rag",
            "q002-transformer",
            "q003-bert",
        ],
        "output_dir": tmp_path,
        "time_budget": 90.0,
        "delay_seconds": 0,
    }

    result = benchmark.run_benchmark(**kwargs)

    # The benchmark must stop immediately after the second call fails.
    assert result == 1
    assert len(calls) == 2

    # The successful first run must remain saved.
    results_path = tmp_path / "results.csv"

    with results_path.open(
        encoding="utf-8",
        newline="",
    ) as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 1
    assert rows[0]["question_id"] == "q001-rag"

    # Its Markdown report must also remain available.
    report_path = tmp_path / "reports" / "E1_q001-rag.md"
    assert report_path.exists()

    # The quota error must be recorded.
    failures_path = tmp_path / "failures.jsonl"
    failures = [
        json.loads(line)
        for line in failures_path.read_text(
            encoding="utf-8"
        ).splitlines()
    ]

    assert len(failures) == 1
    assert "429 RESOURCE_EXHAUSTED" in failures[0]["error"]
