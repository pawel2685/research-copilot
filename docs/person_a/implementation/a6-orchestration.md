# A6: ADK orchestration, implementation plan

Status: to do. Depends on A4 and A5.

## Goal

The agents run as one flow inside ADK, with parallel sub-questions, skipping of the
optional agents, and at most one Critic revision. Plus a runner that executes the flow
and returns the report.

## Read first

- `agents/skipping.py`, `agents/deadline.py` (A4), the agent factories (A5)
- `agents/critic.py` (C): `create_critic_agent`, `CriticResult`
- The ADK facts in the [index](README.md)

## The flow

```
Planner (optional, B) -> [ branch_1 | branch_2 | branch_3 | branch_4 ] -> Writer -> Critic (optional, C)
                          each branch = Searcher -> Reader
```

- `ParallelAgent` needs a fixed list of sub-agents, and the Planner returns 2 to 4
  sub-questions. So the flow has four branches, and a branch skips itself when it has no
  sub-question.
- The revision is not an ADK loop. After the flow, plain Python checks the Critic's
  result. When `approved is False` and there are revision instructions, run the Writer
  once more with those instructions. Never run the Critic again.

## Files to create or change

- `agents/skipping.py` (extend)
- `agents/orchestrator.py` (new)
- `agents/runner.py` (new)
- `tests/test_skip_callbacks.py` (new)
- `tests/test_orchestrator.py` (new)
- `tests/test_runner.py` (new)

## Instructions

### `agents/skipping.py`: callbacks

Both callbacks take a `google.adk.agents.context.Context` and return
`types.Content(...)` to skip the agent, or `None` to let it run.

- `make_deadline_callback(min_left_s)`: reads `ctx.state["deadline_at"]` (a
  `time.time()` value). When `deadline_at - time.time() < min_left_s`, return a short
  `Content` with the text `skipped`. Use it for the Planner (`PLANNER_MIN_LEFT_S`) and
  the Critic (`CRITIC_MIN_LEFT_S`).
- `make_branch_callback(index)`: reads `ctx.state.get("sub_questions")`, normalised by
  `normalize_sub_questions`. When the list has no item at `index`, return a skip
  `Content`. Otherwise store the item in `ctx.state[f"sub_question_{index + 1}"]` and
  return `None`.
- `normalize_sub_questions(value, question) -> list[str]`: accepts `None`, a list of
  strings, a dict with a `questions` list, or a JSON string of either. Returns at most
  four non-empty strings, or `[question]` when nothing usable is given. B's Planner and
  this function must agree on the shape, so confirm it with B.

### `agents/orchestrator.py`

`build_pipeline(cfg, *, search_tool, planner=None, critic=None, models=None) -> SequentialAgent`

1. Build four branches `branch_1` to `branch_4`. Each is a `SequentialAgent` of a
   Searcher and a Reader with unique names and unique output keys
   (`search_results_N`, `reading_notes_N`), and with the branch callback attached.
2. Wrap the branches in a `ParallelAgent`.
3. The Writer reads all the notes. Use optional placeholders for the four notes keys
   (for example `{reading_notes_1?}`).
4. Compose a `SequentialAgent` of: the Planner (only when `cfg.use_planner` and a
   planner is given, with the deadline callback), the `ParallelAgent`, the Writer, and
   the Critic (only when `cfg.use_critic` and a critic is given, with the deadline
   callback).

Searchers use the search tool built with `make_search_tool(...)`, with
`budget_words=cfg.compress_budget_words` and `hybrid=cfg.hybrid`.

### `agents/runner.py`

`async def run_pipeline(question, cfg, *, ...) -> PipelineResult` where `PipelineResult`
is a small dataclass with `report_markdown`, `sub_questions`, `critic_result` and
`state` (the final session state).

1. Create an `InMemorySessionService` and `await` `create_session(app_name=...,
   user_id=..., session_id=..., state={"deadline_at": time.time() +
   cfg.time_budget_s, "sub_questions": [question]})`. The initial `sub_questions` makes
   branch 1 work even when the Planner is skipped.
2. Build the agent with `build_pipeline`, create `Runner(app_name=..., agent=...,
   session_service=...)`, and iterate `runner.run_async(user_id=..., session_id=...,
   new_message=types.Content(role="user", parts=[types.Part(text=question)]))`.
3. Read the final state (`get_session`, signature not verified yet).
4. If the Critic result says `approved is False` and has revision instructions, run
   the Writer once more with those instructions in a second session, and use that
   markdown. Mark the result as unverified, because the revision was not checked.

## Tests

No test calls the API. Use fake `ctx` objects (`types.SimpleNamespace(state={...})`).

- `tests/test_skip_callbacks.py`: the deadline callback skips below the threshold and
  returns `None` above it; the branch callback skips a branch without a sub-question,
  stores the sub-question under `sub_question_N` otherwise; `normalize_sub_questions`
  handles `None`, a list, a dict, a JSON string, more than four items, empty strings
  and garbage.
- `tests/test_orchestrator.py`: the pipeline is a `SequentialAgent`; there are four
  branches inside a `ParallelAgent`; the Planner is absent when `use_planner` is
  `False`; the Critic is absent when `use_critic` is `False`; the optional agents have
  callbacks attached.
- `tests/test_runner.py`: with the ADK `Runner` replaced by a fake, `run_pipeline` puts
  the deadline and `sub_questions` into the initial state, returns the final report,
  and runs the revision exactly once when the Critic rejects.

## Manual check (once)

Run this from the repository root with a real key in `.env`. It is not an automated
test:

```python
import asyncio
from contracts import RunConfig
from agents.runner import run_pipeline

cfg = RunConfig(use_planner=False, use_critic=False)
print(asyncio.run(run_pipeline("What is LoRA?", cfg)))
```

This is also where you confirm the unverified items (state placeholders in
instructions, `get_session`). Write what you found into the stage documentation.

## When the stage is finished

Follow "When a stage is finished" in the [index](README.md).

## Commit message

```
feat: add agent orchestration
```
