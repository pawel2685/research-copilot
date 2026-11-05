import subprocess
import sys

import pytest

import main
import quality_gate
from contracts import Report


def test_run_gate_returns_pytest_exit_code(monkeypatch):
    calls = []

    def fake_run(cmd):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 3)

    monkeypatch.setattr(quality_gate.subprocess, "run", fake_run)

    assert quality_gate.run_gate() == 3
    assert calls == [[sys.executable, "-m", "pytest"]]


def test_main_answers_the_question_when_gate_passes(monkeypatch):
    asked = []
    monkeypatch.setattr(main, "run_gate", lambda: 0)
    monkeypatch.setattr(main, "run_app", lambda argv: asked.append(argv) or 42)
    monkeypatch.setattr(main, "launch_web", lambda: pytest.fail("no web without a question"))

    assert main.main(["What", "is", "LoRA?"]) == 42
    assert asked == [["What", "is", "LoRA?"]]


@pytest.mark.parametrize("argv", [[], [""], ["  "]])
def test_main_starts_the_web_interface_without_a_question(monkeypatch, argv):
    monkeypatch.setattr(main, "run_gate", lambda: 0)
    monkeypatch.setattr(main, "launch_web", lambda: 7)

    def run_app(argv):
        raise AssertionError("no question to answer")

    monkeypatch.setattr(main, "run_app", run_app)

    assert main.main(argv) == 7


def test_main_reads_the_command_line_by_default(monkeypatch):
    monkeypatch.setattr(main, "run_gate", lambda: 0)
    monkeypatch.setattr(main, "run_app", lambda argv: argv)
    monkeypatch.setattr(sys, "argv", ["main.py", "from argv"])

    assert main.main() == ["from argv"]


def test_main_blocks_the_app_when_gate_fails(monkeypatch, capsys):
    monkeypatch.setattr(main, "run_gate", lambda: 1)

    def refuse(*args):
        raise AssertionError("nothing must start when the gate fails")

    monkeypatch.setattr(main, "run_app", refuse)
    monkeypatch.setattr(main, "launch_web", refuse)

    assert main.main(["question"]) == 1
    assert main.main([]) == 1
    assert "app was not started" in capsys.readouterr().out


def test_run_app_prints_the_report_and_verified_yes(monkeypatch, capsys):
    asked = []

    def fake_answer(question):
        asked.append(question)
        return Report(question=question, markdown="# Report", sources=["1"], verified=True)

    monkeypatch.setattr(main, "answer", fake_answer)

    assert main.run_app(["What", "is", "LoRA?"]) == 0
    assert asked == ["What is LoRA?"]
    out = capsys.readouterr().out
    assert "# Report" in out
    assert out.strip().endswith("Verified: yes")


def test_run_app_prints_verified_no(monkeypatch, capsys):
    monkeypatch.setattr(
        main, "answer", lambda question: Report(question=question, markdown="# Report")
    )

    assert main.run_app(["question"]) == 0
    assert capsys.readouterr().out.strip().endswith("Verified: no")


def test_run_app_reads_the_question_from_the_command_line(monkeypatch):
    asked = []
    monkeypatch.setattr(
        main, "answer", lambda question: asked.append(question) or Report(question=question, markdown="")
    )
    monkeypatch.setattr(sys, "argv", ["main.py", "from argv"])

    assert main.run_app() == 0
    assert asked == ["from argv"]


@pytest.mark.parametrize("argv", [[], [""], ["  "]])
def test_run_app_without_a_question_prints_usage_and_fails(monkeypatch, capsys, argv):
    def fail(question):
        raise AssertionError("answer must not be called without a question")

    monkeypatch.setattr(main, "answer", fail)

    assert main.run_app(argv) != 0
    assert "Usage" in capsys.readouterr().out


@pytest.mark.parametrize(
    "code, expected",
    [
        (503, "overloaded"),
        (429, "limit"),
        (404, "MODEL_LIGHT"),
        (400, "answered 400"),
    ],
)
def test_run_app_explains_the_errors_of_the_model_api(monkeypatch, capsys, code, expected):
    from google.genai import errors

    cls = errors.ServerError if code >= 500 else errors.ClientError

    def broken(question):
        raise cls(code, {"error": {"code": code, "message": "the details", "status": "X"}})

    monkeypatch.setattr(main, "answer", broken)

    assert main.run_app(["question"]) == 1
    out = capsys.readouterr().out
    assert out.startswith("Error: ")
    assert expected in out
    assert "Traceback" not in out


def test_run_app_reports_a_configuration_error(monkeypatch, capsys):
    def broken(question):
        raise RuntimeError("MODEL_LIGHT is missing.")

    monkeypatch.setattr(main, "answer", broken)

    assert main.run_app(["question"]) == 1
    assert "MODEL_LIGHT is missing." in capsys.readouterr().out
