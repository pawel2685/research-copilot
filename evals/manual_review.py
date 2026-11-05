
"""Aggregate manual quality reviews of benchmark reports."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from evals.metrics import EXPERIMENT_CONFIGS
from evals.questions import EVALUATION_QUESTIONS


DEFAULT_INPUT = Path("outputs/evaluation/manual_review.csv")
DEFAULT_OUTPUT = Path("outputs/evaluation/manual_review")


def load_manual_reviews(path: Path) -> list[dict]:
    """Load and validate the manual review sheet."""

    if not path.exists():
        raise FileNotFoundError(f"Manual review file not found: {path}")

    required_columns = {
        "configuration",
        "question_id",
        "manual_quality_score",
        "reviewer_notes",
    }

    valid_questions = {
        question.id for question in EVALUATION_QUESTIONS
    }

    reviews = []
    seen = set()

    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise ValueError("Manual review CSV has no header.")

        missing = required_columns - set(reader.fieldnames)
        if missing:
            raise ValueError(
                "Manual review CSV is missing columns: "
                + ", ".join(sorted(missing))
            )

        for line_number, row in enumerate(reader, start=2):
            configuration = row["configuration"].strip()
            question_id = row["question_id"].strip()
            raw_score = row["manual_quality_score"].strip()
            reviewer_notes = row["reviewer_notes"].strip()

            if configuration not in EXPERIMENT_CONFIGS:
                raise ValueError(
                    f"Invalid configuration on line {line_number}: "
                    f"{configuration}"
                )

            if question_id not in valid_questions:
                raise ValueError(
                    f"Invalid question ID on line {line_number}: "
                    f"{question_id}"
                )

            key = (configuration, question_id)

            if key in seen:
                raise ValueError(
                    f"Duplicate manual review on line {line_number}: {key}"
                )

            seen.add(key)

            if not raw_score:
                continue

            try:
                score = float(raw_score)
            except ValueError as error:
                raise ValueError(
                    f"Manual score on line {line_number} must be numeric."
                ) from error

            if not 1 <= score <= 5:
                raise ValueError(
                    f"Manual score on line {line_number} must be between 1 and 5."
                )

            reviews.append(
                {
                    "configuration": configuration,
                    "question_id": question_id,
                    "manual_quality_score": score,
                    "reviewer_notes": reviewer_notes,
                }
            )


    if not reviews:
        raise ValueError(
            "No manual scores found. Fill in manual_quality_score "
            "for at least one reviewed report."
        )

    reviewed_question_ids = {
        review["question_id"] for review in reviews
    }

    reviewed_keys = {
        (review["configuration"], review["question_id"])
        for review in reviews
    }

    expected_keys = {
        (configuration, question_id)
        for configuration in EXPERIMENT_CONFIGS
        for question_id in reviewed_question_ids
    }

    missing_keys = expected_keys - reviewed_keys

    if missing_keys:
        missing_text = ", ".join(
            f"{configuration}/{question_id}"
            for configuration, question_id in sorted(missing_keys)
        )
        raise ValueError(
            "Manual review sample must contain the same question IDs "
            "for every configuration. Missing reviews: "
            f"{missing_text}"
        )

    return reviews



def summarize_manual_reviews(reviews: list[dict]) -> list[dict]:
    """Calculate manual quality statistics for each configuration."""

    grouped: dict[str, list[dict]] = defaultdict(list)

    for review in reviews:
        grouped[review["configuration"]].append(review)

    summaries = []

    for configuration in EXPERIMENT_CONFIGS:
        group = grouped.get(configuration, [])

        if not group:
            continue

        scores = [
            review["manual_quality_score"] for review in group
        ]

        summaries.append(
            {
                "configuration": configuration,
                "reviewed_count": len(scores),
                "mean_manual_quality_score": round(
                    sum(scores) / len(scores), 2
                ),
                "min_manual_quality_score": min(scores),
                "max_manual_quality_score": max(scores),
            }
        )

    return summaries


def write_manual_review_outputs(
    reviews: list[dict],
    output_dir: Path,
) -> dict[str, Path]:
    """Write manual review summary CSV, Markdown and a chart."""

    output_dir.mkdir(parents=True, exist_ok=True)

    summaries = summarize_manual_reviews(reviews)

    csv_path = output_dir / "manual_summary.csv"
    markdown_path = output_dir / "manual_summary.md"
    chart_path = output_dir / "manual_quality.png"

    with csv_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        fieldnames = [
            "configuration",
            "reviewed_count",
            "mean_manual_quality_score",
            "min_manual_quality_score",
            "max_manual_quality_score",
        ]

        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summaries)

    lines = [
        "# Manual quality review",
        "",
        "Manual assessment of a selected sample of generated reports.",
        "",
        "| Configuration | Reviewed reports | Mean score | Min | Max |",
        "|---|---:|---:|---:|---:|",
    ]

    for summary in summaries:
        lines.append(
            f"| {summary['configuration']} "
            f"| {summary['reviewed_count']} "
            f"| {summary['mean_manual_quality_score']:.2f} "
            f"| {summary['min_manual_quality_score']:.2f} "
            f"| {summary['max_manual_quality_score']:.2f} |"
        )

    lines.extend(
        [
            "",
            "Scores use a 1-5 scale. Only reports with a completed "
            "manual score are included.",
            "",
            "## Reviewer notes",
            "",
        ]
    )

    for review in reviews:
        lines.append(
            f"### {review['configuration']} / {review['question_id']}"
        )
        lines.append(
            f"Score: {review['manual_quality_score']:.2f}/5"
        )
        lines.append(
            review["reviewer_notes"] or "No reviewer notes."
        )
        lines.append("")

    markdown_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    # Import matplotlib only when a chart is actually generated.
    import matplotlib.pyplot as plt

    labels = [
        summary["configuration"] for summary in summaries
    ]
    values = [
        summary["mean_manual_quality_score"]
        for summary in summaries
    ]
    counts = [
        summary["reviewed_count"] for summary in summaries
    ]

    figure, axis = plt.subplots(figsize=(8, 5))
    bars = axis.bar(labels, values)

    axis.set_title("Manual report quality by configuration")
    axis.set_xlabel("Configuration")
    axis.set_ylabel("Mean manual quality score (1-5)")
    axis.set_ylim(0, 5)
    axis.grid(axis="y", alpha=0.25)

    for bar, value, count in zip(bars, values, counts):
        axis.annotate(
            f"{value:.2f}\nn={count}",
            (bar.get_x() + bar.get_width() / 2, value),
            xytext=(0, 5),
            textcoords="offset points",
            ha="center",
        )

    figure.tight_layout()
    figure.savefig(chart_path, dpi=160)
    plt.close(figure)

    return {
        "summary_csv": csv_path,
        "summary_markdown": markdown_path,
        "chart": chart_path,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize manual quality reviews."
    )
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT),
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT),
    )

    args = parser.parse_args()

    reviews = load_manual_reviews(Path(args.input))
    outputs = write_manual_review_outputs(
        reviews,
        Path(args.output_dir),
    )

    print(f"Reviewed reports: {len(reviews)}")

    for name, path in outputs.items():
        print(f"{name}: {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
