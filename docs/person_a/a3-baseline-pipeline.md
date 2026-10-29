# A3: Baseline pipeline without ADK

Status: to do.

Goal: a plain-Python `answer(question, cfg)` that runs end to end on the stub search
and C's real `compress()`. The evaluation harness can call it from day one.

## Planned files

- `agents/baseline.py`: `answer(question, cfg) -> Report`. Searches, compresses the
  passages to `cfg.compress_budget_words`, writes a report from them and returns it.
- `tests/test_baseline.py`: tests of the flow, including a run with compression off.

## Depends on

A2.

## Commit

One commit when the stage is done:

```
feat: add baseline pipeline
```

## Done when

`answer("some question", RunConfig())` returns a `Report` without any network call.
