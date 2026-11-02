# A8: Cache and retries, implementation plan

Status: to do. Depends on A6.

## Goal

Protect the free-tier limits and survive temporary errors (`503` high demand, `429`
rate limit) without crashing a run.

## Read first

- `agents/orchestrator.py` and the agent factories (A5, A6)
- The ADK facts in the [index](README.md): `retry_config`, `before_model_callback`,
  `after_model_callback`
- `.gitignore`

## Files to create or change

- `agents/cache.py` (new)
- `agents/retry.py` (new)
- the agent factories and `agents/orchestrator.py` (change, to attach the cache and the
  retries)
- `.gitignore` (add `.cache/`)
- `tests/test_cache.py` and `tests/test_retry.py` (new)

## Instructions

### `agents/cache.py`: disk cache

- A cache directory, `.cache/llm` by default, overridable by the `LLM_CACHE_DIR`
  environment variable.
- A key function: the SHA-256 of the model name plus the serialised request contents.
- `before_model_callback`: on a hit, return the stored response so the model is not
  called. On a miss, return `None`.
- `after_model_callback`: store the response under the key, one JSON file per key.
- Switch: `LLM_CACHE=off` disables both callbacks. This matters, see below.

The exact signatures of the two model callbacks are not verified yet. Inspect them in
the project `.venv` before writing the code (the same way `before_agent_callback` was
checked) and adapt.

**Caching and measurements.** C's evaluation measures latency and token use. Cached
answers return instantly and cost no tokens, which would distort those numbers. Use the
cache while developing and repeating runs, and set `LLM_CACHE=off` for measured
experiment runs. Write this into the stage documentation and the main `README.md`.

### `agents/retry.py`: retries

ADK's `LlmAgent` has a `retry_config` field (`RetryConfig` with `max_attempts`,
`initial_delay`, `max_delay`, `backoff_factor`, `jitter`, `exceptions`). Start with it:

1. Build one shared `RetryConfig` in `agents/retry.py`: a few attempts, growing delay
   with jitter, `exceptions` covering Google's server errors (`503`).
2. Attach it to every `LlmAgent` the factories create.
3. Check with a small fake that the retry really applies to model calls in this ADK
   version. If it does not, or if it cannot separate `429` from other client errors
   such as `404`, write a small own wrapper instead, retrying only `503` and `429`
   and never `404`, `400` or `403`.

A `404` ("model no longer available") must never be retried: it will not go away.

## Tests

- `tests/test_cache.py` (use `tmp_path`): a miss then a hit returns the stored
  response; different prompts or models give different keys; `LLM_CACHE=off` disables
  storing and reading; a corrupted cache file is treated as a miss.
- `tests/test_retry.py`: a function that fails twice with a `503`-like error and then
  succeeds is retried and returns; a `404`-like error is raised at once without a
  retry; after the maximum attempts the last error is raised. Replace the sleep with a
  no-op so tests run fast.

## When the stage is finished

Follow "When a stage is finished" in the [index](README.md). Add a short "Cache and
retries" section to the main `README.md`.

## Commit message

```
feat: add response cache and retries
```
