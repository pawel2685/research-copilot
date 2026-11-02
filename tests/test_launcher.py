import subprocess
import sys

import pytest

import launcher


@pytest.fixture
def good_env(monkeypatch):
    """A complete configuration. The real `.env` is not read."""
    monkeypatch.setattr(launcher, "load_dotenv", lambda path: None)
    monkeypatch.setenv("GOOGLE_API_KEY", "a-key")
    monkeypatch.setenv("MODEL_LIGHT", "light")
    monkeypatch.setenv("MODEL_HEAVY", "heavy")


@pytest.fixture
def commands(monkeypatch):
    """Records the commands that would run, with a configurable exit code."""

    class Recorder:
        def __init__(self):
            self.run = []
            self.call = []
            self.code = 0

    recorder = Recorder()

    def fake_run(command, cwd=None):
        recorder.run.append(command)
        return subprocess.CompletedProcess(command, recorder.code)

    def fake_call(command, cwd=None):
        recorder.call.append(command)
        return recorder.code

    monkeypatch.setattr(launcher.subprocess, "run", fake_run)
    monkeypatch.setattr(launcher.subprocess, "call", fake_call)
    return recorder


def test_a_complete_env_has_no_problems(good_env):
    assert launcher.config_problems() == []


def test_every_missing_setting_is_named(monkeypatch):
    monkeypatch.setattr(launcher, "load_dotenv", lambda path: None)
    for name in ("GOOGLE_API_KEY", "MODEL_LIGHT", "MODEL_HEAVY"):
        monkeypatch.delenv(name, raising=False)

    problems = launcher.config_problems()

    assert len(problems) == 3
    assert any("GOOGLE_API_KEY" in p for p in problems)
    assert any("MODEL_LIGHT" in p for p in problems)
    assert any("MODEL_HEAVY" in p for p in problems)


def test_the_placeholder_key_counts_as_missing(good_env, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "your-api-key-here")

    assert launcher.config_problems() == ["GOOGLE_API_KEY is missing in .env"]


def test_nothing_is_downloaded_when_the_corpus_and_the_index_exist(tmp_path, commands):
    (tmp_path / "corpus.jsonl").write_text("{}\n")
    (tmp_path / "chroma").mkdir()

    assert launcher.ensure_corpus(tmp_path) == 0
    assert commands.run == []


def test_a_missing_corpus_is_fetched_and_indexed(tmp_path, commands, capsys):
    assert launcher.ensure_corpus(tmp_path) == 0

    fetch, index = commands.run
    assert fetch[:3] == [sys.executable, "-m", "retrieval"]
    assert fetch[3:5] == ["--data-dir", str(tmp_path)]
    assert fetch[5] == "fetch"
    # The query is one argument, so no shell quoting can break it.
    assert fetch[fetch.index("--query") + 1] == launcher.CORPUS_QUERY
    assert index[5:] == ["index"]
    assert "corpus is missing" in capsys.readouterr().out


def test_only_the_index_is_built_when_the_corpus_exists(tmp_path, commands):
    (tmp_path / "corpus.jsonl").write_text("{}\n")

    assert launcher.ensure_corpus(tmp_path) == 0
    assert [command[5] for command in commands.run] == ["index"]


def test_a_failed_fetch_stops_before_the_index(tmp_path, commands):
    commands.code = 2

    assert launcher.ensure_corpus(tmp_path) == 1
    assert len(commands.run) == 1


def test_a_failed_index_is_reported(tmp_path, commands):
    (tmp_path / "corpus.jsonl").write_text("{}\n")
    commands.code = 2

    assert launcher.ensure_corpus(tmp_path) == 1


def test_the_corpus_query_names_the_five_evaluation_papers():
    from evals.questions import EVALUATION_QUESTIONS

    for question in EVALUATION_QUESTIONS:
        assert question.reference_title.split(":")[0] in launcher.CORPUS_QUERY


def test_launch_web_stops_on_a_bad_env(monkeypatch, capsys, commands):
    monkeypatch.setattr(launcher, "config_problems", lambda: ["MODEL_LIGHT is missing in .env"])

    assert launcher.launch_web() == 1
    out = capsys.readouterr().out
    assert "MODEL_LIGHT is missing" in out
    assert "README" in out
    assert commands.call == []


def test_launch_web_stops_when_the_corpus_cannot_be_prepared(monkeypatch, capsys, commands):
    monkeypatch.setattr(launcher, "config_problems", lambda: [])
    monkeypatch.setattr(launcher, "ensure_corpus", lambda: 1)

    assert launcher.launch_web() == 1
    assert "corpus could not be prepared" in capsys.readouterr().out
    assert commands.call == []


def test_launch_web_serves_the_demo(monkeypatch, capsys, commands):
    monkeypatch.setattr(launcher, "config_problems", lambda: [])
    monkeypatch.setattr(launcher, "ensure_corpus", lambda: 0)
    commands.code = 5

    assert launcher.launch_web() == 5

    (command,) = commands.call
    assert command[:5] == [sys.executable, "-m", "google.adk.cli", "web", "--host"]
    assert command[-1] == "demo"
    assert "--no-reload" in command
    assert "http://127.0.0.1:8000" in capsys.readouterr().out


def test_ctrl_c_stops_the_server_cleanly(monkeypatch):
    monkeypatch.setattr(launcher, "config_problems", lambda: [])
    monkeypatch.setattr(launcher, "ensure_corpus", lambda: 0)

    def interrupted(command, cwd=None):
        raise KeyboardInterrupt

    monkeypatch.setattr(launcher.subprocess, "call", interrupted)

    assert launcher.launch_web() == 0


def test_the_agents_directory_exists():
    assert (launcher.ROOT / launcher.AGENTS_DIR / "research_copilot" / "agent.py").exists()
