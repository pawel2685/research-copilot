from functools import partial

import numpy as np
import pytest

from agents import retrieval_search
from agents.retrieval_search import search, to_chunk
from contracts import Chunk, SearchFn
from retrieval import Paper, save_corpus


class Encoder:
    """Deterministic vectors, so no embedding model is downloaded."""

    def encode(self, texts, **kwargs):
        return np.array(
            [[1.0, 0.0] if "retrieval" in text.lower() else [0.0, 1.0] for text in texts]
        )


@pytest.fixture(autouse=True)
def fresh_retrievers():
    retrieval_search._retriever.cache_clear()
    yield
    retrieval_search._retriever.cache_clear()


@pytest.fixture
def data_dir(tmp_path):
    papers = [
        Paper(
            "2005.11401v4",
            "Retrieval-Augmented Generation",
            "Retrieval helps language models answer knowledge questions",
            ["P. Lewis"],
            "2020-05-22",
            "https://arxiv.org/abs/2005.11401v4",
        ),
        Paper(
            "2106.09685v2",
            "LoRA",
            "Low-rank adaptation of large language models",
            ["E. Hu"],
            "2021-06-17",
            "https://arxiv.org/abs/2106.09685v2",
        ),
    ]
    save_corpus(papers, tmp_path / "corpus.jsonl")
    return tmp_path


@pytest.fixture
def with_fake_encoder(monkeypatch):
    original = retrieval_search.Retriever
    monkeypatch.setattr(
        retrieval_search,
        "Retriever",
        lambda papers, path: original(papers, path, encoder=Encoder()),
    )


def test_to_chunk_maps_the_fields_and_drops_the_version():
    item = {
        "arxiv_id": "2005.11401v4",
        "text": "Title\n\nAbstract",
        "score": 3,
        "url": "https://arxiv.org/abs/2005.11401v4",
    }
    assert to_chunk(item) == Chunk(
        paper_id="2005.11401",
        text="Title\n\nAbstract",
        score=3.0,
        source_url="https://arxiv.org/abs/2005.11401v4",
    )


def test_id_without_version_is_kept():
    item = {"arxiv_id": "2005.11401", "text": "t", "score": 1.0, "url": "u"}
    assert to_chunk(item).paper_id == "2005.11401"


def test_search_returns_chunks_with_plain_arxiv_ids(data_dir, with_fake_encoder):
    results = search("retrieval", data_dir=data_dir)
    assert results
    assert all(isinstance(chunk, Chunk) for chunk in results)
    assert results[0].paper_id == "2005.11401"
    assert "Retrieval-Augmented" in results[0].text
    assert results[0].source_url.startswith("https://arxiv.org/abs/")


def test_k_limits_the_number_of_results(data_dir, with_fake_encoder):
    assert len(search("language models", k=1, data_dir=data_dir)) == 1


def test_hybrid_flag_selects_the_mode(data_dir, monkeypatch):
    modes = []

    class FakeRetriever:
        def __init__(self, papers, path):
            pass

        def search(self, query, top_k, mode):
            modes.append((top_k, mode))
            return []

    monkeypatch.setattr(retrieval_search, "Retriever", FakeRetriever)
    search("query", k=3, hybrid=True, data_dir=data_dir)
    search("query", k=3, hybrid=False, data_dir=data_dir)
    assert modes == [(3, "hybrid"), (3, "vector")]


def test_blank_query_returns_empty_list(data_dir, with_fake_encoder):
    assert search("   ", data_dir=data_dir) == []


def test_corpus_is_loaded_once_per_directory(data_dir, monkeypatch):
    loads = []
    real_load = retrieval_search.load_corpus
    monkeypatch.setattr(
        retrieval_search,
        "load_corpus",
        lambda path: loads.append(path) or real_load(path),
    )
    search("retrieval", data_dir=data_dir)
    search("language", data_dir=data_dir)
    assert len(loads) == 1


def test_missing_corpus_explains_how_to_build_it(tmp_path):
    with pytest.raises(RuntimeError, match="python -m retrieval fetch"):
        search("retrieval", data_dir=tmp_path)


def test_adapter_fits_the_contract(data_dir, with_fake_encoder):
    fn: SearchFn = partial(search, data_dir=data_dir)
    assert fn("retrieval", k=1)[0].paper_id == "2005.11401"


def test_default_data_dir_is_the_one_of_b():
    from retrieval.search import DEFAULT_DATA

    assert search.__kwdefaults__["data_dir"] == DEFAULT_DATA
