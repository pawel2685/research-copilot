# Implementation plans for person A

One file per stage. Each file says what to implement, in which files, step by step,
which tests to write, and what to do when the stage is finished. The stage files in
[`docs/person_a/`](../README.md) are the documentation of what was built. These files
are the instructions for building it.

## How to use

In VS Code, point the assistant at one plan and name the stage:

```
Implement step A3 following docs/person_a/implementation/a3-baseline-pipeline.md
```

Implement one stage at a time, in order. Do not start a stage before the stages it
depends on are done (see the table below).

## Rules for every stage

- Follow [CONTRIBUTING.md](../../CONTRIBUTING.md). Everything is written in English:
  code, comments, docstrings, commit messages and docs.
- Write tests for all new code in `tests/`, one test file per new module. Automated
  tests never call the real Gemini API: use fakes and `monkeypatch`.
- `python -m pytest` must pass with total coverage of at least 80% (`fail_under` in
  `pyproject.toml`). New code without tests lowers the coverage.
- Do not edit other people's code: `retrieval/` and the Planner (B); `context/`,
  `evals/` and `agents/critic.py` (C). Use them through their public functions.
- Do not change `contracts.py` without approval of the whole team, and never inside a
  stage commit. If a stage needs a contract change, stop and ask.
- Never commit secrets. Keys live only in the local `.env`.
- The assistant never runs git commands. The user does.

## When a stage is finished

1. Run `python -m pytest`. Everything must be green.
2. Rewrite the stage file in `docs/person_a/` (for example `a3-baseline-pipeline.md`)
   as documentation: every file that was added or changed, described from top to
   bottom, in the same style as `a0-setup.md` and `a1-contracts.md`. Set its status
   to `done`.
3. Set the stage to `done` in the table in `docs/person_a/README.md`.
4. Print the commit message from the plan, for the user to commit. One commit per
   stage, containing the code, the tests and the documentation.

Push and the pull request happen once, after the last stage.

## Stages

| Stage | Plan | Depends on |
|-------|------|------------|
| A2 | [Stubs](a2-stubs.md) | A1 |
| A3 | [Baseline pipeline](a3-baseline-pipeline.md) | A2 |
| A4 | [Time budget and skipping](a4-time-budget.md) | A3 |
| A5 | [ADK agents](a5-adk-agents.md) | A3 |
| A6 | [ADK orchestration](a6-orchestration.md) | A4, A5 |
| A7 | [Integration with B and C](a7-integration.md) | A6, B's retrieval |
| A8 | [Cache and retries](a8-cache-and-retries.md) | A6 |
| A9 | [Evaluation hand-off](a9-evaluation-handoff.md) | A7, A8 |
| A10 | [Demo and cleanup](a10-demo-and-cleanup.md) | A9 |

A0 (setup) and A1 (contracts) are done.

## ADK facts checked in this repo (google-adk 2.13.0)

These were checked by inspecting the package in the project `.venv`:

- `Runner(app_name=..., agent=..., session_service=...)`: keyword-only arguments.
  `runner.run_async(user_id=..., session_id=..., new_message=...)` is an async
  generator of events.
- `await InMemorySessionService().create_session(app_name=..., user_id=...,
  session_id=..., state={...})`: it is a coroutine and takes an initial `state`.
- `before_agent_callback` receives a `google.adk.agents.context.Context` (it has
  `state`) and returns an optional `google.genai.types.Content`. When the returned
  content is truthy, the agent run is skipped.
- `LlmAgent` has the fields `name`, `model`, `instruction`, `tools` (plain functions
  are accepted), `output_key`, `output_schema`, `before_agent_callback`,
  `before_model_callback`, `after_model_callback`, `retry_config`, `timeout` and
  `sub_agents`.
- `SequentialAgent` and `ParallelAgent` take `name` and `sub_agents`.
- `RetryConfig(max_attempts, initial_delay, max_delay, backoff_factor, jitter,
  exceptions)`.

Not checked yet. Verify with a small manual run before relying on it:

- `{key}` placeholders in `instruction` are filled from session state (and `{key?}`
  is optional).
- The `get_session` signature and the shape of `Event.usage_metadata`.
- The exact signature of `before_model_callback` and `after_model_callback`.
