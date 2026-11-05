
"""Run the E0-E4 evaluation benchmark and persist results after each run."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from agents.cache import cache_enabled
from agents.pipeline import answer_with_stats
from agents.retrieval_search import search as default_search
from evals.experiment_configs import get_run_config
from evals.metrics import (
    EXPERIMENT_CONFIGS,
    EvaluationRecord,
    write_results_csv,
)
from evals.questions import EVALUATION_QUESTIONS, validate_question_set
from evals.report import generate_evaluation_report, load_results_csv
from evals.single_call_baseline import answer_baseline_with_stats


DEFAULT_OUTPUT_DIR = Path("outputs/evaluation")
RECALL_K = 5


def _parse_names(value: str, known: tuple[str, ...], label: str) -> list[str]:
    names = [item.strip() for item in value.split(",") if item.strip()]
    unknown = sorted(set(names) - set(known))

    if not names:
        raise ValueError(f"No {label} selected.")

    if unknown:
        raise ValueError(
            f"Unknown {label}: {', '.join(unknown)}. "
            f"Available: {', '.join(known)}."
        )

    if len(names) != len(set(names)):
        raise ValueError(f"Duplicate {label} selected.")

    return names


def _is_rate_limit_error(error: Exception) -> bool:
    """Return True when the API error indicates rate limiting or quota exhaustion."""

    error_type = type(error).__name__.casefold()

    if "resourceexhausted" in error_type:
        return True

    status_code = getattr(error, "status_code", None)
    if status_code is None:
        status_code = getattr(error, "code", None)

    if status_code is not None and str(status_code) == "429":
        return True

    message = str(error).casefold()

    indicators = (
        "429 resource_exhausted",
        "resource_exhausted",
        "quota exceeded",
        "generate_content_free_tier_requests",
        "too many requests",
    )

    return any(indicator in message for indicator in indicators)

def _run_one(configuration: str, question: str, time_budget: float):
    """Run one question with the selected experiment configuration."""

    if configuration == "E0":
        return answer_baseline_with_stats(
            question,
            search_fn=default_search,
            k=8,
        )

    cfg = get_run_config(configuration)
    cfg.time_budget_s = time_budget

    return answer_with_stats(question, cfg)


def run_benchmark(
    configurations: list[str],
    question_ids: list[str],
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    time_budget: float = 90.0,
    delay_seconds: float = 2.0,
) -> int:
    """Run selected experiments, resume existing results and save each success."""


    if cache_enabled():
        raise RuntimeError(
            "LLM cache is enabled. Run with LLM_CACHE=off "
            "to measure real token usage and latency."
        )

    validate_question_set()

    if not configurations:
        raise ValueError("At least one configuration is required.")

    if len(configurations) != len(set(configurations)):
        raise ValueError("Configurations must be unique.")

    unknown_configs = set(configurations) - set(EXPERIMENT_CONFIGS)
    if unknown_configs:
        raise ValueError(
            f"Unknown configurations: {', '.join(sorted(unknown_configs))}"
        )

    if not question_ids:
        raise ValueError("At least one question ID is required.")

    if len(question_ids) != len(set(question_ids)):
        raise ValueError("Question IDs must be unique.")

    known_question_ids = {
        question.id for question in EVALUATION_QUESTIONS
    }
    unknown_questions = set(question_ids) - known_question_ids

    if unknown_questions:
        raise ValueError(
            f"Unknown question IDs: {', '.join(sorted(unknown_questions))}"
        )

    if time_budget <= 0:
        raise ValueError("time_budget must be positive.")

    if delay_seconds < 0:
        raise ValueError("delay_seconds cannot be negative.")

    output_dir.mkdir(parents=True, exist_ok=True)

    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    results_path = output_dir / "results.csv"
    failures_path = output_dir / "failures.jsonl"

    questions_by_id = {
        item.id: item for item in EVALUATION_QUESTIONS
    }

    selected_questions = [
        questions_by_id[item] for item in question_ids
    ]

    # Resume from a previous run instead of repeating successful API calls.
    records: list[EvaluationRecord] = (
        load_results_csv(results_path) if results_path.exists() else []
    )


    completed = set()
    seen = set()
    valid_records = []
    stale_records = []

    for record in records:
        key = (record.configuration, record.question_id)

        if record.configuration not in EXPERIMENT_CONFIGS:
            raise ValueError(
                f"Unknown configuration in results CSV: {record.configuration}"
            )

        if record.question_id not in questions_by_id:
            raise ValueError(
                f"Unknown question ID in results CSV: {record.question_id}"
            )

        if key in seen:
            raise ValueError(f"Duplicate benchmark result: {key}")

        seen.add(key)

        report_path = reports_dir / (
            f"{record.configuration}_{record.question_id}.md"
        )

        if not report_path.is_file() or report_path.stat().st_size == 0:
            stale_records.append(record)
            print(
                f"[REPAIR] {key} has no saved report and will be rerun.",
                flush=True,
            )
            continue

        valid_records.append(record)
        completed.add(key)

    if stale_records:
        records = valid_records

        if records:
            write_results_csv(records, results_path, k=RECALL_K)
        else:
            results_path.unlink(missing_ok=True)


    total_jobs = len(configurations) * len(selected_questions)

    print(f"Configurations: {', '.join(configurations)}")
    print(f"Questions: {len(selected_questions)}")
    print(f"Existing completed runs: {len(completed)}")
    print(f"Results: {results_path}")
    print()

    attempted = 0
    errors = 0

    for configuration in configurations:
        for question in selected_questions:
            key = (configuration, question.id)

            if key in completed:
                print(f"[SKIP] {configuration} / {question.id} - already completed")
                continue

            attempted += 1
            print(
                f"[RUN {attempted}] {configuration} / {question.id}: "
                f"{question.question}",
                flush=True,
            )

            try:
                report, stats = _run_one(
                    configuration,
                    question.question,
                    time_budget,
                )

                report_path = reports_dir / (
                    f"{configuration}_{question.id}.md"
                )

                # Save the report before marking the run as completed in the CSV.
                report_path.write_text(
                    report.markdown,
                    encoding="utf-8",
                )

                record = EvaluationRecord(
                    configuration=configuration,
                    question_id=question.id,
                    retrieved_source_ids=tuple(stats.retrieved_source_ids),
                    expected_source_ids=question.expected_source_ids,
                    report_quality_score=None,
                    llm_calls=stats.llm_calls,
                    input_tokens=stats.input_tokens,
                    output_tokens=stats.output_tokens,
                    latency_seconds=stats.latency_seconds,
                )

                updated_records = [*records, record]

                # Persist only after the corresponding report has been saved.
                write_results_csv(updated_records, results_path, k=RECALL_K)

                records = updated_records
                completed.add(key)


                print(
                    f"[OK] {configuration} / {question.id} | "
                    f"sources={len(stats.retrieved_source_ids)} | "
                    f"calls={stats.llm_calls} | "
                    f"tokens={stats.input_tokens + stats.output_tokens} | "
                    f"latency={stats.latency_seconds:.2f}s",
                    flush=True,
                )

            except KeyboardInterrupt:
                print("\nBenchmark interrupted. Completed results were saved.")
                return 130


            except Exception as error:
                errors += 1
                failure = {
                    "configuration": configuration,
                    "question_id": question.id,
                    "error_type": type(error).__name__,
                    "error": str(error),
                }

                failures_path.parent.mkdir(parents=True, exist_ok=True)

                with failures_path.open("a", encoding="utf-8") as file:
                    file.write(json.dumps(failure, ensure_ascii=False) + "\n")
                    file.flush()

                print(
                    f"[ERROR] {configuration} / {question.id}: "
                    f"{type(error).__name__}: {error}",
                    flush=True,
                )

                if _is_rate_limit_error(error):
                    print(
                        "\n[STOP] Gemini API rate limit or quota exhaustion detected. "
                        "Benchmark stopped to avoid additional failed requests. "
                        "Completed results were preserved. "
                        "Run the benchmark again after the quota resets.",
                        flush=True,
                    )
                    return 1


            if delay_seconds > 0:
                time.sleep(delay_seconds)

    print("\n--- BENCHMARK STATUS ---")
    print(f"Successful records: {len(records)}")
    print(f"Errors in this run: {errors}")

    full_matrix = {
        (configuration, question.id)
        for configuration in EXPERIMENT_CONFIGS
        for question in EVALUATION_QUESTIONS
    }

    completed_full_matrix = full_matrix.issubset(completed)

    if completed_full_matrix:
        print("\nAll 25 experiment runs are complete.")
        outputs = generate_evaluation_report(
            results_path,
            output_dir,
            k=RECALL_K,
        )

        print("\n--- GENERATED REPORTS ---")
        for name, path in outputs.items():
            if path is not None:
                print(f"{name}: {path}")

        print(
            "\nReport quality scores are not yet assigned. "
            "Review the saved reports before drawing quality conclusions."
        )
    else:
        missing = len(full_matrix - completed)
        print(f"\nBenchmark is not complete. Missing runs: {missing}")
        print("Run the command again to resume without repeating successful runs.")

    return 0 if errors == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the Research Copilot E0-E4 evaluation benchmark."
    )

    parser.add_argument(
        "--configs",
        default="E0,E1,E2,E3,E4",
        help="Comma-separated experiment configurations.",
    )
    parser.add_argument(
        "--question-ids",
        default=",".join(q.id for q in EVALUATION_QUESTIONS),
        help="Comma-separated benchmark question IDs.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
    )
    parser.add_argument(
        "--time-budget",
        type=float,
        default=90.0,
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=2.0,
    )

    args = parser.parse_args()

    if args.time_budget <= 0:
        parser.error("--time-budget must be positive.")

    if args.delay_seconds < 0:
        parser.error("--delay-seconds cannot be negative.")

    try:
        configurations = _parse_names(
            args.configs,
            EXPERIMENT_CONFIGS,
            "configurations",
        )
        question_ids = _parse_names(
            args.question_ids,
            tuple(q.id for q in EVALUATION_QUESTIONS),
            "question IDs",
        )
    except ValueError as error:
        parser.error(str(error))

    return run_benchmark(
        configurations=configurations,
        question_ids=question_ids,
        output_dir=Path(args.output_dir),
        time_budget=args.time_budget,
        delay_seconds=args.delay_seconds,
    )


if __name__ == "__main__":
    raise SystemExit(main())
