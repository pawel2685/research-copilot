
"""Score saved benchmark reports with an LLM judge."""

from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Callable

from evals.metrics import EXPERIMENT_CONFIGS
from evals.questions import EVALUATION_QUESTIONS
from evals.quality_judge import QualityJudgement, judge_report
from evals.report import generate_evaluation_report


DEFAULT_OUTPUT_DIR = Path("outputs/evaluation")
DEFAULT_RESULTS = DEFAULT_OUTPUT_DIR / "results.csv"
DEFAULT_REPORTS = DEFAULT_OUTPUT_DIR / "reports"
JUDGEMENTS_FILE = DEFAULT_OUTPUT_DIR / "quality_judgements.jsonl"
FAILURES_FILE = DEFAULT_OUTPUT_DIR / "quality_failures.jsonl"
MANUAL_REVIEW_FILE = DEFAULT_OUTPUT_DIR / "manual_review.csv"


def _read_results(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        raise FileNotFoundError(f"Results CSV not found: {path}")

    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise ValueError("Results CSV has no header.")

        required = {
            "configuration",
            "question_id",
            "report_quality_score",
            "retrieved_source_ids",
        }
        missing = required - set(reader.fieldnames)

        if missing:
            raise ValueError(
                f"Results CSV is missing columns: {', '.join(sorted(missing))}"
            )

        return list(reader), list(reader.fieldnames)


def _write_results(
    path: Path,
    rows: list[dict[str, str]],
    fieldnames: list[str],
) -> None:
    """Atomically update the results CSV without changing other measurements."""

    path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path: str | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            delete=False,
        ) as file:
            temporary_path = file.name
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        os.replace(temporary_path, path)

    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)


def _load_judgements(path: Path) -> dict[str, dict]:
    """Load saved judgements to support safe resuming."""

    saved: dict[str, dict] = {}

    if not path.exists():
        return saved

    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            try:
                item = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON in {path}, line {line_number}."
                ) from error

            key = item.get("key")
            if not isinstance(key, str):
                raise ValueError(
                    f"Missing judgement key in {path}, line {line_number}."
                )

            saved[key] = item

    return saved


def _append_jsonl(path: Path, item: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(item, ensure_ascii=False) + "\n")
        file.flush()
        os.fsync(file.fileno())


def _write_manual_review_template(path: Path) -> None:
    """Create a blank manual review sheet without overwriting prior work."""

    if path.exists():
        return

    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = (
        "configuration",
        "question_id",
        "manual_quality_score",
        "reviewer_notes",
    )

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for configuration in EXPERIMENT_CONFIGS:
            for question in EVALUATION_QUESTIONS:
                writer.writerow(
                    {
                        "configuration": configuration,
                        "question_id": question.id,
                        "manual_quality_score": "",
                        "reviewer_notes": "",
                    }
                )


def _parse_filter(
    value: str | None,
    known: tuple[str, ...],
    label: str,
) -> set[str] | None:
    if value is None:
        return None

    selected = {item.strip() for item in value.split(",") if item.strip()}

    if not selected:
        raise ValueError(f"No {label} selected.")

    unknown = selected - set(known)
    if unknown:
        raise ValueError(
            f"Unknown {label}: {', '.join(sorted(unknown))}."
        )

    return selected


