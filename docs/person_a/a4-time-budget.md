# A4: Time budget and skipping

Status: done.

Goal: the Planner and the Critic skip themselves when time runs short, and can be
switched off in `RunConfig`. The core always returns a report. It is plain Python, so
it is testable without ADK. A6 reuses the same rules inside ADK.

## Files

### `agents/deadline.py` (new)

- **`Deadline`.** A dataclass with the fields `at` (the moment the budget ends) and
  `clock` (a function that returns the current time, `time.monotonic` by default). The
  clock can be replaced, so tests never sleep.
- **`Deadline.after(seconds, clock=time.monotonic)`.** Builds a deadline `seconds` from
  now.
- **`left()`.** Seconds left. Negative when the deadline has passed.
- **`should_skip(min_left_s)`.** `True` when `left()` is below `min_left_s`. Exactly
  `min_left_s` seconds left is still enough.

### `agents/skipping.py` (new)

- **Module docstring.** Says that a skipped Planner means the original question is
  used, and a skipped Critic means the report stays unverified.
- **`PLANNER_MIN_LEFT_S = 40.0` and `CRITIC_MIN_LEFT_S = 30.0`.** Example values for the
  time each agent needs. To be tuned after the first real runs.
- **`PlannerFn` and `CriticFn`.** Type aliases for the Planner function
  (`str -> list[str]`) and the Critic function (`Report, list[Chunk] -> CriticResult`).
  They live here, not in `contracts.py`.
- **`plan_questions(question, planner_fn, deadline, cfg)`.** Returns `[question]` when
  `planner_fn` is `None`, when `cfg.use_planner` is `False`, or when less than
  `PLANNER_MIN_LEFT_S` is left. The planner is not called in those cases. Otherwise
  returns the planner's list, or `[question]` when that list is empty.
- **`critique(report, chunks, critic_fn, deadline, cfg)`.** Returns C's
  `critic_skipped_result(reason)` when `critic_fn` is `None`, when `cfg.use_critic` is
  `False`, or when less than `CRITIC_MIN_LEFT_S` is left. Each case has its own reason
  text, and the critic is not called. Otherwise returns `critic_fn(report, chunks)`.
- **`is_verified(result)`.** `True` only when `result.approved is True`, so a rejection
  and a skipped Critic (`approved is None`) both give `False`.

### `agents/baseline.py` (changed)

- **Imports.** `Deadline` and the helpers from `agents/skipping.py`.
- **`merge_chunks(results)` (new).** Flattens the search results of all
  sub-questions, sorts them by score (best first), and drops duplicates, meaning the
  same `paper_id` and `text`. The copy with the highest score is the one kept.
- **`answer(...)`.** Gets three new keyword-only arguments: `planner_fn`, `critic_fn`
  (both `None` by default) and `deadline` (default `Deadline.after(cfg.time_budget_s)`).
  The flow is now:
  1. `plan_questions` gives the sub-questions.
  2. Every sub-question is searched, and `merge_chunks` joins the results.
  3. `compress_chunks` and `build_report` work as in A3.
  4. `critique` checks the report against the kept chunks, and the returned report is a
     copy with `verified` set from `is_verified`.

  Without a planner and a critic the behaviour is the same as in A3.

### `tests/test_deadline.py` (new)

Five tests with a hand-advanced fake clock:

- `left()` shrinks as the clock advances and goes negative after the deadline.
- `should_skip` is `False` with plenty of time and `True` below the threshold.
- `should_skip` is `False` at exactly the threshold.
- `Deadline.after` uses the clock it is given.
- The default clock works: a fresh 60 s deadline has between 0 and 60 s left.

### `tests/test_skipping.py` (new)

Twelve test cases (some parametrized), top to bottom:

- `plan_questions` is skipped without a planner, with `use_planner=False` and with a
  short deadline. The planner fake raises if it is called.
- An empty planner result falls back to `[question]`.
- A normal call returns the planner's list.
- `critique` skipped for the three cases gives `approved is None`, `unverified is True`
  and a message. The critic fake raises if it is called.
- The three skip reasons are different.
- A normal `critique` call returns the critic's result and passes it the report and
  chunks.
- `is_verified` is `True` only for `approved=True`, not for `False` and not for `None`.

### `tests/test_baseline.py` (extended)

Six new tests, after the A3 ones:

- A time budget of `0` skips both agents (their fakes raise if called), and a `Report`
  with `verified` equal to `False` is still returned.
- A given `deadline` wins over `cfg.time_budget_s`.
- With a planner, every sub-question is searched and duplicates are removed.
- An approving critic gives `verified` equal to `True`, and it receives the report and
  the kept chunks.
- A rejecting critic gives `verified` equal to `False`.
- `merge_chunks` keeps the highest-scoring copy first and removes duplicates.

## Commit

```
feat: add time budget and agent skipping
```
