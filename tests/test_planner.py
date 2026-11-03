from google.adk.agents import LlmAgent

from agents.planner import create_planner_agent


def test_planner_has_expected_name_model_and_output_key():
    agent = create_planner_agent("test-model")

    assert isinstance(agent, LlmAgent)
    assert agent.name == "planner"
    assert agent.model == "test-model"
    assert agent.output_key == "sub_questions"


def test_planner_instruction_requires_json_array():
    agent = create_planner_agent("test-model")

    assert "valid JSON array" in agent.instruction
    assert "four" in agent.instruction.lower()
    assert "same language" in agent.instruction.lower()


def test_planner_uses_light_model_by_default(monkeypatch):
    monkeypatch.setattr(
        "agents.planner.load_models",
        lambda: ("light-model", "heavy-model"),
    )

    agent = create_planner_agent()

    assert agent.model == "light-model"


def test_planner_does_not_make_api_request_when_created():
    agent = create_planner_agent("test-model")

    assert agent.name == "planner"
    assert agent.output_key == "sub_questions"
