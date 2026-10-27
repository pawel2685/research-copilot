import subprocess
import sys

import main
import quality_gate


def test_run_gate_returns_pytest_exit_code(monkeypatch):
    calls = []

    def fake_run(cmd):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 3)

    monkeypatch.setattr(quality_gate.subprocess, "run", fake_run)

    assert quality_gate.run_gate() == 3
    assert calls == [[sys.executable, "-m", "pytest"]]


def test_main_starts_app_when_gate_passes(monkeypatch):
    monkeypatch.setattr(main, "run_gate", lambda: 0)
    monkeypatch.setattr(main, "run_app", lambda: 42)

    assert main.main() == 42


def test_main_blocks_app_when_gate_fails(monkeypatch, capsys):
    monkeypatch.setattr(main, "run_gate", lambda: 1)

    def run_app():
        raise AssertionError("app must not start when the gate fails")

    monkeypatch.setattr(main, "run_app", run_app)

    assert main.main() == 1
    assert "app was not started" in capsys.readouterr().out


def test_run_app_returns_success(capsys):
    assert main.run_app() == 0
    assert "Research Copilot" in capsys.readouterr().out
