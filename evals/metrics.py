"""Metrics and CSV export for reproducible research evaluation."""

import csv
import json
import math
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


EXPERIMENT_CONFIGS = ("E0", "E1", "E2", "E3", "E4")


def _normalize_source_id(source_id: str) -> str:
    """Normalize arXiv IDs to allow comparison across URL formats."""
    if not isinstance(source_id, str):
        raise TypeError("Every source ID must be a string.")

    normalized = source_id.strip().casefold()

    if normalized.startswith("https://arxiv.org/abs/"):
        normalized = normalized.removeprefix("https://arxiv.org/abs/")
    elif normalized.startswith("http://arxiv.org/abs/"):
        normalized = normalized.removeprefix("http://arxiv.org/abs/")

    if normalized.startswith("arxiv:"):
        normalized = normalized.removeprefix("arxiv:")

    normalized = re.sub(r"v\d+$", "", normalized)

    if not normalized:
        raise ValueError("Source IDs must not be empty.")

    return normalized


def recall_at_k(
    retrieved_source_ids: Sequence[str],
    expected_source_ids: Sequence[str],
    k: int = 5,
) -> float:
    """Calculate Recall@k for a single research question.

    Recall@k is the fraction of expected relevant sources retrieved
    within the first k results.
    """
    if isinstance(k, bool) or not isinstance(k, int):
        raise TypeError("k must be an integer.")
    if k < 1:
        raise ValueError("k must be at least 1.")
    if isinstance(retrieved_source_ids, (str, bytes)):
        raise TypeError("Retrieved source IDs must be a sequence.")
    if isinstance(expected_source_ids, (str, bytes)):
        raise TypeError("Expected source IDs must be a sequence.")

    expected = {
        _normalize_source_id(source_id)
        for source_id in expected_source_ids
    }
    if not expected:
        raise ValueError("At least one expected source is required.")

    retrieved = {
        _normalize_source_id(source_id)
        for source_id in retrieved_source_ids[:k]
    }

    return len(expected & retrieved) / len(expected)


@dataclass(frozen=True, slots=True)
class EvaluationRecord:
    """Measurements collected from one question in one configuration."""

    configuration: str
    question_id: str
    retrieved_source_ids: tuple[str, ...]
    expected_source_ids: tuple[str, ...]
    report_quality_score: float | None = None
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    latency_seconds: float = 0.0

    def __post_init__(self) -> None:
        if self.configuration not in EXPERIMENT_CONFIGS:
            raise ValueError(
                f"configuration must be one of {EXPERIMENT_CONFIGS}."
            )
        if not self.question_id.strip():
            raise ValueError("question_id must not be empty.")
        if not self.expected_source_ids:
            raise ValueError("At least one expected source is required.")

        if self.report_quality_score is not None:
            score = self.report_quality_score
            if isinstance(score, bool) or not isinstance(score, (int, float)):
                raise TypeError("Quality score must be numeric or None.")
            if not math.isfinite(score) or not 1 <= score <= 5:
                raise ValueError("Quality score must be between 1 and 5.")

        for name in ("llm_calls", "input_tokens", "output_tokens"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer.")
            if value < 0:
                raise ValueError(f"{name} must not be negative.")

        if (
            not math.isfinite(self.latency_seconds)
            or self.latency_seconds < 0
        ):
            raise ValueError(
                "latency_seconds must be finite and non-negative."
            )


@dataclass(frozen=True, slots=True)
class EvaluationSummary:
    """Aggregated metrics for one experiment configuration."""

    configuration: str
    question_count: int
    mean_recall_at_k: float
    mean_report_quality_score: float | None
    total_llm_calls: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    mean_latency_seconds: float
    total_latency_seconds: float


def summarize_results(
    records: Sequence[EvaluationRecord],
    k: int = 5,
) -> list[EvaluationSummary]:
    """Aggregate evaluation records by configuration."""
    if not records:
        raise ValueError("At least one evaluation record is required.")

    grouped: dict[str, list[EvaluationRecord]] = defaultdict(list)
    for record in records:
        grouped[record.configuration].append(record)

    summaries = []

    for configuration in EXPERIMENT_CONFIGS:
        group = grouped.get(configuration)
        if not group:
            continue

        recalls = [
            recall_at_k(
                record.retrieved_source_ids,
                record.expected_source_ids,
                k=k,
            )
            for record in group
        ]
        quality_scores = [
            record.report_quality_score
            for record in group
            if record.report_quality_score is not None
        ]

        total_input = sum(record.input_tokens for record in group)
        total_output = sum(record.output_tokens for record in group)
        total_latency = sum(record.latency_seconds for record in group)

        summaries.append(
            EvaluationSummary(
                configuration=configuration,
                question_count=len(group),
                mean_recall_at_k=sum(recalls) / len(recalls),
                mean_report_quality_score=(
                    sum(quality_scores) / len(quality_scores)
                    if quality_scores
                    else None
                ),
                total_llm_calls=sum(record.llm_calls for record in group),
                total_input_tokens=total_input,
                total_output_tokens=total_output,
                total_tokens=total_input + total_output,
                mean_latency_seconds=total_latency / len(group),
                total_latency_seconds=total_latency,
            )
        )

    return summaries


def write_results_csv(
    records: Sequence[EvaluationRecord],
    output_path: str | Path,
    k: int = 5,
) -> None:
    """Write per-question evaluation results to CSV."""
    if not records:
        raise ValueError("At least one evaluation record is required.")

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = (
        "configuration",
        "question_id",
        "recall_at_k",
        "k",
        "report_quality_score",
        "llm_calls",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "latency_seconds",
        "retrieved_source_ids",
        "expected_source_ids",
    )

    with target.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()

        for record in records:
            writer.writerow(
                {
                    "configuration": record.configuration,
                    "question_id": record.question_id,
                    "recall_at_k": recall_at_k(
                        record.retrieved_source_ids,
                        record.expected_source_ids,
                        k=k,
                    ),
                    "k": k,
                    "report_quality_score": record.report_quality_score,
                    "llm_calls": record.llm_calls,
                    "input_tokens": record.input_tokens,
                    "output_tokens": record.output_tokens,
                    "total_tokens": (
                        record.input_tokens + record.output_tokens
                    ),
                    "latency_seconds": record.latency_seconds,
                    "retrieved_source_ids": json.dumps(
                        record.retrieved_source_ids
                    ),
                    "expected_source_ids": json.dumps(
                        record.expected_source_ids
                    ),
                }
            )


def write_summary_csv(
    summaries: Sequence[EvaluationSummary],
    output_path: str | Path,
) -> None:
    """Write aggregate metrics for each configuration to CSV."""
    if not summaries:
        raise ValueError("At least one summary is required.")

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = list(asdict(summaries[0]).keys())

    with target.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(asdict(summary) for summary in summaries)