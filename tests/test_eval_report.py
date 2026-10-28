
import csv

import pytest

from evals.metrics import EvaluationRecord, write_results_csv
from evals.report import (
    generate_evaluation_report,
    load_results_csv,
    main,
)


def make_record(
    configuration="E0",
    question_id="q001-rag",
    quality=4.0,
):
    return EvaluationRecord(
        configuration=configuration,
        question_id=question_id,
        retrieved_source_ids=("2005.11401",),
        expected_source_ids=("2005.11401",),
        report_quality_score=quality,
        llm_calls=2,
        input_tokens=100,
        output_tokens=50,
        latency_seconds=1.25,
    )


def test_load_results_csv_round_trip(tmp_path):
    source = tmp_path / "results.csv"
    original = [make_record()]

    write_results_csv(original, source)
    loaded = load_results_csv(source)

    assert len(loaded) == 1
    assert loaded[0].configuration == "E0"
    assert loaded[0].question_id == "q001-rag"
    assert loaded[0].report_quality_score == 4.0
    assert loaded[0].input_tokens == 100


def test_load_results_csv_rejects_missing_columns(tmp_path):
    source = tmp_path / "invalid.csv"
    source.write_text("configuration,question_id\nE0,q001\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing columns"):
        load_results_csv(source)


def test_load_results_csv_rejects_empty_data(tmp_path):
    source = tmp_path / "empty.csv"
    write_results_csv([make_record()], source)

    # Keep the header but remove all data rows.
    header = source.read_text(encoding="utf-8").splitlines()[0]
    source.write_text(header + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="no evaluation records"):
        load_results_csv(source)


def test_load_results_csv_rejects_invalid_source_json(tmp_path):
    source = tmp_path / "invalid-source.csv"
    fields = [
        "configuration",
        "question_id",
        "retrieved_source_ids",
        "expected_source_ids",
        "report_quality_score",
        "llm_calls",
        "input_tokens",
        "output_tokens",
        "latency_seconds",
    ]

    with source.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            {
                "configuration": "E0",
                "question_id": "q001-rag",
                "retrieved_source_ids": "not-json",
                "expected_source_ids": '["2005.11401"]',
                "report_quality_score": "4",
                "llm_calls": "1",
                "input_tokens": "10",
                "output_tokens": "5",
                "latency_seconds": "1.0",
            }
        )

    with pytest.raises(ValueError, match="row 2"):
        load_results_csv(source)


def test_generate_report_writes_table_and_charts(tmp_path):
    source = tmp_path / "results.csv"
    output_dir = tmp_path / "nested" / "report"

    records = [
        make_record("E0", "q001-rag", 3.0),
        make_record("E1", "q001-rag", 5.0),
    ]
    write_results_csv(records, source)

    outputs = generate_evaluation_report(source, output_dir, k=5)

    assert outputs["summary_csv"].is_file()
    assert outputs["summary_markdown"].is_file()
    assert outputs["recall_chart"].is_file()
    assert outputs["quality_chart"].is_file()
    assert outputs["token_chart"].is_file()
    assert outputs["latency_chart"].is_file()

    markdown = outputs["summary_markdown"].read_text(encoding="utf-8")
    assert "E0" in markdown
    assert "E1" in markdown
    assert "Recall@5" in markdown


def test_report_skips_quality_chart_when_scores_are_missing(tmp_path):
    source = tmp_path / "results.csv"
    write_results_csv([make_record(quality=None)], source)

    outputs = generate_evaluation_report(source, tmp_path / "report")

    assert outputs["quality_chart"] is None
    assert not (tmp_path / "report" / "report_quality.png").exists()


def test_command_line_entry_point_generates_report(tmp_path):
    source = tmp_path / "results.csv"
    write_results_csv([make_record()], source)
    output_dir = tmp_path / "cli-report"

    result = main(
        [
            str(source),
            "--output-dir",
            str(output_dir),
            "--k",
            "5",
        ]
    )

    assert result == 0
    assert (output_dir / "summary.csv").is_file()
    assert (output_dir / "summary.md").is_file()
