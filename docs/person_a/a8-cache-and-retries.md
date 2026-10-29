# A8: Cache and retries

Status: to do.

Goal: protect the free-tier limits and survive temporary errors.

## Planned files

- `agents/cache.py`: a disk cache of model responses, keyed by a hash of the prompt.
- `agents/retry.py`: retries for `503` and `429` with a growing pause.
- `tests/test_cache.py` and `tests/test_retry.py`: tests of both.

## Depends on

A5.

## Commit

One commit when the stage is done:

```
feat: add response cache and retries
```

## Done when

Repeating the same call does not hit the API again, and a `503` does not crash a run.
