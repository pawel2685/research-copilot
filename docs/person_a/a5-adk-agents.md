# A5: ADK agents

Status: done.

Goal: the three core agents (Searcher, Reader, Writer) as real ADK `LlmAgent` objects,
created without any network call. The agents are not wired together yet: that is A6.

## Files

### `agents/config.py` (new)

- **`load_models()`.** Calls `load_dotenv()`, then reads `MODEL_LIGHT` and `MODEL_HEAVY`
  and returns them as `(light, heavy)`. A variable that is missing or empty raises a
  `RuntimeError` that names it, in the same style as `agents/critic.py`. Model names
  are never written in the code.

### `agents/tools.py` (new)

- **`make_search_tool(search_fn, *, hybrid=True, budget_words=None, k=8)`.** Returns
  the plain function `search_papers(query)` that the Searcher uses as a tool. The
  function calls `search_fn(query, k=k, hybrid=hybrid)`, compresses the result with
  `compress_chunks(chunks, budget_words)`, and returns a list of dicts with the keys
  `paper_id`, `text` and `source_url`, so the result is JSON-friendly.
- **Docstring of `search_papers`.** ADK builds the tool description from the name, the
  type hints and the docstring, so the docstring says what the tool does and what
  `query` means. Checked offline: ADK produces a declaration named `search_papers` with
  one required string parameter, `query`.
- **Why compression is here.** The Reader only ever sees passages within the word
  budget.

### `agents/searcher.py` (new)

- **`SEARCHER_INSTRUCTION`.** Call the search tool for the question and return the
  passages as they are, with their `paper_id`. Do not summarise and do not invent
  passages.
- **`create_searcher_agent(search_tool, model=None)`.** An `LlmAgent` named `searcher`
  with `tools=[search_tool]` and `output_key="search_results"`. When `model` is `None`
  it uses `MODEL_LIGHT`.

### `agents/reader.py` (new)

- **`READER_INSTRUCTION`.** Summarise the passages as short factual notes. Every note
  ends with its `paper_id` in square brackets. Use only the given passages, and say so
  when there are none. The passages are inserted with the `{search_results}`
  placeholder.
- **`create_reader_agent(model=None)`.** An `LlmAgent` named `reader` with
  `output_key="reading_notes"`. Default model: `MODEL_LIGHT`.

### `agents/writer.py` (new)

- **`WRITER_INSTRUCTION`.** Write a short Markdown report that answers the question
  using only the notes, with the `paper_id` in square brackets after each claim. Never
  invent sources. If nothing was found, say that plainly. The notes are inserted with
  the `{reading_notes}` placeholder.
- **`create_writer_agent(model=None)`.** An `LlmAgent` named `writer` with
  `output_key="report_markdown"`. Default model: `MODEL_HEAVY`.

All three factories take the model first and fall back to `load_models()` only when it
is `None`, so they are testable without `.env`.

### Not verified yet

The `{search_results}` and `{reading_notes}` placeholders rely on ADK filling the
instruction from session state. This is checked in A6 with a manual run. If it does not
work, the data has to be passed in another way. The manual check with a real API call
is also still to do.

### `tests/test_config.py` (new)

Five test cases. `load_dotenv` is replaced with a no-op, so the real `.env` never
interferes.

- Both values are returned when set.
- A missing `MODEL_LIGHT` and a missing `MODEL_HEAVY` each raise a `RuntimeError`
  that names the variable.
- An empty value counts as missing.

### `tests/test_tools.py` (new)

Six tests with a fake search function that records its calls:

- The tool returns dicts with the three keys.
- It honours `budget_words`.
- Without a budget it keeps everything.
- It passes the query, `hybrid` and `k` to the search function.
- Its name is `search_papers` and its docstring mentions `query`.
- With the stub search, `low-rank` finds `2106.09685`.

### `tests/test_agents.py` (new)

Six tests, none of them calls the API:

- The Searcher, the Reader and the Writer each have the expected type, `name`, `model`
  and `output_key`. The Searcher has exactly one tool, and the instructions of the
  Reader and the Writer contain their placeholders.
- With `model=None` and a configured environment, the Writer takes `MODEL_HEAVY` and
  the other two `MODEL_LIGHT`.
- An explicit model wins over the environment.
- Without a model and without the environment, a `RuntimeError` is raised.

## Commit

```
feat: add core adk agents
```
