import asyncio
from types import SimpleNamespace

import pytest
from google.adk.agents import SequentialAgent
from google.adk.models.llm_request import LlmRequest
from google.adk.runners import InMemoryRunner
from google.genai import types

from agents import model_switch
from agents.model_switch import (
    CHOICE_KEY,
    USED_KEY,
    add_writer_switch,
    make_model_override,
    split_command,
)
from agents.orchestrator import build_pipeline
from agents.tools import make_search_tool
from contracts import RunConfig
from stubs.search import search as stub_search
from tests.fake_llm import FakeLlm


@pytest.mark.parametrize(
    "text, expected",
    [
        ("/lite What is LoRA?", ("light", "What is LoRA?")),
        ("/light What is LoRA?", ("light", "What is LoRA?")),
        ("/heavy What is LoRA?", ("heavy", "What is LoRA?")),
        ("  /LITE   What is LoRA?  ", ("light", "What is LoRA?")),
        ("/lite", ("light", "")),
        ("/heavy   ", ("heavy", "")),
        ("What is LoRA?", (None, "What is LoRA?")),
        ("  What is LoRA?  ", (None, "What is LoRA?")),
        ("", (None, "")),
        ("/unknown What is LoRA?", (None, "/unknown What is LoRA?")),
        ("Is /lite a command?", (None, "Is /lite a command?")),
        ("/litely", (None, "/litely")),
    ],
)
def test_split_command(text, expected):
    assert split_command(text) == expected


def _request(model="original"):
    return LlmRequest(model=model, contents=[])


@pytest.mark.parametrize(
    "state, expected",
    [
        ({}, "heavy-model"),
        ({CHOICE_KEY: "heavy"}, "heavy-model"),
        ({CHOICE_KEY: "light"}, "light-model"),
        ({CHOICE_KEY: "nonsense"}, "heavy-model"),
    ],
)
def test_override_sets_the_model_from_the_chat_choice(state, expected):
    ctx = SimpleNamespace(state=state)
    request = _request()

    assert make_model_override("light-model", "heavy-model")(ctx, request) is None

    assert request.model == expected
    assert ctx.state[USED_KEY] == expected


def _pipeline(callback=None):
    fake = FakeLlm()
    pipeline = build_pipeline(
        RunConfig(use_planner=False, use_critic=False),
        search_tool=make_search_tool(stub_search),
        models=(fake, fake),
    )
    if callback:
        writer = next(a for a in pipeline.sub_agents if a.name == "writer")
        writer.before_model_callback = callback
    return pipeline


def test_the_switch_goes_in_front_of_the_cache_of_the_writer_only():
    pipeline = add_writer_switch(_pipeline(), "light-model", "heavy-model")

    by_name = {agent.name: agent for agent in pipeline.sub_agents}
    callbacks = by_name["writer"].before_model_callback
    assert callbacks[0].__name__ == "override"
    # The cache callback of the Writer is still there, behind the switch.
    assert [c.__name__ for c in callbacks[1:]] == ["before_model"]
    assert [a.name for a in pipeline.sub_agents] == ["search_branches", "writer"]
    assert by_name["search_branches"].sub_agents[0].sub_agents[0].before_model_callback[0].__name__ == "before_model"


def test_the_switch_keeps_a_single_callback_that_was_not_a_list():
    def other(ctx, request):
        return None

    pipeline = _pipeline()
    writer = next(a for a in pipeline.sub_agents if a.name == "writer")
    writer.before_model_callback = other

    add_writer_switch(pipeline, "light-model", "heavy-model")

    assert writer.before_model_callback[1:] == [other]


def test_the_switch_works_for_a_writer_without_callbacks():
    pipeline = _pipeline()
    writer = next(a for a in pipeline.sub_agents if a.name == "writer")
    writer.before_model_callback = None

    add_writer_switch(pipeline, "light-model", "heavy-model")

    assert len(writer.before_model_callback) == 1


def test_a_pipeline_without_a_writer_is_left_alone():
    pipeline = SequentialAgent(name="empty", sub_agents=[])
    assert add_writer_switch(pipeline, "l", "h") is pipeline


class RecordingFake(FakeLlm):
    """Records the model name of every request, by the role in the system instruction."""

    seen: list = []

    async def generate_content_async(self, llm_request, stream=False):
        system = str(llm_request.config.system_instruction)
        self.seen.append(("Writer" if "You are the Writer" in system else "other", llm_request.model))
        async for response in super().generate_content_async(llm_request, stream):
            yield response


def test_the_chat_choice_reaches_the_model_call_of_the_writer(monkeypatch):
    """The whole flow on the real ADK runner: `/lite` and `/heavy` change the Writer's model."""
    # The demo builds its pipeline when it is imported, so it needs model names and no real `.env`.
    import importlib
    import sys

    import dotenv

    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)
    monkeypatch.setenv("MODEL_LIGHT", "dummy-light")
    monkeypatch.setenv("MODEL_HEAVY", "dummy-heavy")
    for name in ("demo.research_copilot", "demo.research_copilot.agent"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    demo = importlib.import_module("demo.research_copilot.agent")

    fake = RecordingFake(seen=[])
    pipeline = build_pipeline(
        RunConfig(use_planner=False, use_critic=False),
        search_tool=make_search_tool(stub_search),
        models=(fake, fake),
    )
    pipeline.before_agent_callback = demo.make_start_callback(RunConfig())
    add_writer_switch(pipeline, "light-model", "heavy-model")

    async def ask(runner, session, text):
        message = types.Content(role="user", parts=[types.Part(text=text)])
        async for _ in runner.run_async(user_id="u", session_id=session.id, new_message=message):
            pass
        stored = await runner.session_service.get_session(
            app_name="switch-test", user_id="u", session_id=session.id
        )
        return stored.state

    async def run():
        runner = InMemoryRunner(agent=pipeline, app_name="switch-test")
        session = await runner.session_service.create_session(app_name="switch-test", user_id="u")
        states = []
        for text in ("low-rank matrices", "/lite low-rank matrices", "attention", "/heavy attention"):
            states.append(await ask(runner, session, text))
        return states

    states = asyncio.run(run())

    writer_models = [model for role, model in fake.seen if role == "Writer"]
    # No command: the model of the environment. `/lite` is sticky. `/heavy` goes back.
    assert writer_models == ["heavy-model", "light-model", "light-model", "heavy-model"]
    assert [s[USED_KEY] for s in states] == writer_models
    # The command is not part of the question.
    assert states[1]["question"] == "low-rank matrices"
    assert "2106.09685" in states[1]["report_markdown"]


def test_module_exports():
    assert model_switch.CHOICE_KEY == "writer_model_choice"
    assert model_switch.USED_KEY == "writer_model_used"
