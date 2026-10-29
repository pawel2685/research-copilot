import pytest
from google.adk.agents import LlmAgent

from agents import config
from agents.reader import create_reader_agent
from agents.searcher import create_searcher_agent
from agents.tools import make_search_tool
from agents.writer import create_writer_agent
from stubs.search import search


@pytest.fixture
def models(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", lambda: False)
    monkeypatch.setenv("MODEL_LIGHT", "light-model")
    monkeypatch.setenv("MODEL_HEAVY", "heavy-model")


def _tool():
    return make_search_tool(search)


def test_searcher_has_name_model_output_key_and_one_tool():
    agent = create_searcher_agent(_tool(), "m")
    assert isinstance(agent, LlmAgent)
    assert (agent.name, agent.model, agent.output_key) == ("searcher", "m", "search_results")
    assert len(agent.tools) == 1


def test_reader_has_name_model_and_output_key():
    agent = create_reader_agent("m")
    assert isinstance(agent, LlmAgent)
    assert (agent.name, agent.model, agent.output_key) == ("reader", "m", "reading_notes")
    assert "{search_results}" in agent.instruction


def test_writer_has_name_model_and_output_key():
    agent = create_writer_agent("m")
    assert isinstance(agent, LlmAgent)
    assert (agent.name, agent.model, agent.output_key) == ("writer", "m", "report_markdown")
    assert "{reading_notes}" in agent.instruction


def test_default_models_come_from_the_environment(models):
    assert create_searcher_agent(_tool()).model == "light-model"
    assert create_reader_agent().model == "light-model"
    assert create_writer_agent().model == "heavy-model"


def test_explicit_model_wins_over_the_environment(models):
    assert create_writer_agent("explicit").model == "explicit"


def test_missing_environment_raises_without_an_explicit_model(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", lambda: False)
    monkeypatch.delenv("MODEL_LIGHT", raising=False)
    monkeypatch.delenv("MODEL_HEAVY", raising=False)
    with pytest.raises(RuntimeError, match="MODEL_LIGHT"):
        create_reader_agent()