def score_results(
    results_path: Path = DEFAULT_RESULTS,
    reports_dir: Path = DEFAULT_REPORTS,
    judgements_path: Path = JUDGEMENTS_FILE,
    failures_path: Path = FAILURES_FILE,
    manual_review_path: Path = MANUAL_REVIEW_FILE,
    *,
    limit: int = 5,
    delay_seconds: float = 2.0,
    configurations: set[str] | None = None,
    question_ids: set[str] | None = None,
    judge_fn: Callable = judge_report,
) -> dict[str, int]:
    """Score missing reports, save progress and resume previous judgements."""

    if limit < 1:
        raise ValueError("limit must be at least 1.")

    if delay_seconds < 0:
        raise ValueError("delay_seconds cannot be negative.")

    rows, fieldnames = _read_results(results_path)
    saved_judgements = _load_judgements(judgements_path)

    questions = {question.id: question for question in EVALUATION_QUESTIONS}
    _write_manual_review_template(manual_review_path)

    expected_keys = {
    f"{configuration}::{question.id}"
    for configuration in EXPERIMENT_CONFIGS
    for question in EVALUATION_QUESTIONS
    }

    seen: set[str] = set()

    for row in rows:
        key = f"{row['configuration']}::{row['question_id']}"

        if key not in expected_keys:
            raise ValueError(f"Unexpected benchmark result: {key}")

        if key in seen:
            raise ValueError(f"Duplicate benchmark result: {key}")

        seen.add(key)

    counts = {
        "already_scored": 0,
        "restored_from_log": 0,
        "newly_scored": 0,
        "failed": 0,
    }

    requests_used = 0

    for index, row in enumerate(rows):
        configuration = row["configuration"]
        question_id = row["question_id"]
        key = f"{configuration}::{question_id}"

        if configurations is not None and configuration not in configurations:
            continue

        if question_ids is not None and question_id not in question_ids:
            continue

        if row["report_quality_score"].strip():
            counts["already_scored"] += 1
            continue

        # Restore a saved judgement if the process stopped before updating CSV.
        if key in saved_judgements:
            item = saved_judgements[key]
            judgement = QualityJudgement.model_validate(item["judgement"])
            row["report_quality_score"] = str(judgement.overall_score)
            counts["restored_from_log"] += 1
            _write_results(results_path, rows, fieldnames)
            continue

        if requests_used >= limit:
            continue

        if question_id not in questions:
            raise ValueError(f"Unknown question ID in results: {question_id}")

        report_path = reports_dir / f"{configuration}_{question_id}.md"

        if not report_path.exists():
            failure = {
                "key": key,
                "error_type": "FileNotFoundError",
                "error": f"Report not found: {report_path}",
            }
            _append_jsonl(failures_path, failure)
            counts["failed"] += 1
            continue

        report_markdown = report_path.read_text(encoding="utf-8")

        try:
            requests_used += 1
            judgement, stats = judge_fn(
                questions[question_id],
                report_markdown,
                retrieved_source_ids=tuple(
                    json.loads(row["retrieved_source_ids"])
                ) if row.get("retrieved_source_ids") else (),
            )

            item = {
                "key": key,
                "configuration": configuration,
                "question_id": question_id,
                "judgement": judgement.model_dump(),
                "overall_score": judgement.overall_score,
                "judge_usage": {
                    "llm_calls": stats.llm_calls,
                    "input_tokens": stats.input_tokens,
                    "output_tokens": stats.output_tokens,
                    "total_tokens": stats.input_tokens + stats.output_tokens,
                    "latency_seconds": stats.latency_seconds,
                },
            }

            # Save the full judgement before updating results.csv.
            # This makes an interrupted run recoverable without another API call.
            _append_jsonl(judgements_path, item)
            saved_judgements[key] = item

            row["report_quality_score"] = str(judgement.overall_score)
            _write_results(results_path, rows, fieldnames)

            counts["newly_scored"] += 1

            print(
                f"[SCORED] {key} | "
                f"quality={judgement.overall_score:.2f}/5 | "
                f"judge calls={stats.llm_calls} | "
                f"judge tokens={stats.input_tokens + stats.output_tokens}",
                flush=True,
            )

        except Exception as error:
            failure = {
                "key": key,
                "error_type": type(error).__name__,
                "error": str(error),
            }
            _append_jsonl(failures_path, failure)
            counts["failed"] += 1

            print(
                f"[ERROR] {key}: {type(error).__name__}: {error}",
                flush=True,
            )

        if delay_seconds > 0:
            time.sleep(delay_seconds)

    print("\n--- QUALITY JUDGE STATUS ---")
    for name, count in counts.items():
        print(f"{name}: {count}")

    scored_count = sum(
        1 for row in rows if row["report_quality_score"].strip()
    )
    print(f"Rows with quality scores: {scored_count}/{len(rows)}")
    print(f"Judge details: {judgements_path}")
    print(f"Manual review template: {manual_review_path}")

    expected_count = len(expected_keys)

    if seen == expected_keys and scored_count == expected_count:
        print("\nAll benchmark reports have quality scores.")
        outputs = generate_evaluation_report(
            results_path,
            results_path.parent,
            k=5,
        )
        for name, path in outputs.items():
            if path is not None:
                print(f"{name}: {path}")

    return counts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Score saved Research Copilot benchmark reports."
    )
    parser.add_argument(
        "--results",
        default=str(DEFAULT_RESULTS),
    )
    parser.add_argument(
        "--reports-dir",
        default=str(DEFAULT_REPORTS),
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum new LLM judge requests in this run.",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=2.0,
    )
    parser.add_argument(
        "--configs",
        default=None,
        help="Optional comma-separated configurations.",
    )
    parser.add_argument(
        "--question-ids",
        default=None,
        help="Optional comma-separated question IDs.",
    )

    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be at least 1.")

    if args.delay_seconds < 0:
        parser.error("--delay-seconds cannot be negative.")

    try:
        configurations = _parse_filter(
            args.configs,
            EXPERIMENT_CONFIGS,
            "configurations",
        )
        question_ids = _parse_filter(
            args.question_ids,
            tuple(question.id for question in EVALUATION_QUESTIONS),
            "question IDs",
        )
    except ValueError as error:
        parser.error(str(error))

    output_dir = Path(args.output_dir)

    score_results(
        results_path=Path(args.results),
        reports_dir=Path(args.reports_dir),
        judgements_path=output_dir / "quality_judgements.jsonl",
        failures_path=output_dir / "quality_failures.jsonl",
        manual_review_path=output_dir / "manual_review.csv",
        limit=args.limit,
        delay_seconds=args.delay_seconds,
        configurations=configurations,
        question_ids=question_ids,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
