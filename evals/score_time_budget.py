
"""Score time-budget experiment reports with the LLM quality judge."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from pathlib import Path
from typing import Callable

import matplotlib.pyplot as plt

from agents.cache import cache_enabled
from evals.quality_judge import judge_report
from evals.questions import EVALUATION_QUESTIONS


DEFAULT_OUTPUT_DIR = Path("outputs/evaluation/time_budget")


def _read_jsonl(path: Path) -> list[dict]:
    """Read JSON Lines records. A missing file is treated as empty."""

    if not path.exists():
        return []

    records = []

    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON in {path}, line {line_number}."
                ) from error

    return records


def _append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")
        file.flush()


def _make_key(record: dict) -> tuple[int, str]:
    return (
        int(record["budget_seconds"]),
        str(record["question_id"]),
    )


def _index_unique_records(
    records: list[dict],
    label: str,
) -> dict[tuple[int, str], dict]:
    """Index JSONL records and reject duplicate budget/question pairs."""

    indexed = {}

    for record in records:
        key = _make_key(record)

        if key in indexed:
            raise ValueError(f"Duplicate {label}: {key}")

        indexed[key] = record

    return indexed


def _get_attr(value, name: str, default=None):
    """Read an attribute from a Pydantic model or a simple test object."""

    if isinstance(value, dict):
        return value.get(name, default)

    return getattr(value, name, default)


def _serialize_judgement(judgement) -> dict:
    """Extract the rubric fields from a QualityJudgement."""

    return {
        "relevance": int(_get_attr(judgement, "relevance")),
        "coverage": int(_get_attr(judgement, "coverage")),
        "factual_support": int(
            _get_attr(judgement, "factual_support")
        ),
        "citation_quality": int(
            _get_attr(judgement, "citation_quality")
        ),
        "overall_score": round(
            float(_get_attr(judgement, "overall_score")), 4
        ),
        "rationale": str(_get_attr(judgement, "rationale", "")),
        "warnings": list(_get_attr(judgement, "warnings", [])),
    }


def _serialize_usage(stats) -> dict:
    return {
        "llm_calls": int(_get_attr(stats, "llm_calls", 0)),
        "input_tokens": int(_get_attr(stats, "input_tokens", 0)),
        "output_tokens": int(_get_attr(stats, "output_tokens", 0)),
        "latency_seconds": round(
            float(_get_attr(stats, "latency_seconds", 0.0)), 4
        ),
    }


def _write_quality_outputs(
    experiment_records: list[dict],
    judgement_records: list[dict],
    output_dir: Path,
) -> dict[str, Path]:
    """Join quality scores with run metrics and create summaries."""

    judgement_by_key = {
        _make_key(record): record for record in judgement_records
    }

    results_by_budget: dict[int, list[dict]] = {}

    for record in experiment_records:
        budget = int(record["budget_seconds"])
        results_by_budget.setdefault(budget, []).append(record)

    summaries = []

    for budget in sorted(results_by_budget):
        runs = results_by_budget[budget]
        scored = [
            judgement_by_key[_make_key(run)]
            for run in runs
            if _make_key(run) in judgement_by_key
        ]

        scores = [
            float(record["judgement"]["overall_score"])
            for record in scored
        ]

        latencies = [
            float(run["latency_seconds"]) for run in runs
        ]
        token_counts = [
            int(run["total_tokens"]) for run in runs
        ]

        summaries.append(
            {
                "budget_seconds": budget,
                "completed_runs": len(runs),
                "scored_runs": len(scored),
                "mean_quality_score": (
                    round(statistics.mean(scores), 4)
                    if scores else ""
                ),
                "quality_stddev": (
                    round(statistics.stdev(scores), 4)
                    if len(scores) > 1 else 0.0
                ),
                "mean_latency_seconds": round(
                    statistics.mean(latencies), 2
                ),
                "mean_total_tokens": round(
                    statistics.mean(token_counts), 2
                ),
                "planner_skip_rate": round(
                    sum(
                        bool(run["planner_skipped_by_deadline"])
                        for run in runs
                    ) / len(runs),
                    4,
                ),
                "critic_skip_rate": round(
                    sum(
                        bool(run["critic_skipped_by_deadline"])
                        for run in runs
                    ) / len(runs),
                    4,
                ),
                "verified_rate": round(
                    sum(bool(run["verified"]) for run in runs) / len(runs),
                    4,
                ),
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / "time_budget_quality_summary.csv"
    markdown_path = output_dir / "time_budget_quality_summary.md"
    quality_chart_path = output_dir / "quality_vs_time_budget.png"
    skips_chart_path = output_dir / "skips_vs_time_budget.png"

    fieldnames = [
        "budget_seconds",
        "completed_runs",
        "scored_runs",
        "mean_quality_score",
        "quality_stddev",
        "mean_latency_seconds",
        "mean_total_tokens",
        "planner_skip_rate",
        "critic_skip_rate",
        "verified_rate",
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
        "# Time budget experiment – quality evaluation",
        "",
        "E4 configuration evaluated under different time budgets.",
        "Quality scores come from the independent LLM judge.",
        "",
        "| Budget (s) | Runs | Scored | Mean quality | Std. dev. | Mean latency (s) | Mean tokens | Planner skip rate | Critic skip rate | Verified rate |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for item in summaries:
        quality = (
            f"{item['mean_quality_score']:.2f}"
            if item["mean_quality_score"] != ""
            else "N/A"
        )

        lines.append(
            f"| {item['budget_seconds']} "
            f"| {item['completed_runs']} "
            f"| {item['scored_runs']} "
            f"| {quality} "
            f"| {item['quality_stddev']:.2f} "
            f"| {item['mean_latency_seconds']:.2f} "
            f"| {item['mean_total_tokens']:.0f} "
            f"| {item['planner_skip_rate']:.0%} "
            f"| {item['critic_skip_rate']:.0%} "
            f"| {item['verified_rate']:.0%} |"
        )

    lines.extend(
        [
            "",
            "Skip rates are calculated from all successfully completed "
            "runs for each budget.",
            "Quality means and standard deviations use only reports "
            "successfully scored by the LLM judge.",
            "",
        ]
    )

    markdown_path.write_text("\n".join(lines), encoding="utf-8")

    scored_summaries = [
        item for item in summaries
        if item["mean_quality_score"] != ""
    ]

    if scored_summaries:
        budgets = [
            item["budget_seconds"] for item in scored_summaries
        ]
        means = [
            item["mean_quality_score"] for item in scored_summaries
        ]
        deviations = [
            item["quality_stddev"] for item in scored_summaries
        ]

        plt.figure(figsize=(8, 5))
        plt.errorbar(
            budgets,
            means,
            yerr=deviations,
            marker="o",
            capsize=4,
        )
        plt.xlabel("Time budget (seconds)")
        plt.ylabel("Mean LLM judge quality score (1–5)")
        plt.title("Report quality vs. time budget")
        plt.xticks(budgets)
        plt.ylim(1, 5)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(quality_chart_path, dpi=150)
        plt.close()

    plt.figure(figsize=(8, 5))
    budgets = [item["budget_seconds"] for item in summaries]
    planner_rates = [
        item["planner_skip_rate"] * 100 for item in summaries
    ]
    critic_rates = [
        item["critic_skip_rate"] * 100 for item in summaries
    ]

    plt.plot(
        budgets,
        planner_rates,
        marker="o",
        label="Planner skipped",
    )
    plt.plot(
        budgets,
        critic_rates,
        marker="o",
        label="Critic skipped",
    )
    plt.xlabel("Time budget (seconds)")
    plt.ylabel("Skipped runs (%)")
    plt.title("Agent skip rate vs. time budget")
    plt.xticks(budgets)
    plt.ylim(0, 100)
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(skips_chart_path, dpi=150)
    plt.close()

    return {
        "summary_csv": csv_path,
        "summary_markdown": markdown_path,
        "quality_chart": quality_chart_path,
        "skips_chart": skips_chart_path,
    }


def score_time_budget_reports(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    limit: int | None = None,
    delay_seconds: float = 5.0,
    judge_fn: Callable = judge_report,
) -> dict[str, int]:
    """Judge saved reports, resuming from previously saved judgements."""

    if limit is not None and limit < 0:
        raise ValueError("limit cannot be negative.")

    if delay_seconds < 0:
        raise ValueError("delay_seconds cannot be negative.")

    results_path = output_dir / "time_budget_results.jsonl"
    judgements_path = output_dir / "quality_judgements.jsonl"
    failures_path = output_dir / "quality_failures.jsonl"

    experiment_records = _read_jsonl(results_path)

    if not experiment_records:
        raise ValueError(
            f"No experiment results found in {results_path}."
        )

    questions_by_id = {
        question.id: question for question in EVALUATION_QUESTIONS
    }


    existing_judgements = _read_jsonl(judgements_path)

    completed = _index_unique_records(
        existing_judgements,
        "time-budget judgement",
    )

    experiment_by_key = _index_unique_records(
        experiment_records,
        "time-budget experiment result",
    )

    unexpected_judgements = set(completed) - set(experiment_by_key)

    if unexpected_judgements:
        raise ValueError(
            "Judgements without matching experiment results: "
            + ", ".join(
                str(key) for key in sorted(unexpected_judgements)
            )
        )


    new_requests = 0
    errors = 0

    for run in experiment_records:
        key = _make_key(run)

        if key in completed:
            continue

        if limit is not None and new_requests >= limit:
            break

        question_id = str(run["question_id"])

        if question_id not in questions_by_id:
            errors += 1
            _append_jsonl(
                failures_path,
                {
                    "budget_seconds": key[0],
                    "question_id": question_id,
                    "error": "Question ID not found in EVALUATION_QUESTIONS.",
                },
            )
            continue

        report_path = Path(run["report_file"])

        if not report_path.exists():
            errors += 1
            _append_jsonl(
                failures_path,
                {
                    "budget_seconds": key[0],
                    "question_id": question_id,
                    "error": f"Report file not found: {report_path}",
                },
            )
            continue

        report_markdown = report_path.read_text(encoding="utf-8")
        source_ids = tuple(run.get("retrieved_source_ids", []))

        print(
            f"[JUDGE] budget={key[0]}s / question={question_id}",
            flush=True,
        )

        # Count each attempted judge call, including failed calls,
        # against the request limit.
        new_requests += 1

        try:
            judgement, judge_stats = judge_fn(
                questions_by_id[question_id],
                report_markdown,
                source_ids,
            )

            record = {
                "budget_seconds": key[0],
                "question_id": question_id,
                "judgement": _serialize_judgement(judgement),
                "judge_usage": _serialize_usage(judge_stats),
            }

            _append_jsonl(judgements_path, record)
            completed[key] = record

            score = record["judgement"]["overall_score"]

            print(
                f"[OK] budget={key[0]}s / question={question_id} "
                f"/ quality={score:.2f}",
                flush=True,
            )

        except KeyboardInterrupt:
            raise

        except Exception as error:
            errors += 1

            _append_jsonl(
                failures_path,
                {
                    "budget_seconds": key[0],
                    "question_id": question_id,
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
            )

            print(
                f"[ERROR] budget={key[0]}s / question={question_id}: "
                f"{type(error).__name__}: {error}",
                flush=True,
            )

        if delay_seconds > 0:
            time.sleep(delay_seconds)

    paths = _write_quality_outputs(
        experiment_records,
        list(completed.values()),
        output_dir,
    )

    expected = set(experiment_by_key)
    missing = expected - set(completed)

    print("\n--- TIME BUDGET QUALITY SCORING ---")
    print(f"Experiment runs: {len(expected)}")
    print(f"Judged reports: {len(completed)}")
    print(f"New judge requests: {new_requests}")
    print(f"Errors in this run: {errors}")
    print(f"Reports still needing a judgement: {len(missing)}")

    for label, path in paths.items():
        print(f"{label}: {path}")

    return {
        "experiment_runs": len(expected),
        "judged": len(completed),
        "new_requests": new_requests,
        "errors": errors,
        "missing": len(missing),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Score saved time-budget experiment reports."
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of new LLM judge requests.",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=5.0,
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
    )

    args = parser.parse_args()

    if cache_enabled():
        parser.error(
            "LLM cache is enabled. Run with LLM_CACHE=off to ensure "
            "the judge uses real model calls."
        )

    try:
        result = score_time_budget_reports(
            output_dir=Path(args.output_dir),
            limit=args.limit,
            delay_seconds=args.delay_seconds,
        )
    except ValueError as error:
        parser.error(str(error))

    return 0 if result["errors"] == 0 and result["missing"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
