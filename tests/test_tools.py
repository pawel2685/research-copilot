from agents.tools import make_search_tool
from contracts import Chunk


def _fake_search(chunks):
    calls = []

    def search_fn(query, k=8, hybrid=True):
        calls.append({"query": query, "k": k, "hybrid": hybrid})
        return list(chunks)

    search_fn.calls = calls
    return search_fn


def _chunk(paper_id, text):
    return Chunk(paper_id=paper_id, text=text, source_url=f"https://arxiv.org/abs/{paper_id}")


def test_tool_returns_dicts_with_the_three_keys():
    tool = make_search_tool(_fake_search([_chunk("1", "alpha beta")]))
    assert tool("alpha") == [
        {"paper_id": "1", "text": "alpha beta", "source_url": "https://arxiv.org/abs/1"}
    ]


def test_tool_honours_the_word_budget():
    tool = make_search_tool(
        _fake_search([_chunk("1", "a b c"), _chunk("2", "d e f")]), budget_words=4
    )
    assert [(p["paper_id"], p["text"]) for p in tool("q")] == [("1", "a b c"), ("2", "d")]


def test_tool_without_budget_keeps_everything():
    tool = make_search_tool(_fake_search([_chunk("1", "a b c"), _chunk("2", "d e f")]))
    assert len(tool("q")) == 2


def test_tool_passes_query_hybrid_and_k_to_the_search_function():
    search_fn = _fake_search([])
    make_search_tool(search_fn, hybrid=False, k=3)("my query")
    assert search_fn.calls == [{"query": "my query", "k": 3, "hybrid": False}]


def test_tool_name_and_docstring_describe_it_for_the_model():
    tool = make_search_tool(_fake_search([]))
    assert tool.__name__ == "search_papers"
    assert "query" in tool.__doc__


def test_tool_works_with_the_stub_search():
    from stubs.search import search

    tool = make_search_tool(search)
    assert "2106.09685" in [p["paper_id"] for p in tool("low-rank")]
