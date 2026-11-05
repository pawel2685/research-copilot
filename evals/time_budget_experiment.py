
"""Evaluate the E4 pipeline under different time budgets."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from pathlib import Path
from typing import Callable

from agents.pipeline import answer_with_stats
from agents.cache import cache_enabled
from contracts import Report
from agents.stats import RunStats
from evals.experiment_configs import get_run_config
from evals.questions import EVALUATION_QUESTIONS, validate_question_set


DEFAULT_OUTPUT_DIR = Path("outputs/evaluation/time_budget")
DEFAULT_BUDGETS = (30, 60, 120)


def _load_completed(path: Path) -> dict[tuple[int, str], dict]:
    """Load saved results so interrupted experiments can be resumed."""

    completed: dict[tuple[int, str], dict] = {}

    if not path.exists():
        return completed

    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON in {path}, line {line_number}."
                ) from error

            key = (
                int(record["budget_seconds"]),
                record["question_id"],
            )

            if key in completed:
                raise ValueError(
                    f"Duplicate time-budget result: {key}"
                )

            completed[key] = record

    return completed


def _append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")
        file.flush()

def _is_rate_limit_error(error: Exception) -> bool:
    """Detect Gemini API rate limits and quota exhaustion."""

    error_type = type(error).__name__.lower()
    message = str(error).lower()

    status_code = getattr(error, "status_code", None)
    code = getattr(error, "code", None)

    return (
        "resourceexhausted" in error_type
        or status_code == 429
        or code == 429
        or any(
            marker in message
            for marker in (
                "429 resource_exhausted",
                "resource_exhausted",
                "resource exhausted",
                "quota exceeded",
                "generate_content_free_tier_requests",
                "too many requests",
            )
        )
    )

def _write_summary(
    records: list[dict],
    output_dir: Path,
) -> dict[str, Path]:
    """Write aggregate runtime and agent-skip metrics by budget."""

    grouped: dict[int, list[dict]] = {}

    for record in records:
        budget = int(record["budget_seconds"])
        grouped.setdefault(budget, []).append(record)

    summaries = []

    for budget in sorted(grouped):
        group = grouped[budget]

        latencies = [
            float(item["latency_seconds"]) for item in group
        ]
        token_counts = [
            int(item["input_tokens"]) + int(item["output_tokens"])
            for item in group
        ]

        summaries.append(
            {
                "budget_seconds": budget,
                "completed_runs": len(group),
                "mean_latency_seconds": round(
                    statistics.mean(latencies), 2
                ),
                "mean_total_tokens": round(
                    statistics.mean(token_counts), 2
                ),
                "planner_skipped_count": sum(
                    bool(item["planner_skipped_by_deadline"])
                    for item in group
                ),
                "critic_skipped_count": sum(
                    bool(item["critic_skipped_by_deadline"])
                    for item in group
                ),
                "critic_approved_count": sum(
                    bool(item["verified"]) for item in group
                ),
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / "time_budget_summary.csv"
    markdown_path = output_dir / "time_budget_summary.md"

    fieldnames = [
        "budget_seconds",
        "completed_runs",
        "mean_latency_seconds",
        "mean_total_tokens",
        "planner_skipped_count",
        "critic_skipped_count",
        "critic_approved_count",
    ]

    with csv_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summaries)

    lines = [
        "# Time budget experiment",
        "",
        "E4 configuration with different time budgets.",
        "",
        "| Budget (s) | Runs | Mean latency (s) | Mean tokens | Planner skips | Critic skips | Critic approvals |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for item in summaries:
        lines.append(
            f"| {item['budget_seconds']} "
            f"| {item['completed_runs']} "
            f"| {item['mean_latency_seconds']:.2f} "
            f"| {item['mean_total_tokens']:.0f} "
            f"| {item['planner_skipped_count']} "
            f"| {item['critic_skipped_count']} "
            f"| {item['critic_approved_count']} |"
        )

    lines.extend(
        [
            "",
            "A Critic approval is counted only when the final report is verified.",
            "Quality scores from the independent LLM judge and manual review "
            "will be added in a separate evaluation step.",
        ]
    )

    markdown_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    return {
        "summary_csv": csv_path,
        "summary_markdown": markdown_path,
    }


def run_time_budget_experiment(
    *,
    budgets: tuple[int, ...] = DEFAULT_BUDGETS,
    question_ids: tuple[str, ...] | None = None,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    delay_seconds: float = 5.0,
    answer_fn: Callable = answer_with_stats,
) -> dict[str, int]:
    """Run and persist the E4 time-budget experiment."""

    validate_question_set()

    if not budgets:
        raise ValueError("At least one time budget is required.")

    if any(budget <= 0 for budget in budgets):
        raise ValueError("All time budgets must be positive.")

    if len(set(budgets)) != len(budgets):
        raise ValueError("Time budgets must be unique.")

    if delay_seconds < 0:
        raise ValueError("delay_seconds cannot be negative.")

    questions_by_id = {
        question.id: question for question in EVALUATION_QUESTIONS
    }

    selected_ids = (
        question_ids
        if question_ids is not None
        else tuple(questions_by_id)
    )

    if not selected_ids:
        raise ValueError("At least one question must be selected.")

    if len(set(selected_ids)) != len(selected_ids):
        raise ValueError("Question IDs must be unique.")

    unknown = set(selected_ids) - set(questions_by_id)

    if unknown:
        raise ValueError(
            f"Unknown question IDs: {', '.join(sorted(unknown))}"
        )

    selected_questions = [
        questions_by_id[question_id]
        for question_id in selected_ids
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    results_path = output_dir / "time_budget_results.jsonl"
    failures_path = output_dir / "time_budget_failures.jsonl"

    completed = _load_completed(results_path)

    total_jobs = len(budgets) * len(selected_questions)
    errors = 0
    new_runs = 0
    rate_limit_hit = False

    print("Configuration: E4")
    print(f"Budgets: {', '.join(str(b) for b in budgets)} seconds")
    print(f"Questions: {len(selected_questions)}")
    print(f"Total selected runs: {total_jobs}")
    print(f"Previously completed runs: {len(completed)}")
    print(f"Output: {output_dir}")
    print()

    try:
        for budget in budgets:
            for question in selected_questions:
                key = (budget, question.id)

                if key in completed:
                    print(
                        f"[SKIP] {budget}s / {question.id} - already completed"
                    )
                    continue

                print(
                    "[RUN] "
                    f"E4 / {budget}s / {question.id}: {question.question}",
                    flush=True,
                )

                cfg = get_run_config("E4")
                cfg.time_budget_s = float(budget)

                try:
                    report, stats = answer_fn(question.question, cfg)

                    if not isinstance(report, Report):
                        raise TypeError(
                            "answer_fn must return a Report as its first value."
                        )

                    if not isinstance(stats, RunStats):
                        raise TypeError(
                            "answer_fn must return RunStats as its second value."
                        )

                    report_filename = f"budget_{budget}s_{question.id}.md"
                    report_path = reports_dir / report_filename

                    report_path.write_text(
                        report.markdown,
                        encoding="utf-8",
                    )

                    record = {
                        "experiment": "time_budget",
                        "configuration": "E4",
                        "budget_seconds": budget,
                        "question_id": question.id,
                        "report_file": str(report_path),
                        "retrieved_source_ids": list(
                            stats.retrieved_source_ids
                        ),
                        "llm_calls": stats.llm_calls,
                        "input_tokens": stats.input_tokens,
                        "output_tokens": stats.output_tokens,
                        "total_tokens": (
                            stats.input_tokens + stats.output_tokens
                        ),
                        "latency_seconds": round(
                            stats.latency_seconds, 4
                        ),
                        "planner_skipped_by_deadline": (
                            stats.planner_skipped_by_deadline
                        ),
                        "critic_skipped_by_deadline": (
                            stats.critic_skipped_by_deadline
                        ),
                        "verified": report.verified,
                    }

                    _append_jsonl(results_path, record)
                    completed[key] = record
                    new_runs += 1

                    print(
                        f"[OK] E4 / {budget}s / {question.id} | "
                        f"calls={stats.llm_calls} | "
                        f"tokens={stats.input_tokens + stats.output_tokens} | "
                        f"latency={stats.latency_seconds:.2f}s | "
                        f"planner_skipped={stats.planner_skipped_by_deadline} | "
                        f"critic_skipped={stats.critic_skipped_by_deadline}",
                        flush=True,
                    )

                except KeyboardInterrupt:
                    raise

                except Exception as error:
                    errors += 1

                    failure = {
                        "budget_seconds": budget,
                        "question_id": question.id,
                        "error_type": type(error).__name__,
                        "error": str(error),
                    }

                    _append_jsonl(failures_path, failure)

                    print(
                        f"[ERROR] {budget}s / {question.id}: "
                        f"{type(error).__name__}: {error}",
                        flush=True,
                    )

                    if _is_rate_limit_error(error):
                        rate_limit_hit = True
                        print(
                            "\n[STOP] Gemini API rate limit or quota "
                            "exhaustion detected. Experiment stopped "
                            "to avoid additional failed requests. "
                            "Completed results were preserved.",
                            flush=True,
                        )
                        break

            if rate_limit_hit:
                break

    except KeyboardInterrupt:
        print("\nExperiment interrupted. Completed runs were saved.")

    all_records = list(completed.values())

    _write_summary(all_records, output_dir)

    expected = {
        (budget, question.id)
        for budget in budgets
        for question in selected_questions
    }
    missing = expected - set(completed)

    print("\n--- TIME BUDGET EXPERIMENT STATUS ---")
    print(f"Successful runs: {len(completed)}")
    print(f"New successful runs: {new_runs}")
    print(f"Errors in this run: {errors}")
    print(f"Missing selected runs: {len(missing)}")

    if not missing:
        print("Selected time-budget experiment is complete.")
    else:
        print("Run the same command again to resume missing runs.")

    return {
        "successful": len(completed),
        "new_successful": new_runs,
        "errors": errors,
        "missing": len(missing),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the E4 time-budget experiment."
    )

    parser.add_argument(
        "--budgets",
        default="30,60,120",
        help="Comma-separated time budgets in seconds.",
    )
    parser.add_argument(
        "--question-ids",
        default=None,
        help="Optional comma-separated benchmark question IDs.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=5.0,
    )

    args = parser.parse_args()

    try:
        budgets = tuple(
            int(value.strip())
            for value in args.budgets.split(",")
            if value.strip()
        )
        question_ids = (
            tuple(
                value.strip()
                for value in args.question_ids.split(",")
                if value.strip()
            )
            if args.question_ids
            else None
        )
    except ValueError:
        parser.error("Budgets must be comma-separated integers.")

    if cache_enabled():
        parser.error(
            "LLM cache is enabled. Run with LLM_CACHE=off to measure "
            "real token usage and latency."
        )

    try:
        result = run_time_budget_experiment(
            budgets=budgets,
            question_ids=question_ids,
            output_dir=Path(args.output_dir),
            delay_seconds=args.delay_seconds,
        )
    except ValueError as error:
        parser.error(str(error))

    return 0 if result["errors"] == 0 and result["missing"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
