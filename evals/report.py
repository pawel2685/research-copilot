
"""Generate comparison tables and charts from evaluation CSV results."""

import argparse
import csv
import json
from pathlib import Path
from typing import Sequence

from evals.metrics import (
    EvaluationRecord,
    EvaluationSummary,
    summarize_results,
    write_summary_csv,
)


REQUIRED_COLUMNS = {
    "configuration",
    "question_id",
    "retrieved_source_ids",
    "expected_source_ids",
    "report_quality_score",
    "llm_calls",
    "input_tokens",
    "output_tokens",
    "latency_seconds",
}


def _parse_source_ids(value: str, column: str, row_number: int) -> tuple[str, ...]:
    """Parse a JSON array of source identifiers from a CSV cell."""
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in column '{column}', row {row_number}."
        ) from exc

    if not isinstance(parsed, list) or not all(
        isinstance(item, str) for item in parsed
    ):
        raise ValueError(
            f"Column '{column}' must contain a JSON array of strings "
            f"(row {row_number})."
        )

    return tuple(parsed)


def load_results_csv(path: str | Path) -> list[EvaluationRecord]:
    """Load per-question measurements previously exported by metrics.py."""
    target = Path(path)

    with target.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)

        if reader.fieldnames is None:
            raise ValueError("The input CSV has no header.")

        missing = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            raise ValueError(
                f"Input CSV is missing columns: {', '.join(sorted(missing))}"
            )

        records = []

        for row_number, row in enumerate(reader, start=2):
            try:
                quality_text = row["report_quality_score"]
                quality = (
                    float(quality_text) if quality_text.strip() else None
                )

                record = EvaluationRecord(
                    configuration=row["configuration"],
                    question_id=row["question_id"],
                    retrieved_source_ids=_parse_source_ids(
                        row["retrieved_source_ids"],
                        "retrieved_source_ids",
                        row_number,
                    ),
                    expected_source_ids=_parse_source_ids(
                        row["expected_source_ids"],
                        "expected_source_ids",
                        row_number,
                    ),
                    report_quality_score=quality,
                    llm_calls=int(row["llm_calls"]),
                    input_tokens=int(row["input_tokens"]),
                    output_tokens=int(row["output_tokens"]),
                    latency_seconds=float(row["latency_seconds"]),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"Invalid evaluation data in CSV row {row_number}: {exc}"
                ) from exc

            records.append(record)

    if not records:
        raise ValueError("The input CSV contains no evaluation records.")

    return records


def write_summary_markdown(
    summaries: Sequence[EvaluationSummary],
    output_path: str | Path,
    k: int = 5,
) -> None:
    """Write aggregated results as a Markdown comparison table."""
    if not summaries:
        raise ValueError("At least one summary is required.")

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Research Copilot Evaluation",
        "",
        (
            f"Recall@{k} measures the fraction of expected sources "
            f"retrieved in the first {k} results."
        ),
        "",
        "Report quality is scored from 1 to 5. A dash means that no "
        "quality rating was recorded.",
        "",
        (
            "| Configuration | Questions | Mean Recall@k | "
            "Mean Report Quality | LLM Calls | Tokens | "
            "Mean Latency (s) |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|",
    ]

    for summary in summaries:
        quality = (
            f"{summary.mean_report_quality_score:.2f}/5"
            if summary.mean_report_quality_score is not None
            else "—"
        )

        lines.append(
            f"| {summary.configuration} "
            f"| {summary.question_count} "
            f"| {summary.mean_recall_at_k:.3f} "
            f"| {quality} "
            f"| {summary.total_llm_calls} "
            f"| {summary.total_tokens} "
            f"| {summary.mean_latency_seconds:.3f} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation notes",
            "",
            "- Compare all configurations on the same question set.",
            "- Lower token counts and latency indicate lower measured cost.",
            "- Quality ratings should use the same rubric across configurations.",
            "- Do not draw conclusions from missing or incomplete measurements.",
            "",
        ]
    )

    target.write_text("\n".join(lines), encoding="utf-8")


def _save_bar_chart(
    summaries: Sequence[EvaluationSummary],
    metric: str,
    title: str,
    y_label: str,
    output_path: Path,
) -> Path | None:
    """Save one chart, skipping metrics that have no available values."""
    points = [
        (summary.configuration, getattr(summary, metric))
        for summary in summaries
        if getattr(summary, metric) is not None
    ]

    if not points:
        return None

    # Use a non-interactive backend so this works in CI and on headless hosts.
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels, values = zip(*points)

    figure, axis = plt.subplots(figsize=(8, 4.5))
    axis.bar(labels, values)
    axis.set_title(title)
    axis.set_xlabel("Experiment configuration")
    axis.set_ylabel(y_label)
    axis.grid(axis="y", alpha=0.3)
    axis.set_axisbelow(True)

    figure.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=160)
    plt.close(figure)

    return output_path


def generate_evaluation_report(
    input_csv: str | Path,
    output_dir: str | Path,
    k: int = 5,
) -> dict[str, Path | None]:
    """Generate summary CSV, Markdown table, and metric charts."""
    records = load_results_csv(input_csv)
    summaries = summarize_results(records, k=k)

    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    summary_csv = target_dir / "summary.csv"
    summary_markdown = target_dir / "summary.md"

    write_summary_csv(summaries, summary_csv)
    write_summary_markdown(summaries, summary_markdown, k=k)

    charts = {
        "recall_chart": _save_bar_chart(
            summaries,
            "mean_recall_at_k",
            f"Mean Recall@{k}",
            f"Recall@{k}",
            target_dir / "recall_at_k.png",
        ),
        "quality_chart": _save_bar_chart(
            summaries,
            "mean_report_quality_score",
            "Mean Report Quality",
            "Score (1-5)",
            target_dir / "report_quality.png",
        ),
        "token_chart": _save_bar_chart(
            summaries,
            "total_tokens",
            "Total Token Usage",
            "Input + output tokens",
            target_dir / "total_tokens.png",
        ),
        "latency_chart": _save_bar_chart(
            summaries,
            "mean_latency_seconds",
            "Mean Response Latency",
            "Seconds",
            target_dir / "mean_latency.png",
        ),
    }

    return {
        "summary_csv": summary_csv,
        "summary_markdown": summary_markdown,
        **charts,
    }


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Generate Research Copilot evaluation reports from CSV."
    )
    parser.add_argument(
        "input_csv",
        help="CSV file containing per-question evaluation measurements.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/evaluation",
        help="Directory for summary files and charts.",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=5,
        help="Cut-off used for Recall@k (default: 5).",
    )

    args = parser.parse_args(argv)
    if args.k < 1:
        parser.error("--k must be at least 1.")

    outputs = generate_evaluation_report(
        args.input_csv,
        args.output_dir,
        k=args.k,
    )

    for name, path in outputs.items():
        if path is not None:
            print(f"{name}: {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
