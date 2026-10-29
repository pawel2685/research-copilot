# A3: Baseline pipeline without ADK

Status: done.

Goal: a plain-Python `answer(question, cfg)` that runs end to end on the stub search
and C's real `compress()`, with no network call. The evaluation harness can call it from
day one, and later stages reuse `compress_chunks` for compression.

## Files

### `agents/passages.py`

- **Module docstring.** Says the module holds helpers for `Chunk` objects.
- **`compress_chunks(chunks, budget_words)`.** Compresses chunks to a word budget while
  keeping their `paper_id`, `score` and `source_url`. `compress()` works on plain texts
  and drops empty ones, so its result cannot be mapped back by index when empty texts
  are present. The function:
  1. Drops chunks whose text has no words.
  2. Returns the remaining chunks unchanged when `budget_words` is `None`.
  3. Calls `compress()` on the remaining texts. Its result is a prefix of those texts,
     the last one possibly shortened, so result `i` belongs to remaining chunk `i`.
  4. Returns a copy of each of those chunks with the new text (`model_copy`). The input
     chunks are never modified. A budget of `0` gives an empty list.

### `agents/baseline.py`

- **Module docstring.** Says it is plain Python and that the writer is a template on
  purpose, until the ADK agents in A5.
- **`NO_SOURCES_MESSAGE`.** The line `No sources were found for this question.`
- **`build_report(question, chunks)`.** The template writer:
  - With no chunks, the markdown is `# <question>` followed by `NO_SOURCES_MESSAGE`,
    and `sources` is empty.
  - Otherwise `sources` holds the unique `paper_id` values in order of appearance, and
    the markdown has a `# <question>` title, a `## Findings` list with one
    `- <text> [<paper_id>]` line per chunk, and a `## Sources` list with one line per
    unique paper: the `source_url`, or the `paper_id` when the url is empty.
  - `verified` is always `False`, because no Critic ran.
- **`answer(question, cfg=None, *, search_fn=stub_search)`.** The pipeline:
  1. `cfg` defaults to `RunConfig()`.
  2. `search_fn(question, hybrid=cfg.hybrid)` finds the passages. The default is the
     stub from `stubs/search.py`, until A7 replaces it with B's retrieval.
  3. `compress_chunks(chunks, cfg.compress_budget_words)` trims them.
  4. `build_report` writes and returns the `Report`.

### `tests/test_passages.py`

Seven tests, top to bottom:

- Empty and whitespace-only chunks are dropped.
- A `None` budget keeps the chunks unchanged.
- A `None` budget still drops empty chunks.
- A small budget trims the last kept chunk and drops the rest.
- The kept chunks keep their `paper_id` and `source_url`.
- A budget of `0` returns an empty list.
- The input chunks are not modified.

### `tests/test_baseline.py`

Eleven tests with a fake `search_fn` that records its calls, top to bottom:

- The result is a `Report` with the same question, and `verified` is `False`.
- Every kept `paper_id` is in `sources` and in the markdown, without duplicates.
- The exact markdown layout of a one-passage report.
- An empty `source_url` falls back to the `paper_id` in `## Sources`.
- A `None` budget keeps all matched passages.
- A small budget keeps only the passages that fit.
- A budget of `0` gives no sources and the "No sources" message.
- An empty search result gives the "No sources" message.
- `cfg.hybrid` is passed to `search_fn`.
- Without a config, the default `RunConfig()` is used.
- With the default stub, `answer("low-rank matrices")` has source `2106.09685`.

## Commit

```
feat: add baseline pipeline
```
