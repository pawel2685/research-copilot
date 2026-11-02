# A4: Time budget and skipping, implementation plan

Status: to do. Depends on A3.

## Goal

The Planner and the Critic skip themselves when time runs short, and can be switched
off in `RunConfig`. The core always returns a report. This is plain Python, so it is
testable without ADK. A6 reuses the same rules inside ADK.

## Read first

- `agents/baseline.py` and `agents/passages.py` (from A3)
- `agents/critic.py` (C): `CriticResult`, `critic_skipped_result(reason)`
- `contracts.py` (`RunConfig.use_planner`, `use_critic`, `time_budget_s`)

## Files to create or change

- `agents/deadline.py` (new)
- `agents/skipping.py` (new)
- `agents/baseline.py` (change)
- `tests/test_deadline.py` (new)
- `tests/test_skipping.py` (new)
- `tests/test_baseline.py` (extend)

## Instructions

### `agents/deadline.py`

A dataclass `Deadline` with an injectable clock, so tests never sleep:

- fields: `at: float` and `clock: Callable[[], float] = time.monotonic`
- `Deadline.after(seconds, clock=time.monotonic)`: builds a deadline `seconds` from now
- `left() -> float`: seconds left (negative when the deadline has passed)
- `should_skip(min_left_s: float) -> bool`: `True` when `left()` is below `min_left_s`

### `agents/skipping.py`

- Constants `PLANNER_MIN_LEFT_S = 40.0` and `CRITIC_MIN_LEFT_S = 30.0`. They are
  example values (the time an agent needs). Tune them after the first real runs.
- Type aliases (not in `contracts.py`):
  `PlannerFn = Callable[[str], list[str]]` and
  `CriticFn = Callable[[Report, list[Chunk]], CriticResult]`.
- `plan_questions(question, planner_fn, deadline, cfg) -> list[str]`: returns
  `[question]` when `planner_fn` is `None`, when `cfg.use_planner` is `False`, or when
  `deadline.should_skip(PLANNER_MIN_LEFT_S)`. Otherwise returns `planner_fn(question)`,
  falling back to `[question]` when it returns an empty list.
- `critique(report, chunks, critic_fn, deadline, cfg) -> CriticResult`: returns
  `critic_skipped_result(reason)` (from C) when `critic_fn` is `None`, when
  `cfg.use_critic` is `False`, or when `deadline.should_skip(CRITIC_MIN_LEFT_S)`. Give a
  different `reason` text for each case. Otherwise returns `critic_fn(report, chunks)`.
- `is_verified(result: CriticResult) -> bool`: `result.approved is True`.

### `agents/baseline.py`

Extend `answer` with keyword-only arguments `planner_fn: PlannerFn | None = None`,
`critic_fn: CriticFn | None = None` and `deadline: Deadline | None = None`
(default `Deadline.after(cfg.time_budget_s)`):

1. `sub_questions = plan_questions(...)`.
2. Search every sub-question, merge the chunks, remove duplicates (same `paper_id` and
   `text`), keep the highest score first.
3. Compress and build the report as in A3.
4. `result = critique(report, kept_chunks, ...)`, then `report.verified =
   is_verified(result)` (use `model_copy(update=...)`).

## Tests

`tests/test_deadline.py` (fake clock, a list or counter you advance by hand):

- `left()` shrinks as the clock advances and goes negative after the deadline
- `should_skip` is `False` with plenty of time and `True` below the threshold
- `Deadline.after` uses the clock it is given

`tests/test_skipping.py`:

- `plan_questions`: skipped for `None`, for `use_planner=False` and for a short
  deadline; the planner is not called when skipped (the fake raises if called); an
  empty planner result falls back to `[question]`; a normal call returns the planner's
  list
- `critique`: the same three skip cases return a result with `approved is None` and
  `unverified is True`; the critic function is not called when skipped; a normal call
  returns the critic's result
- `is_verified` is `True` only for `approved is True` (not for `False` and not for
  `None`)

`tests/test_baseline.py` (extend):

- a tiny `time_budget_s` skips both agents and still returns a `Report` with
  `verified` equal to `False`
- with a planner, every sub-question is searched and duplicates are removed
- an approving critic gives `verified` equal to `True`; a rejecting one gives `False`

## When the stage is finished

Follow "When a stage is finished" in the [index](README.md). In the documentation,
describe the two new modules, the changes to `agents/baseline.py`, and every test file.

## Commit message

```
feat: add time budget and agent skipping
```
