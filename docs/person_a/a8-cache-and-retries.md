# A8: Cache and retries

Status: done.

Goal: protect the free-tier limits and survive temporary errors (`503` high demand,
`429` rate limit) without crashing a run.

## Findings (google-adk 2.13.0)

Checked in the installed packages:

- **`LlmAgent` has no `retry_config`.** The `RetryConfig` in the package is for
  workflow nodes. The implementation index listed it as an `LlmAgent` field, which was
  wrong, and the index is corrected.
- **The `Gemini` model class has `retry_options`** (`google.genai.types.HttpRetryOptions`:
  `attempts`, `initial_delay`, `max_delay`, `exp_base`, `jitter`, `http_status_codes`).
  The genai SDK does the retrying inside the model call. It retries only the listed
  status codes, waits with a growing pause and jitter, and raises the last error when
  the attempts are used up. So no own wrapper was needed.
- **Model callbacks.** `before_model_callback(callback_context, llm_request)` returns
  an `LlmResponse` (the model call is skipped) or `None`.
  `after_model_callback(callback_context, llm_response)` gets only the response, not
  the request. Both accept a list.
- **`LlmAgent.model` can be a string or a model object.** A `Gemini` object with
  retries can replace the name.

## Files

### `agents/retry.py` (new)

- **`RETRYABLE_STATUS_CODES = (429, 503)`.** `429` is the rate limit, `503` the
  temporary overload. Never `404` (the model is not available for the account and does
  not come back), `400` or `403`.
- **`RETRY_OPTIONS`.** An `HttpRetryOptions` with 4 attempts, a first pause of 2 s that
  doubles, a maximum pause of 30 s and jitter, for those status codes only. Example
  values, to tune after the first real runs. The pauses count against the time budget,
  and the skip callbacks only look at the deadline when an agent starts.
- **`make_model(model)`.** A model name becomes `Gemini(model=name,
  retry_options=RETRY_OPTIONS)`. A model object (a fake in tests) and an empty name
  are returned unchanged.

### `agents/cache.py` (new)

- **Switches.** `LLM_CACHE=off` disables reading and writing (read at every call, on
  by default). `LLM_CACHE_DIR` sets the directory, `.cache/llm` by default.
- **`cache_key(llm_request)`.** The SHA-256 of the model name, the contents of the
  request and its config (system instruction, tools, output schema).
- **`before_model(ctx, llm_request)`.** On a hit returns the stored `LlmResponse`, so
  the model is not called. On a miss it remembers the key and returns `None`.
- **`after_model(ctx, llm_response)`.** Stores the response of a miss, one JSON file per
  key, written to a temporary file first and then renamed. Responses with no content,
  partial responses and error responses are not stored. It never changes the response.
  A directory that cannot be written is ignored: the cache is then only slower.
- **Pending keys.** `after_model` does not get the request, so the key is kept in a
  dictionary under (invocation id, agent name). Parallel branches have different agent
  names, so they do not mix up.
- **Corrupted files.** An unreadable file, bad JSON or a file of the wrong shape is a
  miss.
- **`with_cache(agent)`.** A copy of the agent with the two callbacks put in front of
  the ones it already has. The original agent is not modified.

### `agents/orchestrator.py` (changed)

- **`harden_agent(agent)`.** A copy of the agent with its model name replaced by
  `make_model(...)` and the cache attached. It is applied to the Searchers, the
  Readers, the Writer, and also to B's Planner and C's Critic, because they are copied
  anyway and their code is not edited.

### `agents/runner.py` (changed)

The revision Writer is hardened as well.

### `.gitignore` (changed)

Added `.cache/`.

### `README.md` (changed)

A "Cache and retries" section.

### `tests/conftest.py` (new)

An automatic fixture that sets `LLM_CACHE=off` for every test, so no test reads or
writes cache files. The cache tests switch it on in a temporary directory.

### `tests/test_cache.py` (new)

Twenty tests with `tmp_path`:

- A miss then a hit returns the stored response, with one file per key.
- Different prompts, models, system instructions, tools and output schemas give
  different keys.
- `LLM_CACHE=off` disables reading and storing. The default is on, and the default
  directory is `.cache/llm`.
- A corrupted file and a file of the wrong shape are a miss.
- Responses with no content, partial ones and error ones are not stored.
- Binary parts (the thought signature) survive the round trip.
- A hit registers nothing and is not stored again. Parallel agents do not mix up their
  requests. An unwritable directory does not break a run.
- `with_cache` puts the callbacks first and keeps the others.
- On the real ADK runner with a fake model: a repeated run does not call the model at
  all and gives the same report. With the switch off, every run calls it.

### `tests/test_retry.py` (new)

The tests run the retry policy that the SDK builds from our options, with the sleep
replaced by a no-op:

- `429` and `503` are retried until the call succeeds, also mixed.
- The pause grows and stays below the maximum.
- `404`, `400`, `403` and `401` are raised at once, with no retry. A `404` after a
  `503` ends the retries.
- After the maximum attempts the last error is raised.
- Only `429` and `503` are listed.
- `make_model` gives a `Gemini` model with the options, the options reach the SDK
  client, and a model object or an empty name is left alone.

The tests use `retry_args` from `google.genai._api_client`, a private function, and
`tenacity` (a dependency of google-genai). If a new SDK version moves them, these
tests need an update.

### `tests/test_orchestrator.py` (changed)

The model assertions now compare the model name (`agent.model.model`), because the model
is a `Gemini` object. New tests: every agent has the retry options and the cache
callbacks, the originals are not modified, a model object is kept, and existing model
callbacks stay after the cache.

## Cache and measurements

C's evaluation measures latency and token use. A cached answer comes back at once and
costs no tokens, which would distort those numbers. Use the cache while developing and
repeating runs, and set `LLM_CACHE=off` for measured experiment runs (A9).

## Not checked

Retries and the cache were tested with fakes and the SDK's own retry policy, not with a
real `503` or a real response from Gemini. Whether a real response with a thought
signature survives the cache can be checked with the manual run: run the same question
twice and see that the second run is fast.

## Commit

```
feat: add response cache and retries
```
