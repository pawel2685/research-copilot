"""The whole flow on the real ADK runner, with a fake model instead of Gemini."""
import asyncio

from google.adk.agents import LlmAgent

from agents.critic import create_critic_agent
from agents.runner import run_pipeline
from contracts import Chunk, RunConfig
from tests.fake_llm import FakeLlm

QUESTION = "low-rank matrices"
NO_OPTIONAL = RunConfig(use_planner=False, use_critic=False)


def _run(fake, cfg, question=QUESTION, **kwargs):
    return asyncio.run(run_pipeline(question, cfg, models=(fake, fake), **kwargs))


def _planner(fake):
    return LlmAgent(
        name="planner",
        model=fake,
        instruction="You are the Planner. Split the question.",
        output_key="sub_questions",
    )


def test_one_branch_runs_and_the_notes_reach_the_writer():
    fake = FakeLlm()
    result = _run(fake, NO_OPTIONAL)
    assert result.sub_questions == [QUESTION]
    assert "2106.09685" in result.state["search_results_1"]
    assert "2106.09685" in result.state["reading_notes_1"]
    assert "2106.09685" in result.report_markdown
    # Branches 2 to 4 were skipped: they have no sub-question.
    for n in (2, 3, 4):
        assert f"reading_notes_{n}" not in result.state
    assert len(fake.instructions["Searcher"]) == 2  # tool call, then the answer
    assert len(fake.instructions["Reader"]) == 1
    assert len(fake.instructions["Writer"]) == 1


def test_sub_question_and_passages_are_filled_into_the_instructions():
    fake = FakeLlm()
    _run(fake, NO_OPTIONAL)
    assert f"Question to search for:\n{QUESTION}" in fake.instructions["Searcher"][0]
    assert "2106.09685" in fake.instructions["Reader"][0]
    assert "2106.09685" in fake.instructions["Writer"][0]
    assert "reading_notes_" not in fake.instructions["Writer"][0]  # no placeholder left


def test_planner_sub_questions_run_in_parallel_branches():
    fake = FakeLlm(planner_json='["low-rank matrices", "attention"]')
    result = _run(fake, RunConfig(use_critic=False), planner=_planner(fake))
    assert result.sub_questions == ["low-rank matrices", "attention"]
    assert "2106.09685" in result.state["reading_notes_1"]
    assert "1706.03762" in result.state["reading_notes_2"]
    assert "reading_notes_3" not in result.state
    assert "2106.09685" in result.report_markdown
    assert "1706.03762" in result.report_markdown


def test_tiny_time_budget_skips_planner_and_critic_and_still_returns_a_report():
    fake = FakeLlm()
    result = _run(
        fake,
        RunConfig(time_budget_s=0),
        planner=_planner(fake),
        critic=create_critic_agent(fake),
    )
    assert "Planner" not in fake.instructions
    assert "Critic" not in fake.instructions
    assert result.sub_questions == [QUESTION]
    assert "2106.09685" in result.report_markdown
    assert result.critic_result.unverified is True
    assert result.verified is False


def test_critic_approval_gives_a_verified_result():
    fake = FakeLlm(critic_json='{"approved": true}')
    result = _run(fake, RunConfig(use_planner=False), critic=create_critic_agent(fake))
    assert len(fake.instructions["Critic"]) == 1
    assert result.critic_result.approved is True
    assert result.verified is True
    assert result.revised is False


def test_critic_rejection_triggers_exactly_one_revision():
    fake = FakeLlm(critic_json='{"approved": false, "revision_instructions": ["Fix X."]}')
    result = _run(fake, RunConfig(use_planner=False), critic=create_critic_agent(fake))
    assert len(fake.instructions["Critic"]) == 1
    assert len(fake.instructions["Writer"]) == 2
    revision = fake.instructions["Writer"][1]
    assert "- Fix X." in revision
    assert "REPORT" in revision  # the draft
    assert "2106.09685" in revision  # the notes
    assert result.revised is True
    assert result.verified is False


def test_search_function_gets_the_config_and_the_budget():
    calls = []

    def search_fn(query, k=8, hybrid=True):
        calls.append((query, hybrid))
        return [Chunk(paper_id="1", text="one two three four", source_url="u")]

    fake = FakeLlm()
    cfg = RunConfig(use_planner=False, use_critic=False, hybrid=False, compress_budget_words=2)
    result = _run(fake, cfg, search_fn=search_fn)
    assert calls == [(QUESTION, False)]
    assert "one two" in result.state["search_results_1"]
    assert "three" not in result.state["search_results_1"]
