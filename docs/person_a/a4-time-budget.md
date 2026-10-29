# A4: Time budget and skipping

Status: to do.

Goal: the Planner and the Critic skip themselves when time runs short. The core
always returns a report.

## Planned files

- `agents/deadline.py`: a `Deadline` helper with the time left and a check whether an
  agent should be skipped.
- `agents/skipping.py`: the rules for the Planner (skipped: use the original question)
  and the Critic (skipped: use C's `critic_skipped_result()`, so `verified` stays
  `False`).
- `tests/test_deadline.py` and `tests/test_skipping.py`: tests with an injected clock.

## Depends on

A3.

## Commit

One commit when the stage is done:

```
feat: add time budget and agent skipping
```

## Done when

With a tiny time budget, a run skips both agents and still returns a `Report`.
