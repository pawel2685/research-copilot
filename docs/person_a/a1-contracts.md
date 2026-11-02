# A1: Contracts

Status: done.

Goal: one shared file with the data types and function signatures that all modules
agree on, so A, B and C can work in parallel.

## Files

### `contracts.py`

Read top to bottom:

- **Module docstring.** States that the file belongs to the whole team and that it is
  changed only in a separate pull request approved by everyone.
- **`Chunk`** (pydantic model): one passage from a paper.
  - `paper_id`: the arXiv id, for example `2005.11401`. The evaluation metrics compare
    arXiv ids, so this must be an arXiv id.
  - `text`: the passage.
  - `score`: relevance score from retrieval, default `0.0`.
  - `source_url`: link to the source, default empty.
- **`Report`** (pydantic model): what the system returns for one question.
  - `question` and `markdown`: the question and the written report.
  - `sources`: list of source ids. Each instance gets its own list.
  - `verified`: `False` by default. It is `True` only when the Critic ran and its
    result has `approved` equal to `True`.
- **`RunConfig`** (pydantic model): the switches for one run. The same switches drive
  the experiments E0 to E4.
  - `use_planner`, `use_critic`, `hybrid`: all `True` by default.
  - `compress_budget_words`: word budget for context compression, `3000` by default.
    `None` means no compression. It counts whitespace-separated words, not model
    tokens, because that is how `compress()` counts.
  - `time_budget_s`: time budget of a run in seconds, `90.0` by default (an example
    value to be tuned).
- **`SearchFn`** (protocol): the signature of the search function that retrieval
  provides: `(query, k=8, hybrid=True) -> list[Chunk]`.
- **`CompressFn`** (protocol): the signature of C's `compress()`:
  `(chunks: Sequence[str], budget: int) -> list[str]`. It works on plain texts and
  drops empty chunks, so `result[i]` does not always match `chunks[i]`.

### `tests/test_contracts.py`

Six tests, top to bottom:

- `Chunk` has the expected defaults (`score` 0, empty `source_url`).
- `Report` is unverified by default and has no sources.
- Two `Report` instances do not share the same `sources` list.
- `RunConfig` has the expected defaults.
- `RunConfig` accepts `None` to turn compression off.
- C's real `compress()` fits `CompressFn`, so a signature change on either side shows
  up as a failing test.

## Commit

```
feat: add shared contracts
```
