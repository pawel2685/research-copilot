# A5: ADK agents, implementation plan

Status: to do. Depends on A3.

## Goal

The three core agents (Searcher, Reader, Writer) as real ADK `LlmAgent` objects,
created without any network call.

## Read first

- `agents/critic.py` (C): the pattern to follow. `create_critic_agent(model=None)`
  reads `MODEL_LIGHT` from `.env` and raises `RuntimeError` when it is missing.
- `agents/passages.py` (A3): `compress_chunks`
- `contracts.py` (`SearchFn`)

## Files to create

- `agents/config.py`
- `agents/tools.py`
- `agents/searcher.py`
- `agents/reader.py`
- `agents/writer.py`
- `tests/test_config.py`
- `tests/test_tools.py`
- `tests/test_agents.py`

## Instructions

### `agents/config.py`

`load_models() -> tuple[str, str]` returns `(MODEL_LIGHT, MODEL_HEAVY)`. Call
`load_dotenv()`, read both variables with `os.getenv`, and raise `RuntimeError` naming
the missing variable (same style as `agents/critic.py`).

### `agents/tools.py`

`make_search_tool(search_fn, *, hybrid=True, budget_words=None, k=8)` returns a plain
function `search_papers(query: str) -> list[dict]` for the Searcher:

- it calls `search_fn(query, k=k, hybrid=hybrid)`, then `compress_chunks(chunks,
  budget_words)`;
- it returns `[{"paper_id": ..., "text": ..., "source_url": ...}, ...]` (JSON-friendly);
- set `search_papers.__name__` and a docstring that tells the model what the tool does
  and what `query` means. ADK builds the tool description from the name, the type
  hints and the docstring.

Compression happens inside the tool, so the Reader only ever sees passages within the
word budget.

### `agents/searcher.py`

`create_searcher_agent(search_tool, model=None) -> LlmAgent`

- `name="searcher"`, model from `MODEL_LIGHT`, `tools=[search_tool]`,
  `output_key="search_results"`.
- Instruction: call the search tool for the question and return the passages as they
  are, with their `paper_id` values. Do not summarise and do not invent passages.

### `agents/reader.py`

`create_reader_agent(model=None) -> LlmAgent`

- `name="reader"`, model from `MODEL_LIGHT`, `output_key="reading_notes"`.
- Instruction: summarise the passages in `{search_results}` as short factual notes.
  Every note ends with the `paper_id` it comes from in square brackets. Use only the
  given passages. If there are none, say so.

### `agents/writer.py`

`create_writer_agent(model=None) -> LlmAgent`

- `name="writer"`, model from `MODEL_HEAVY`, `output_key="report_markdown"`.
- Instruction: write a short report in Markdown that answers the question using only
  `{reading_notes}`. Cite the `paper_id` in square brackets after each claim. Never
  invent sources. If the notes say nothing was found, say that plainly.

All three factories take an explicit `model` argument first, and fall back to
`load_models()` only when it is `None`. This keeps them testable without `.env`.

The `{search_results}` and `{reading_notes}` placeholders rely on ADK filling
`instruction` from session state. This is not verified yet (see the index). Check it
in A6 with a manual run, and if it does not work, pass the data in another way.

## Tests

No test calls the Gemini API.

- `tests/test_config.py`: `load_models()` returns both values when set (use
  `monkeypatch.setenv`, and replace `load_dotenv` with a no-op so the real `.env` does
  not interfere); raises `RuntimeError` naming each missing variable.
- `tests/test_tools.py`: the tool returns a list of dicts with the three keys; it
  honours `budget_words`; it passes `hybrid` and `k` to the search function (a fake
  records them); its name is `search_papers`; with the stub search, `"low-rank"` finds
  `2106.09685`.
- `tests/test_agents.py`: each factory, called with an explicit model string, returns
  an `LlmAgent` with the expected `name`, `model` and `output_key`; the Searcher has
  exactly one tool; with `model=None` and a configured environment, the Writer takes
  `MODEL_HEAVY` and the others `MODEL_LIGHT`.

## When the stage is finished

Follow "When a stage is finished" in the [index](README.md). In the documentation,
describe each of the five modules and the three test files.

## Commit message

```
feat: add core adk agents
```
