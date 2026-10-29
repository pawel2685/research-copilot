from agents.baseline import NO_SOURCES_MESSAGE, answer, build_report
from contracts import Chunk, Report, RunConfig


def _chunk(paper_id: str, text: str, url: str | None = None) -> Chunk:
    if url is None:
        url = f"https://arxiv.org/abs/{paper_id}"
    return Chunk(paper_id=paper_id, text=text, score=1.0, source_url=url)


def _fake_search(chunks):
    calls = []

    def search_fn(query, k=8, hybrid=True):
        calls.append({"query": query, "hybrid": hybrid})
        return list(chunks)

    search_fn.calls = calls
    return search_fn


def test_returns_report_with_question_and_not_verified():
    search_fn = _fake_search([_chunk("1", "alpha beta")])
    report = answer("What is alpha?", RunConfig(), search_fn=search_fn)
    assert isinstance(report, Report)
    assert report.question == "What is alpha?"
    assert report.verified is False
    assert report.markdown.startswith("# What is alpha?")


def test_every_kept_paper_id_is_in_sources_and_markdown_without_duplicates():
    search_fn = _fake_search(
        [_chunk("1", "alpha beta"), _chunk("2", "gamma delta"), _chunk("1", "epsilon zeta")]
    )
    report = answer("q", RunConfig(), search_fn=search_fn)
    assert report.sources == ["1", "2"]
    for paper_id in report.sources:
        assert f"[{paper_id}]" in report.markdown
    sources_section = report.markdown.split("## Sources")[1]
    assert sources_section.count("https://arxiv.org/abs/1") == 1
    assert sources_section.count("https://arxiv.org/abs/2") == 1


def test_markdown_layout():
    search_fn = _fake_search([_chunk("1", "alpha beta")])
    report = answer("q", RunConfig(), search_fn=search_fn)
    assert report.markdown == (
        "# q\n\n## Findings\n- alpha beta [1]\n\n## Sources\n- https://arxiv.org/abs/1\n"
    )


def test_source_falls_back_to_paper_id_when_url_is_empty():
    report = build_report("q", [_chunk("1", "alpha", url="")])
    assert report.markdown.endswith("## Sources\n- 1\n")


def test_none_budget_keeps_all_matched_passages():
    chunks = [_chunk(str(i), "word " * 50) for i in range(5)]
    report = answer("q", RunConfig(compress_budget_words=None), search_fn=_fake_search(chunks))
    assert report.sources == ["0", "1", "2", "3", "4"]


def test_small_budget_keeps_only_the_passages_that_fit():
    chunks = [_chunk("1", "a b c"), _chunk("2", "d e f"), _chunk("3", "g h i")]
    report = answer("q", RunConfig(compress_budget_words=4), search_fn=_fake_search(chunks))
    assert report.sources == ["1", "2"]
    assert "- d [2]" in report.markdown
    assert "g h i" not in report.markdown


def test_zero_budget_gives_no_sources_message():
    search_fn = _fake_search([_chunk("1", "alpha beta")])
    report = answer("q", RunConfig(compress_budget_words=0), search_fn=search_fn)
    assert report.sources == []
    assert NO_SOURCES_MESSAGE in report.markdown
    assert report.verified is False


def test_empty_search_result_gives_no_sources_message():
    report = answer("q", RunConfig(), search_fn=_fake_search([]))
    assert report.markdown == f"# q\n\n{NO_SOURCES_MESSAGE}\n"
    assert report.sources == []


def test_hybrid_flag_is_passed_to_search_fn():
    search_fn = _fake_search([])
    answer("q", RunConfig(hybrid=False), search_fn=search_fn)
    answer("q", RunConfig(hybrid=True), search_fn=search_fn)
    assert [call["hybrid"] for call in search_fn.calls] == [False, True]


def test_default_config_is_used_when_none_is_given():
    search_fn = _fake_search([])
    answer("q", search_fn=search_fn)
    assert search_fn.calls == [{"query": "q", "hybrid": RunConfig().hybrid}]


def test_works_with_the_default_stub():
    report = answer("low-rank matrices")
    assert "2106.09685" in report.sources
