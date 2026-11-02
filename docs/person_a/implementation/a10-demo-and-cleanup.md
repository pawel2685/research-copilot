# A10: Demo and cleanup, implementation plan

Status: to do. Depends on A9.

## Goal

A demo for the presentation and tidy documentation, so a new team member can follow the
README and run everything.

## Read first

- `agents/orchestrator.py` (A6) and `agents/pipeline.py` (A7)
- The main `README.md` and everything in `docs/`

## Files to create or change

- `demo/research_copilot/__init__.py` (new)
- `demo/research_copilot/agent.py` (new)
- `tests/test_demo.py` (new)
- `README.md` (change)
- `docs/` (cleanup)

## Instructions

### The demo for `adk web`

`adk web` takes a folder that contains agent packages. Each package exposes a
`root_agent`.

- `demo/research_copilot/__init__.py`: `from . import agent`.
- `demo/research_copilot/agent.py`: loads the repo-root `.env`
  (`load_dotenv(Path(__file__).resolve().parents[2] / ".env")`), builds the pipeline
  with `build_pipeline(RunConfig(), ...)` and the real search, Planner and Critic, and
  assigns it to `root_agent`.
- Run it from the repository root with `adk web demo`, then pick `research_copilot` in
  the browser. Check the exact command in the ADK documentation for this version.

### Cleanup

- Update the main `README.md`: the final structure, how to run `python main.py` and
  `adk web demo`, the cache and the experiments. Remove the "agents are not implemented
  yet" status line.
- Remove leftovers from `docs/`, for example the exported
  `docs/Research Copilot (EN).html`. The user removes tracked files with git.
- Check that every stage file in `docs/person_a/` describes what was actually built and
  that the status table in `docs/person_a/README.md` is correct.

## Tests

- `tests/test_demo.py`: importing `demo.research_copilot.agent` gives a `root_agent`
  built without any network call (set a dummy model name through the environment so
  the test does not need a real `.env`).

## When the stage is finished

Follow "When a stage is finished" in the [index](README.md). After this stage, the
branch is complete: the user pushes `feat/person-a` and opens the pull request.

## Commit message

```
docs: finish demo and documentation
```
