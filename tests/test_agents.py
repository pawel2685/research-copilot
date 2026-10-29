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


def test_searcher_can_get_its_own_name_output_key_and_question_key():
    agent = create_searcher_agent(
        _tool(), "m", name="searcher_2", output_key="search_results_2", question_key="sub_question_2"
    )
    assert (agent.name, agent.output_key) == ("searcher_2", "search_results_2")
    assert "{sub_question_2}" in agent.instruction


def test_searcher_without_question_key_has_no_placeholder():
    assert "{" not in create_searcher_agent(_tool(), "m").instruction


def test_reader_can_get_its_own_name_and_keys():
    agent = create_reader_agent("m", name="reader_3", input_key="search_results_3", output_key="reading_notes_3")
    assert (agent.name, agent.output_key) == ("reader_3", "reading_notes_3")
    assert "{search_results_3}" in agent.instruction
    assert "{search_results}" not in agent.instruction


def test_writer_reads_several_optional_notes():
    agent = create_writer_agent("m", notes_keys=["a", "b"], optional_notes=True)
    assert "{a?}" in agent.instruction and "{b?}" in agent.instruction
    assert "{draft_report}" not in agent.instruction


def test_revision_writer_gets_the_draft_and_the_corrections():
    agent = create_writer_agent("m", revision=True)
    assert "{draft_report}" in agent.instruction
    assert "{revision_instructions}" in agent.instruction
    assert "{reading_notes}" in agent.instruction
