# A5: ADK agents

Status: to do.

Goal: the three core agents as real ADK agents.

## Planned files

- `agents/config.py`: reads `MODEL_LIGHT` and `MODEL_HEAVY` from `.env` and fails
  with a clear message when one is missing.
- `agents/searcher.py`: the Searcher (`LlmAgent`) with the `search` tool.
- `agents/reader.py`: the Reader (`LlmAgent`) that summarises the compressed passages.
- `agents/writer.py`: the Writer (`LlmAgent`) that writes the report with sources.
- `tests/test_agents.py`: tests that each agent is created without a network call.

One real call is checked by hand. Automated tests make no real API calls.

## Depends on

A1 and a working API key.

## Commit

One commit when the stage is done:

```
feat: add core adk agents
```

## Done when

Each agent is created without a network call, and a manual run gives sensible output.
