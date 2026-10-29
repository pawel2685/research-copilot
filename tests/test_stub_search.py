from contracts import Chunk, SearchFn
from stubs.search import search


def test_search_returns_chunks():
    results = search("language model")
    assert results
    assert all(isinstance(chunk, Chunk) for chunk in results)


def test_best_match_comes_first():
    results = search("low-rank matrices")
    assert results[0].paper_id == "2106.09685"


def test_scores_are_not_increasing():
    scores = [chunk.score for chunk in search("language model")]
    assert scores == sorted(scores, reverse=True)


def test_k_limits_the_number_of_results():
    assert len(search("language model", k=1)) == 1


def test_no_match_returns_empty_list():
    assert search("zzz") == []


def test_hybrid_flag_is_ignored():
    assert search("language model", hybrid=True) == search("language model", hybrid=False)


def test_sources_point_to_arxiv():
    for chunk in search("language model"):
        assert chunk.source_url == f"https://arxiv.org/abs/{chunk.paper_id}"


def test_stub_fits_the_contract():
    fn: SearchFn = search
    assert fn("attention", k=1)[0].paper_id == "1706.03762"
