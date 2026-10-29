# A0: Setup

Status: done.

Goal: a working repository and local environment for the whole team, with a quality
gate that blocks the app when tests fail.

## Repository settings (GitHub)

- `main` is protected by a ruleset: no direct pushes, no force pushes, no deletion.
- Every change goes through a pull request, and a pull request needs one approval.
  Approvals are dismissed when new commits are pushed, and the author of the last
  push cannot approve it.

## Files

### `.gitignore`

The standard Python template. It keeps local and generated files out of the repo:
`__pycache__/`, `.venv`, `.env` (the secrets file), and the coverage output
(`htmlcov/`, `.coverage`).

### `requirements.txt`

Dependencies, one per line:

- `google-adk`: the agent framework.
- `pydantic`: data models (used by the contracts and the Critic's structured result).
- `pytest` and `pytest-cov`: tests and coverage.
- `python-dotenv`: loads `.env`.
- `matplotlib>=3.9,<4`: charts in the evaluation report.

### `.env.example`

The template of the local `.env` file, with four variables:

- `GOOGLE_GENAI_USE_VERTEXAI=FALSE`: use the Gemini API key, not Vertex AI.
- `GOOGLE_API_KEY`: the placeholder for your own key.
- `MODEL_LIGHT=gemini-3.5-flash-lite`: model for the light agents.
- `MODEL_HEAVY=gemini-3.5-flash`: model for the Writer.

Each person copies it to `.env` and puts their own key in. `.env` is never committed.

### `pyproject.toml`

Configuration for pytest and coverage:

- pytest looks for tests in `tests/` and always runs with coverage, printing missing
  lines and writing an HTML report.
- Coverage measures the whole repo, except `.venv/` and `tests/`.
- The run fails when total coverage is below 80% (`fail_under`).
- Lines marked `pragma: no cover` and the `if __name__ == "__main__":` guard are
  excluded from coverage.

### `quality_gate.py`

One function, `run_gate()`. It runs `python -m pytest` with the current interpreter
and returns its exit code. Zero means the gate passed.

### `main.py`

The entry point of the app, started with `python main.py`.

- `run_app()` prints `Research Copilot: agents are not implemented yet.` and returns 0.
  It is the placeholder that the real pipeline will replace (done in A7: `run_app()`
  now answers the question given on the command line).
- `main()` runs the gate first. If the gate fails, it prints that the app was not
  started and returns 1. If it passes, it returns the result of `run_app()`.
- The `__main__` guard exits with the return value of `main()`.

### `tests/test_main.py`

Four tests of `main.py` and `quality_gate.py`:

- `run_gate()` runs `python -m pytest` and returns its exit code (the subprocess call
  is replaced by a fake).
- `main()` starts the app when the gate passes.
- `main()` does not start the app when the gate fails and prints the reason.
- `run_app()` returns 0 and prints the app name.

### `README.md`

The guide for a new team member, top to bottom: what the project is, requirements,
setup (clone, virtual environment, free Gemini API key, `.env`, a check that the key
works), how to run the app and the tests, the models and how to list them, the
project structure, the team rules and a troubleshooting table of errors we met.

### `docs/CONTRIBUTING.md`

The team rules, top to bottom: everything is written in English; `main` is protected;
branch name prefixes (`feat/`, `fix/`, `docs/`, `chore/`, `test/`); commit messages
with the same prefix; the pull request rules (one approval, stale approvals
dismissed, resolved comments); how to start a branch; no secrets in the repo;
`contracts.py` changes need everyone's approval.

## Commit

```
chore: project setup and readme
```

Delivered in pull request #1.
