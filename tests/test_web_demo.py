import asyncio
from unittest.mock import Mock

import pytest
from google.adk.tools import FunctionTool

from retrieval import Paper, save_corpus
from web_agents.research_demo import agent, tools
import run_web


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "DEFAULT_DATA", tmp_path)
    monkeypatch.setattr(tools, "_cached", None)
    monkeypatch.setattr(tools, "_signature", None)
    save_corpus([Paper("1v1", "Quantization", "Model compression", [], "2024", "https://arxiv.org/abs/1v1")], tmp_path / "corpus.jsonl")
    return tmp_path


def test_adk_tool_schema_and_real_bm25(corpus):
    declaration = FunctionTool(tools.search_papers)._get_declaration()
    assert declaration.name == "search_papers"
    schema = declaration.parameters_json_schema
    if schema is None:
        schema = declaration.parameters.model_dump()
    assert "query" in schema["properties"]
    assert agent.root_agent.tools == [tools.search_papers]
    result = asyncio.run(tools.search_papers("quantization", "bm25", 3))
    assert result["status"] == "success"
    assert result["results"][0]["arxiv_id"] == "1v1"
    previous = tools._cached
    assert tools._search("absent", "bm25", 1)["count"] == 0
    assert tools._cached is previous
    save_corpus([], corpus / "corpus.jsonl")
    assert tools._search("quantization", "bm25", 1)["corpus_size"] == 0
    assert tools._cached is not previous


def test_tool_errors(corpus, monkeypatch):
    for args in [(" ", "bm25", 1), ("x", "invalid", 1), ("x", "bm25", 11)]:
        assert tools._search(*args)["status"] == "error"
    (corpus / "corpus.jsonl").unlink()
    assert "Corpus missing" in tools._search("x", "bm25", 1)["message"]
    save_corpus([], corpus / "corpus.jsonl")
    monkeypatch.setattr(tools, "load_corpus", Mock(side_effect=RuntimeError("test failure")))
    result = tools._search("x", "vector", 1)
    assert result["status"] == "error"
    assert "test failure" not in result["message"]


def test_launcher(monkeypatch, tmp_path):
    monkeypatch.setattr(run_web, "__file__", str(tmp_path / "run_web.py"))
    monkeypatch.setattr(run_web.os, "chdir", Mock())
    monkeypatch.setattr(run_web, "load_dotenv", Mock())
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert run_web.main() == 1
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_LIGHT", raising=False)
    assert run_web.main() == 1
    monkeypatch.setenv("MODEL_LIGHT", "test-model")
    assert run_web.main() == 1
    save_corpus([], tmp_path / "data" / "corpus.jsonl")
    monkeypatch.setattr(run_web, "run_gate", lambda: 1)
    assert run_web.main() == 1
    monkeypatch.setattr(run_web, "run_gate", lambda: 0)
    launch = Mock(return_value=0)
    monkeypatch.setattr(run_web.subprocess, "call", launch)
    assert run_web.main() == 0
    assert "web_agents" in launch.call_args.args[0]
