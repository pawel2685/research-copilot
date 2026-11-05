
import csv

import pytest

from evals.metrics import EXPERIMENT_CONFIGS
from evals.manual_review import (
    load_manual_reviews,
    summarize_manual_reviews,
    write_manual_review_outputs,
)


def create_manual_csv(path, rows):
    fieldnames = [
        "configuration",
        "question_id",
        "manual_quality_score",
        "reviewer_notes",
    ]

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)



def test_load_manual_reviews_ignores_blank_scores(tmp_path):
    path = tmp_path / "manual_review.csv"

    rows = []

    for configuration in EXPERIMENT_CONFIGS:
        rows.append(
            {
                "configuration": configuration,
                "question_id": "q001-rag",
                "manual_quality_score": "4",
                "reviewer_notes": (
                    "Good coverage." if configuration == "E0" else ""
                ),
            }
        )

        rows.append(
            {
                "configuration": configuration,
                "question_id": "q002-transformer",
                "manual_quality_score": "",
                "reviewer_notes": "",
            }
        )

    create_manual_csv(path, rows)

    reviews = load_manual_reviews(path)

    assert len(reviews) == 5
    assert all(
        review["question_id"] == "q001-rag"
        for review in reviews
    )

    assert reviews[0]["configuration"] == "E0"
    assert reviews[0]["manual_quality_score"] == 4.0
    assert reviews[0]["reviewer_notes"] == "Good coverage."



def test_summarize_manual_reviews_groups_by_configuration():
    reviews = [
        {
            "configuration": "E0",
            "question_id": "q001-rag",
            "manual_quality_score": 4.0,
            "reviewer_notes": "",
        },
        {
            "configuration": "E0",
            "question_id": "q004-lora",
            "manual_quality_score": 2.0,
            "reviewer_notes": "",
        },
        {
            "configuration": "E2",
            "question_id": "q001-rag",
            "manual_quality_score": 5.0,
            "reviewer_notes": "",
        },
    ]

    summaries = summarize_manual_reviews(reviews)

    assert len(summaries) == 2

    assert summaries[0]["configuration"] == "E0"
    assert summaries[0]["reviewed_count"] == 2
    assert summaries[0]["mean_manual_quality_score"] == 3.0
    assert summaries[0]["min_manual_quality_score"] == 2.0
    assert summaries[0]["max_manual_quality_score"] == 4.0

    assert summaries[1]["configuration"] == "E2"
    assert summaries[1]["mean_manual_quality_score"] == 5.0


def test_load_manual_reviews_rejects_invalid_score(tmp_path):
    path = tmp_path / "manual_review.csv"

    create_manual_csv(
        path,
        [
            {
                "configuration": "E0",
                "question_id": "q001-rag",
                "manual_quality_score": "6",
                "reviewer_notes": "",
            }
        ],
    )

    with pytest.raises(ValueError, match="between 1 and 5"):
        load_manual_reviews(path)


def test_load_manual_reviews_rejects_duplicate_entries(tmp_path):
    path = tmp_path / "manual_review.csv"

    row = {
        "configuration": "E0",
        "question_id": "q001-rag",
        "manual_quality_score": "4",
        "reviewer_notes": "",
    }

    create_manual_csv(path, [row, row])

    with pytest.raises(ValueError, match="Duplicate"):
        load_manual_reviews(path)


def test_load_manual_reviews_rejects_empty_sheet(tmp_path):
    path = tmp_path / "manual_review.csv"

    create_manual_csv(
        path,
        [
            {
                "configuration": "E0",
                "question_id": "q001-rag",
                "manual_quality_score": "",
                "reviewer_notes": "",
            }
        ],
    )

    with pytest.raises(ValueError, match="No manual scores"):
        load_manual_reviews(path)


def test_write_manual_review_outputs(tmp_path):
    reviews = [
        {
            "configuration": "E0",
            "question_id": "q001-rag",
            "manual_quality_score": 4.0,
            "reviewer_notes": "Clear answer.",
        },
        {
            "configuration": "E1",
            "question_id": "q001-rag",
            "manual_quality_score": 5.0,
            "reviewer_notes": "Very good citations.",
        },
    ]

    outputs = write_manual_review_outputs(reviews, tmp_path)

    assert outputs["summary_csv"].exists()
    assert outputs["summary_markdown"].exists()
    assert outputs["chart"].exists()

    markdown = outputs["summary_markdown"].read_text(
        encoding="utf-8"
    )

    assert "Manual quality review" in markdown
    assert "Very good citations." in markdown


def test_load_manual_reviews_rejects_unbalanced_sample(tmp_path):
    path = tmp_path / "manual_review.csv"

    rows = [
        {
            "configuration": "E0",
            "question_id": "q001-rag",
            "manual_quality_score": "4",
            "reviewer_notes": "",
        },
        {
            "configuration": "E1",
            "question_id": "q001-rag",
            "manual_quality_score": "3",
            "reviewer_notes": "",
        },
    ]

    create_manual_csv(path, rows)

    with pytest.raises(
        ValueError,
        match="same question IDs for every configuration",
    ):
        load_manual_reviews(path)
