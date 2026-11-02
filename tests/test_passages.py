from agents.passages import compress_chunks
from contracts import Chunk


def _chunk(paper_id: str, text: str) -> Chunk:
    return Chunk(
        paper_id=paper_id, text=text, score=1.0, source_url=f"https://arxiv.org/abs/{paper_id}"
    )


def test_empty_chunks_are_dropped():
    chunks = [_chunk("1", "one two"), _chunk("2", "   "), _chunk("3", ""), _chunk("4", "three")]
    result = compress_chunks(chunks, 100)
    assert [chunk.paper_id for chunk in result] == ["1", "4"]


def test_none_budget_keeps_everything_unchanged():
    chunks = [_chunk("1", "one two three"), _chunk("2", "four five six")]
    assert compress_chunks(chunks, None) == chunks


def test_none_budget_still_drops_empty_chunks():
    chunks = [_chunk("1", "one"), _chunk("2", " ")]
    assert compress_chunks(chunks, None) == [chunks[0]]


def test_small_budget_trims_last_kept_chunk_and_drops_the_rest():
    chunks = [_chunk("1", "one two three"), _chunk("2", "four five six"), _chunk("3", "seven")]
    result = compress_chunks(chunks, 5)
    assert [chunk.paper_id for chunk in result] == ["1", "2"]
    assert result[0].text == "one two three"
    assert result[1].text == "four five"


def test_kept_chunks_keep_paper_id_and_source_url():
    chunks = [_chunk("1", ""), _chunk("2", "one two three four")]
    result = compress_chunks(chunks, 2)
    assert result == [
        Chunk(paper_id="2", text="one two", score=1.0, source_url="https://arxiv.org/abs/2")
    ]


def test_zero_budget_returns_empty_list():
    assert compress_chunks([_chunk("1", "one two")], 0) == []


def test_input_chunks_are_not_modified():
    chunks = [_chunk("1", "one two three"), _chunk("2", "four five six")]
    snapshot = [chunk.model_copy() for chunk in chunks]
    compress_chunks(chunks, 4)
    assert chunks == snapshot
