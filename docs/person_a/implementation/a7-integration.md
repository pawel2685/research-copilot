# A7: Integration with B and C, implementation plan

Status: to do. Depends on A6 and on B's retrieval being merged into `main`.

## Goal

The real modules replace the stand-ins, `answer()` is the one public entry point, and
`python main.py` answers a question.

## Before you start

Pull `main` into `feat/person-a` (the user does this) and check that B's modules
exist: the search function in `retrieval/` and the Planner agent. Their signatures must
match `SearchFn` and the Planner contract agreed in A6. If something is missing, do the
parts that do not depend on it and stop there. Do not write B's code.

## Read first

- B's `retrieval/` (the search function) and the Planner agent
- `agents/runner.py` and `agents/orchestrator.py` (A6)
- `main.py` and `tests/test_main.py`

## Files to create or change

- `agents/pipeline.py` (new): the public API
- `main.py` (change)
- `tests/test_pipeline.py` (new)
- `tests/test_main.py` (extend)

## Instructions

### `agents/pipeline.py`

`answer(question: str, cfg: RunConfig | None = None) -> Report` runs the ADK pipeline
with `asyncio.run(run_pipeline(...))` and converts the result into a `Report`:

- `question`: the input question
- `markdown`: the final report text
- `sources`: the unique `paper_id` values cited in the notes
- `verified`: `is_verified(critic_result)`, so `False` when the Critic was skipped or
  rejected

Wire B's search function, B's Planner agent and C's `create_critic_agent()`. When a
switch in `cfg` is off, that agent is left out (A6 already handles it).

### `main.py`

`run_app()` reads the question from the command line (`python main.py "<question>"`),
calls `answer()`, and prints the Markdown report, then `Verified: yes` or
`Verified: no`. With no question it prints a usage line and returns a non-zero code.
Keep the quality gate in `main()` untouched: the app still starts only when the tests
pass.

## Tests

- `tests/test_pipeline.py`: with `run_pipeline` replaced by a fake, `answer()` builds
  the `Report` correctly: sources are unique and in order, `verified` is `True` only
  for an approving Critic, an unverified result when the Critic was skipped.
- `tests/test_main.py`: `run_app()` prints the report for a question (fake `answer`),
  prints a usage message and returns non-zero without a question.

## Manual check (once)

Run `python main.py "What problem does retrieval-augmented generation address?"` with a
real key. Compare the cited sources with `evals/questions.py` (`2005.11401`).

## When the stage is finished

Follow "When a stage is finished" in the [index](README.md). Also update the
"Running the app" section of the main `README.md` with the new command.

## Commit message

```
feat: integrate retrieval, compression and critic
```
