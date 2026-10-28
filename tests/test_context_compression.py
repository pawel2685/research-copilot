
import pytest

from context.compression import compress


def test_preserves_chunks_that_fit_budget():
    chunks = ["one two", "three four"]

    assert compress(chunks, budget=4) == chunks


def test_truncates_last_chunk_to_remaining_budget():
    assert compress(
        ["one two", "three four five"],
        budget=4,
    ) == ["one two", "three four"]


def test_zero_budget_returns_empty_list():
    assert compress(["one two", "three"], budget=0) == []


def test_empty_chunks_are_skipped():
    assert compress(["", "  ", "one two"], budget=2) == ["one two"]


def test_negative_budget_raises_value_error():
    with pytest.raises(ValueError):
        compress(["one two"], budget=-1)


def test_non_integer_budget_raises_type_error():
    with pytest.raises(TypeError):
        compress(["one two"], budget=1.5)


def test_string_is_not_accepted_as_chunk_sequence():
    with pytest.raises(TypeError):
        compress("one two", budget=2)


def test_non_string_chunk_raises_type_error():
    with pytest.raises(TypeError):
        compress(["one", 2], budget=3)


def test_does_not_modify_original_chunks():
    chunks = ["one two", "three four"]
    original = chunks.copy()

    compress(chunks, budget=3)

    assert chunks == original
