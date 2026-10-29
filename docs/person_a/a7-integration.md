# A7: Integration with B and C

Status: to do.

Goal: replace the stand-ins with the real modules.

## Planned files

- `agents/orchestrator.py` (changed): uses B's retrieval instead of the stub search,
  and C's `compress()` and Critic.
- `main.py` (changed): `run_app()` calls `answer()` instead of printing the
  placeholder.
- `tests/test_integration.py`: tests of the wired flow.

## Depends on

A6, plus B's retrieval.

## Commit

One commit when the stage is done:

```
feat: integrate retrieval, compression and critic
```

## Done when

`python main.py` answers a real question using the real modules.
