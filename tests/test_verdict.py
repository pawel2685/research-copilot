import asyncio
import json
import time

import pytest
from google.adk.agents import SequentialAgent
from google.adk.events import Event
from google.adk.runners import InMemoryRunner
from google.genai import types

from agents.critic import ClaimAssessment, CriticResult, create_critic_agent, critic_skipped_result
from agents.orchestrator import build_pipeline, notes_keys
from agents.tools import make_search_tool
from agents.verdict import ReadableSequentialAgent, format_critic_result, readable_event
from contracts import RunConfig
from stubs.search import search as stub_search
from tests.fake_llm import FakeLlm


def _claim(text="LoRA freezes the weights.", status="supported", ids=("2106.09685",), why="The abstract says so."):
    return ClaimAssessment(claim=text, status=status, source_ids=list(ids), rationale=why)


def test_an_approved_verdict_is_a_short_readable_summary():
    text = format_critic_result(CriticResult(approved=True, assessments=[_claim(), _claim("B.", ids=("1706.03762",))]))

    assert text.startswith("### Critic: approved")
    assert "2 of 2 claims are supported" in text
    assert "The report is **verified**." in text
    assert "- **supported** [2106.09685]: LoRA freezes the weights." in text
    assert "- **supported** [1706.03762]: B." in text
    assert "titles and abstracts" in text
    assert "{" not in text and '"approved"' not in text
    # A supported claim needs no explanation.
    assert "Why:" not in text


def test_a_rejected_verdict_lists_the_problems_and_the_corrections():
    result = CriticResult(
        approved=False,
        assessments=[
            _claim(),
            _claim("RAG never changes weights.", "unsupported", ("2005.11401",), "The abstract mentions fine-tuning."),
            _claim("It is faster.", "contradicted", (), "The paper says the opposite."),
        ],
        revision_instructions=["Remove the claim about weights.", "Drop the speed claim."],
    )

    text = format_critic_result(result)

    assert text.startswith("### Critic: changes needed")
    assert "1 of 3 claims are supported" in text
    assert "The report is **not verified**." in text
    assert "- **unsupported** [2005.11401]: RAG never changes weights." in text
    assert "  - Why: The abstract mentions fine-tuning." in text
    # A claim without sources has no brackets.
    assert "- **contradicted**: It is faster." in text
    assert "**Corrections for the Writer:**" in text
    assert "- Remove the claim about weights." in text
    assert "- Drop the speed claim." in text


def test_a_skipped_critic_says_so_and_why():
    text = format_critic_result(critic_skipped_result("Critic skipped because the time budget was insufficient."))

    assert text.startswith("### Critic: skipped")
    assert "time budget was insufficient" in text
    assert "**not verified**" in text


def test_a_skipped_critic_without_a_message_still_explains():
    result = CriticResult(approved=None, message="")
    assert "was not checked" in format_critic_result(result)


def test_a_verdict_without_claims_has_no_empty_list():
    text = format_critic_result(CriticResult(approved=True))
    assert "0 of 0 claims" in text
    assert "\n- " not in text


def _event(text, author="critic", partial=False):
    return Event(
        author=author,
        partial=partial,
        content=types.Content(role="model", parts=[types.Part(text=text)]),
    )


def test_the_json_message_of_the_critic_becomes_text():
    event = readable_event(_event(CriticResult(approved=True).model_dump_json()))
    assert event.content.parts[0].text.startswith("### Critic: approved")


@pytest.mark.parametrize(
    "event",
    [
        _event("# A report", author="writer"),
        _event(CriticResult(approved=True).model_dump_json(), author="writer"),
        _event(CriticResult(approved=True).model_dump_json(), partial=True),
        _event("not json at all"),
        _event('{"approved": "maybe"}'),
        _event(""),
        Event(author="critic"),
        Event(author="critic", content=types.Content(role="model", parts=[])),
    ],
)
def test_other_messages_are_left_alone(event):
    before = event.model_dump_json()
    assert readable_event(event).model_dump_json() == before


def _pipeline(fake, pipeline_class):
    return build_pipeline(
        RunConfig(use_planner=False),
        search_tool=make_search_tool(stub_search),
        critic=create_critic_agent(fake),
        models=(fake, fake),
        pipeline_class=pipeline_class,
    )


def _run(pipeline):
    """Run one question on the real ADK runner, with the start state that the runner sets."""
    start_state = {
        "question": "low-rank matrices",
        "sub_questions": ["low-rank matrices"],
        "deadline_at": time.time() + 300,
        **{key: "" for key in notes_keys()},
    }

    async def run():
        runner = InMemoryRunner(agent=pipeline, app_name="verdict-test")
        session = await runner.session_service.create_session(
            app_name="verdict-test", user_id="u", state=start_state
        )
        message = types.Content(role="user", parts=[types.Part(text="low-rank matrices")])
        events = [
            event
            async for event in runner.run_async(user_id="u", session_id=session.id, new_message=message)
        ]
        stored = await runner.session_service.get_session(
            app_name="verdict-test", user_id="u", session_id=session.id
        )
        return events, stored.state

    return asyncio.run(run())


def _texts(events, author):
    return [
        part.text
        for event in events
        if event.author == author and event.content
        for part in event.content.parts or []
        if part.text
    ]


def test_the_chat_of_the_real_runner_ends_with_text_and_the_state_keeps_the_data():
    critic_json = json.dumps(
        {
            "approved": False,
            "assessments": [
                {"claim": "A claim.", "status": "unsupported", "source_ids": ["2106.09685"], "rationale": "No evidence."}
            ],
            "revision_instructions": ["Fix the claim."],
        }
    )
    events, state = _run(_pipeline(FakeLlm(critic_json=critic_json), ReadableSequentialAgent))

    (verdict,) = _texts(events, "critic")
    assert verdict.startswith("### Critic: changes needed")
    assert "Fix the claim." in verdict
    assert '"approved"' not in verdict
    # The other agents are not changed.
    assert _texts(events, "writer")[0].startswith("REPORT ")
    # The data in the session is the original result, not the text.
    assert state["critic_result"]["approved"] is False
    assert state["critic_result"]["revision_instructions"] == ["Fix the claim."]


def test_a_plain_sequential_agent_still_shows_the_json():
    """The switch is the pipeline class: the default flow of the app is not changed."""
    events, _ = _run(_pipeline(FakeLlm(critic_json='{"approved": true}'), SequentialAgent))

    (verdict,) = _texts(events, "critic")
    assert json.loads(verdict)["approved"] is True


def test_the_demo_flow_is_the_readable_one():
    import importlib
    import sys

    import dotenv

    from _pytest.monkeypatch import MonkeyPatch

    with MonkeyPatch.context() as patch:
        patch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)
        patch.setenv("MODEL_LIGHT", "dummy-light")
        patch.setenv("MODEL_HEAVY", "dummy-heavy")
        for name in ("demo.research_copilot", "demo.research_copilot.agent"):
            patch.delitem(sys.modules, name, raising=False)
        demo = importlib.import_module("demo.research_copilot.agent")
        assert isinstance(demo.root_agent, ReadableSequentialAgent)
