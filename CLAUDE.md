# Research Copilot

Multi-agent research assistant built with Google ADK (Python 3.12). Given a research
question it finds papers on arXiv, summarises them, checks its own claims and writes a
short report with sources. Five agents: Planner, Searcher, Reader, Writer, Critic. The
Planner and the Critic are skipped when the time budget runs short.

Team of three: A (core and orchestration, this branch `feat/person-a`), B (retrieval and
the Planner), C (compression, the Critic and the evaluation).

## Commands

Run from the repository root with the virtual environment active
(`.venv\Scripts\Activate.ps1` on Windows PowerShell).

- Tests with coverage: `python -m pytest`
- Run the app (runs the tests first): `python main.py`
- Install dependencies: `pip install -r requirements.txt`

## Structure

- `contracts.py`: shared types (`Chunk`, `Report`, `RunConfig`) and function signatures
- `agents/`: ADK agents and the skipping logic (`critic.py` is C's)
- `retrieval/`: search over the paper corpus (B)
- `context/`: context compression (C)
- `evals/`: questions, metrics, reports (C)
- `stubs/`: stand-ins so the team can work in parallel
- `tests/`: one test file per module
- `docs/`: `CONTRIBUTING.md`, and `person_a/` with the stage documentation

## Rules

- Follow `docs/CONTRIBUTING.md`. Everything is in English: code, comments, docstrings,
  commit messages and docs.
- Never run git commands. The user does. When a stage is done, print the commit
  message.
- One commit per stage: code, tests and documentation together.
- Do not edit B's or C's code (`retrieval/`, `context/`, `evals/`, `agents/critic.py`).
  Use their public functions.
- Do not change `contracts.py` without approval of the whole team, and never inside a
  stage commit. If a stage needs a contract change, stop and ask.
- Never commit secrets. Keys live only in the local `.env`. Model names come from
  `MODEL_LIGHT` and `MODEL_HEAVY` in `.env`, never hard-coded.
- Use the free tier only. Never suggest enabling billing.

## Testing

- Every new module gets tests in `tests/`.
- Automated tests never call the Gemini API. Use fakes and `monkeypatch`.
- `python -m pytest` must pass with total coverage of at least 80% (`fail_under` in
  `pyproject.toml`). Untested code lowers coverage and `python main.py` refuses to start.
- Do not weaken a test to make it pass. Fix the code or ask.

## Working on a stage

Plans are in `docs/person_a/implementation/`, one file per stage (A2 to A10). Read the
index there first, then the plan for the requested stage, and implement only that stage.

When the stage is done:

1. Run `python -m pytest` and make it green.
2. Rewrite the stage file in `docs/person_a/` as documentation: every added or changed
   file, described from top to bottom. Set its status to `done`.
3. Set the stage to `done` in the table in `docs/person_a/README.md`.
4. Print the commit message from the plan.

Documentation edits do not need approval. Code edits only when the user asks for them.

## Gotchas

- `context.compression.compress` works on plain texts, counts whitespace-separated words
  (not model tokens) and drops empty chunks, so result indexes do not match input
  indexes. Use `agents/passages.py` (`compress_chunks`) to keep ids and urls.
- `Chunk.paper_id` is an arXiv id such as `2005.11401`. The evaluation metrics compare
  these ids.
- `Report.verified` is `True` only when `CriticResult.approved is True`.
- google-adk 2.13: `before_agent_callback` takes a `google.adk.agents.context.Context`;
  returning truthy `types.Content` skips the agent. `create_session` is async.
  `Runner` takes keyword arguments only. Check anything not listed in
  `docs/person_a/implementation/README.md` in the installed package before relying on it.
- Gemini: `gemini-2.5-*` return `404` for new accounts. A `503` is temporary overload and
  a `429` is a rate limit. Keep the `genai.Client()` in a variable, or the HTTP client
  gets closed.
- Evaluation measures latency and tokens, so the response cache must be off
  (`LLM_CACHE=off`) for measured runs.

## Context hygiene

Start a new session for each stage. State lives in the repo (`docs/person_a/`), not in
the conversation. Point to files and functions explicitly instead of letting the agent
search the whole repo.
