from agents.baseline import NO_SOURCES_MESSAGE, answer, build_report, merge_chunks
from agents.critic import CriticResult
from agents.deadline import Deadline
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


def _fail_planner(question):
    raise AssertionError("planner must not be called")


def _fail_critic(report, chunks):
    raise AssertionError("critic must not be called")


def test_tiny_time_budget_skips_both_agents_and_still_returns_a_report():
    search_fn = _fake_search([_chunk("1", "alpha beta")])
    report = answer(
        "q",
        RunConfig(time_budget_s=0.0),
        search_fn=search_fn,
        planner_fn=_fail_planner,
        critic_fn=_fail_critic,
    )
    assert isinstance(report, Report)
    assert report.sources == ["1"]
    assert report.verified is False
    assert [call["query"] for call in search_fn.calls] == ["q"]


def test_given_deadline_is_used_instead_of_the_config_budget():
    deadline = Deadline.after(0.0)
    report = answer(
        "q",
        RunConfig(time_budget_s=1000.0),
        search_fn=_fake_search([_chunk("1", "alpha")]),
        critic_fn=_fail_critic,
        deadline=deadline,
    )
    assert report.verified is False


def test_planner_sub_questions_are_all_searched_and_duplicates_removed():
    def search_fn(query, k=8, hybrid=True):
        calls.append(query)
        return [_chunk("shared", "same text"), _chunk(query, f"text of {query}")]

    calls = []
    report = answer(
        "q",
        RunConfig(),
        search_fn=search_fn,
        planner_fn=lambda q: ["a", "b"],
    )
    assert calls == ["a", "b"]
    assert report.sources == ["shared", "a", "b"]
    assert report.markdown.count("same text") == 1


def test_approving_critic_gives_verified_true():
    seen = []

    def critic_fn(report, chunks):
        seen.append((report, chunks))
        return CriticResult(approved=True)

    report = answer(
        "q", RunConfig(), search_fn=_fake_search([_chunk("1", "alpha")]), critic_fn=critic_fn
    )
    assert report.verified is True
    assert seen[0][0].sources == ["1"]
    assert [chunk.paper_id for chunk in seen[0][1]] == ["1"]


def test_rejecting_critic_gives_verified_false():
    report = answer(
        "q",
        RunConfig(),
        search_fn=_fake_search([_chunk("1", "alpha")]),
        critic_fn=lambda report, chunks: CriticResult(approved=False),
    )
    assert report.verified is False


def test_merge_chunks_keeps_the_highest_score_first_and_removes_duplicates():
    low = Chunk(paper_id="1", text="same", score=1.0)
    high = Chunk(paper_id="1", text="same", score=5.0)
    other = Chunk(paper_id="2", text="other", score=3.0)
    assert merge_chunks([[low, other], [high]]) == [high, other]
