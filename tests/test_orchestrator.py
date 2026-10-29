from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent

from agents import cache
from agents.critic import create_critic_agent
from agents.orchestrator import build_pipeline, harden_agent, notes_keys
from agents.retry import RETRY_OPTIONS
from agents.tools import make_search_tool
from contracts import RunConfig
from stubs.search import search
from tests.fake_llm import FakeLlm

MODELS = ("light-model", "heavy-model")


def _model_name(agent):
    return agent.model.model


def _planner():
    return LlmAgent(name="planner", model="m", instruction="plan", output_key="sub_questions")


def _build(cfg=None, **kwargs):
    return build_pipeline(
        cfg or RunConfig(),
        search_tool=make_search_tool(search),
        models=MODELS,
        **kwargs,
    )


def _names(pipeline):
    return [agent.name for agent in pipeline.sub_agents]


def test_pipeline_is_a_sequential_agent():
    assert isinstance(_build(), SequentialAgent)


def test_four_branches_run_in_a_parallel_agent():
    branches = _build().sub_agents[0]
    assert isinstance(branches, ParallelAgent)
    assert [b.name for b in branches.sub_agents] == [f"branch_{n}" for n in range(1, 5)]
    for branch in branches.sub_agents:
        assert isinstance(branch, SequentialAgent)
        assert [a.name[:6] for a in branch.sub_agents] == ["search", "reader"]


def test_branches_have_unique_names_and_output_keys():
    branches = _build().sub_agents[0].sub_agents
    agents = [agent for branch in branches for agent in branch.sub_agents]
    assert len({agent.name for agent in agents}) == 8
    assert len({agent.output_key for agent in agents}) == 8
    assert [b.sub_agents[1].output_key for b in branches] == notes_keys()


def test_branches_have_the_branch_callback_and_use_the_light_model():
    branches = _build().sub_agents[0].sub_agents
    assert all(branch.before_agent_callback is not None for branch in branches)
    assert all(_model_name(a) == "light-model" for b in branches for a in b.sub_agents)


def test_writer_uses_the_heavy_model_and_reads_all_notes_as_optional():
    writer = _build().sub_agents[-1]
    assert (writer.name, _model_name(writer)) == ("writer", "heavy-model")
    for key in notes_keys():
        assert f"{{{key}?}}" in writer.instruction


def test_without_optional_agents_the_flow_is_branches_and_writer():
    assert _names(_build()) == ["search_branches", "writer"]


def test_all_agents_in_order():
    pipeline = _build(planner=_planner(), critic=create_critic_agent("m"))
    assert _names(pipeline) == ["planner", "search_branches", "writer", "critic"]


def test_planner_is_absent_when_use_planner_is_false():
    pipeline = _build(RunConfig(use_planner=False), planner=_planner())
    assert "planner" not in _names(pipeline)


def test_critic_is_absent_when_use_critic_is_false():
    pipeline = _build(RunConfig(use_critic=False), critic=create_critic_agent("m"))
    assert "critic" not in _names(pipeline)


def test_optional_agents_have_a_skip_callback_and_the_originals_are_untouched():
    planner, critic = _planner(), create_critic_agent("m")
    pipeline = _build(planner=planner, critic=critic)
    for agent in (pipeline.sub_agents[0], pipeline.sub_agents[-1]):
        assert len(agent.before_agent_callback) == 1
    assert planner.before_agent_callback is None
    assert critic.before_agent_callback is None


def test_existing_callbacks_of_an_optional_agent_are_kept():
    def mine(ctx):
        return None

    planner = _planner()
    planner.before_agent_callback = mine
    callbacks = _build(planner=planner).sub_agents[0].before_agent_callback
    assert len(callbacks) == 2 and callbacks[1] is mine


def test_existing_callback_list_of_an_optional_agent_is_kept():
    def mine(ctx):
        return None

    planner = _planner()
    planner.before_agent_callback = [mine]
    callbacks = _build(planner=planner).sub_agents[0].before_agent_callback
    assert len(callbacks) == 2 and callbacks[1] is mine


def test_models_come_from_the_environment_when_not_given(monkeypatch):
    from agents import config

    monkeypatch.setattr(config, "load_dotenv", lambda: False)
    monkeypatch.setenv("MODEL_LIGHT", "env-light")
    monkeypatch.setenv("MODEL_HEAVY", "env-heavy")
    pipeline = build_pipeline(RunConfig(), search_tool=make_search_tool(search))
    assert _model_name(pipeline.sub_agents[-1]) == "env-heavy"
    assert _model_name(pipeline.sub_agents[0].sub_agents[0].sub_agents[0]) == "env-light"


def _all_llm_agents(pipeline):
    agents = []
    for step in pipeline.sub_agents:
        if isinstance(step, LlmAgent):
            agents.append(step)
        else:
            agents += [a for branch in step.sub_agents for a in branch.sub_agents]
    return agents


def test_every_agent_has_retries_and_the_cache():
    pipeline = _build(planner=_planner(), critic=create_critic_agent("m"))
    agents = _all_llm_agents(pipeline)
    assert len(agents) == 11  # planner, 4 x (searcher, reader), writer, critic
    for agent in agents:
        assert agent.model.retry_options == RETRY_OPTIONS
        assert agent.before_model_callback[0] is cache.before_model
        assert agent.after_model_callback[0] is cache.after_model


def test_the_original_agent_is_not_modified():
    planner = LlmAgent(name="planner", model="plain-name", instruction="x")
    _build(planner=planner)
    assert planner.model == "plain-name"
    assert planner.before_model_callback is None


def test_a_model_object_is_kept():
    fake = FakeLlm()
    assert harden_agent(LlmAgent(name="a", model=fake, instruction="x")).model is fake


def test_existing_model_callbacks_are_kept_after_the_cache():
    def mine(ctx, request):
        return None

    agent = LlmAgent(name="a", model="m", instruction="x", before_model_callback=mine)
    hardened = harden_agent(agent)
    assert hardened.before_model_callback == [cache.before_model, mine]
