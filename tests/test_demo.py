import asyncio
import importlib
import sys
import time
from types import SimpleNamespace

import pytest
from google.adk.agents import SequentialAgent
from google.genai import types

from contracts import RunConfig
from stubs.search import search as stub_search


@pytest.fixture
def demo(monkeypatch):
    """Import the demo agent fresh, with dummy model names and no real `.env`."""
    import dotenv

    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)
    monkeypatch.setenv("MODEL_LIGHT", "dummy-light")
    monkeypatch.setenv("MODEL_HEAVY", "dummy-heavy")
    for name in ("demo.research_copilot", "demo.research_copilot.agent"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    return importlib.import_module("demo.research_copilot.agent")


def _names(pipeline):
    return [agent.name for agent in pipeline.sub_agents]


def test_importing_the_demo_gives_a_root_agent_without_a_network_call(demo):
    assert isinstance(demo.root_agent, SequentialAgent)
    # The default config has the Critic on and no Planner is available yet.
    assert _names(demo.root_agent) == [
        "planner",
        "search_branches",
        "writer",
        "critic",
    ]


def test_the_package_exposes_the_agent_module_for_adk_web(demo):
    package = importlib.import_module("demo.research_copilot")
    assert package.agent is demo


def test_the_models_come_from_the_environment(demo):
    planner = demo.root_agent.sub_agents[0]
    writer = demo.root_agent.sub_agents[2]
    critic = demo.root_agent.sub_agents[3]

    assert planner.model.model == "dummy-light"
    assert writer.model.model == "dummy-heavy"
    assert critic.model.model == "dummy-light"


def test_the_critic_is_left_out_when_the_config_switches_it_off(demo):
    pipeline = demo.build_demo_pipeline(RunConfig(use_critic=False))
    assert _names(pipeline) == ["planner", "search_branches", "writer"]


def test_the_project_root_is_importable_for_adk_web(demo):
    assert str(demo.ROOT) in sys.path
    assert (demo.ROOT / "contracts.py").exists()


def _ctx(text, state=None):
    content = types.Content(role="user", parts=[types.Part(text=text)]) if text else None
    return SimpleNamespace(user_content=content, state=state if state is not None else {})


def test_start_callback_prepares_the_state_for_the_question(demo):
    cfg = RunConfig(time_budget_s=60)
    ctx = _ctx("  What is LoRA?  ")
    before = time.time()
    assert demo.make_start_callback(cfg)(ctx) is None
    assert ctx.state["question"] == "What is LoRA?"
    assert ctx.state["sub_questions"] == ["What is LoRA?"]
    assert before + 60 <= ctx.state["deadline_at"] <= time.time() + 60
    assert all(ctx.state[f"reading_notes_{n}"] == "" for n in range(1, 5))


def test_start_callback_reads_the_model_command_and_strips_it_from_the_question(demo):
    ctx = _ctx("/lite What is LoRA?")
    demo.make_start_callback(RunConfig())(ctx)
    assert ctx.state["question"] == "What is LoRA?"
    assert ctx.state["sub_questions"] == ["What is LoRA?"]
    assert ctx.state["writer_model_choice"] == "light"


def test_the_model_choice_stays_until_it_is_changed(demo):
    state = {}
    start = demo.make_start_callback(RunConfig())
    start(_ctx("/lite first", state))
    start(_ctx("second", state))
    assert state["writer_model_choice"] == "light"
    start(_ctx("/heavy third", state))
    assert state["writer_model_choice"] == "heavy"
    assert state["question"] == "third"


def test_a_message_without_a_command_sets_no_choice(demo):
    ctx = _ctx("What is LoRA?")
    demo.make_start_callback(RunConfig())(ctx)
    assert "writer_model_choice" not in ctx.state


def test_the_demo_writer_can_switch_models(demo):
    writer = demo.root_agent.sub_agents[2]
    assert writer.name == "writer"
    assert writer.before_model_callback[0].__name__ == "override"


def test_start_callback_starts_a_second_question_fresh(demo):
    state = {"deadline_at": 1.0, "reading_notes_2": "old notes", "sub_questions": ["old"]}
    ctx = _ctx("new question", state)
    demo.make_start_callback(RunConfig())(ctx)
    assert ctx.state["deadline_at"] > time.time()
    assert ctx.state["reading_notes_2"] == ""
    assert ctx.state["sub_questions"] == ["new question"]


def test_start_callback_handles_a_message_without_text(demo):
    ctx = _ctx(None)
    demo.make_start_callback(RunConfig())(ctx)
    assert ctx.state["question"] == ""


def test_the_demo_pipeline_runs_on_the_real_adk_runner_with_a_fake_model(demo, monkeypatch):
    """The whole demo flow: start callback, branches, Writer and Critic skipped or run."""
    from google.adk.runners import InMemoryRunner

    from tests.fake_llm import FakeLlm

    fake = FakeLlm()
    # Same agents as the demo, but with the fake model instead of the dummy names.
    pipeline = demo.build_pipeline(
        RunConfig(),
        search_tool=demo.make_search_tool(stub_search),
        critic=demo.create_critic_agent(fake),
        models=(fake, fake),
    )
    pipeline.before_agent_callback = demo.make_start_callback(RunConfig())

    async def run():
        runner = InMemoryRunner(agent=pipeline, app_name="demo-test")
        session = await runner.session_service.create_session(
            app_name="demo-test", user_id="u"
        )
        message = types.Content(role="user", parts=[types.Part(text="low-rank matrices")])
        async for _ in runner.run_async(
            user_id="u", session_id=session.id, new_message=message
        ):
            pass
        return await runner.session_service.get_session(
            app_name="demo-test", user_id="u", session_id=session.id
        )

    session = asyncio.run(run())
    assert "2106.09685" in session.state["report_markdown"]
    assert session.state["critic_result"]["approved"] is True
