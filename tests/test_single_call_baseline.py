from contracts import Chunk
from evals.single_call_baseline import answer_baseline_with_stats


def test_e0_uses_vector_search_and_one_llm_call(monkeypatch):
    import evals.single_call_baseline as baseline

    chunks = [
        Chunk(
            paper_id="2106.09685",
            text=(
                "LoRA freezes the pre-trained model weights. "
                "Example notation: {AttentionDSE} and {ic}."
            ),
            source_url="https://arxiv.org/abs/2106.09685",
        )
    ]

    def fake_search(query, k=8, hybrid=True):
        assert query == "What is LoRA?"
        assert hybrid is False
        return chunks

    async def fake_run(agent, question, state, usage):
        assert agent.name == "single_call_baseline"
        assert agent.output_key == "baseline_report"

        prompt = agent.instruction(None)

        assert "2106.09685" in prompt
        assert "{AttentionDSE}" in prompt
        assert "{ic}" in prompt

        usage.llm_calls = 1
        usage.input_tokens = 100
        usage.output_tokens = 50

        return {"baseline_report": "# LoRA report"}

    monkeypatch.setattr(
        baseline,
        "load_models",
        lambda: ("light-model", "heavy-model"),
    )
    monkeypatch.setattr(
        baseline,
        "harden_agent",
        lambda agent: agent,
    )
    monkeypatch.setattr(
        baseline,
        "_run_agent",
        fake_run,
    )

    report, stats = answer_baseline_with_stats(
        "What is LoRA?",
        search_fn=fake_search,
    )

    assert report.markdown == "# LoRA report"
    assert report.sources == ["2106.09685"]
    assert report.verified is False

    assert stats.retrieved_source_ids == ("2106.09685",)
    assert stats.llm_calls == 1
    assert stats.input_tokens == 100
    assert stats.output_tokens == 50
    assert stats.latency_seconds >= 0


def test_e0_handles_empty_retrieval(monkeypatch):
    import evals.single_call_baseline as baseline

    async def fake_run(agent, question, state, usage):
        prompt = agent.instruction(None)

        assert "No relevant source passages" in prompt

        usage.llm_calls = 1

        return {"baseline_report": "# No sources found"}

    monkeypatch.setattr(
        baseline,
        "load_models",
        lambda: ("light-model", "heavy-model"),
    )
    monkeypatch.setattr(
        baseline,
        "harden_agent",
        lambda agent: agent,
    )
    monkeypatch.setattr(
        baseline,
        "_run_agent",
        fake_run,
    )

    report, stats = answer_baseline_with_stats(
        "Question without matching sources",
        search_fn=lambda query, k=8, hybrid=True: [],
    )

    assert report.markdown == "# No sources found"
    assert report.sources == []
    assert stats.retrieved_source_ids == ()
    assert stats.llm_calls == 1