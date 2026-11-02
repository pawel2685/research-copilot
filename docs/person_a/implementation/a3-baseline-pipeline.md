# A3: Baseline pipeline, implementation plan

Status: to do. Depends on A2.

## Goal

A plain-Python `answer(question, cfg)` that runs end to end with no network call, on
the stub search and C's real `compress()`. The evaluation harness can call it from day
one, and A5 to A7 reuse its helper for compression.

## Read first

- `contracts.py` (`Chunk`, `Report`, `RunConfig`, `SearchFn`)
- `context/compression.py` (`compress(chunks: Sequence[str], budget) -> list[str]`)
- `stubs/search.py`

## Files to create

- `agents/passages.py`
- `agents/baseline.py`
- `tests/test_passages.py`
- `tests/test_baseline.py`

## Instructions

### `agents/passages.py`: `compress_chunks`

`compress_chunks(chunks: Sequence[Chunk], budget_words: int | None) -> list[Chunk]`

`compress()` works on plain texts and drops empty ones, so its result cannot be mapped
back to chunks by index when empty texts are present. This helper does the mapping:

1. Drop chunks whose text has no words (`not chunk.text.split()`).
2. If `budget_words` is `None`, return the remaining chunks unchanged.
3. Call `compress([c.text for c in remaining], budget_words)`.
4. The result is a prefix of the non-empty texts, the last one possibly shortened.
   Return `remaining[i].model_copy(update={"text": result[i]})` for every `i` in the
   result.

### `agents/baseline.py`: `answer`

`answer(question: str, cfg: RunConfig | None = None, *, search_fn: SearchFn = stub_search) -> Report`

Import the stub as `from stubs.search import search as stub_search`. It is the default
until A7 replaces it with B's retrieval.

1. `cfg = cfg or RunConfig()`.
2. `chunks = search_fn(question, hybrid=cfg.hybrid)`.
3. `kept = compress_chunks(chunks, cfg.compress_budget_words)`.
4. Build the report with a helper `build_report(question, chunks) -> Report`:
   - `sources`: the unique `paper_id` values in order of appearance.
   - `verified`: always `False` here, because no Critic ran.
   - `markdown`, with this layout:

     ```
     # <question>

     ## Findings
     - <text> [<paper_id>]

     ## Sources
     - <source_url, or paper_id when the url is empty>
     ```

   - When `chunks` is empty, `markdown` is `# <question>` followed by the line
     `No sources were found for this question.` and `sources` is empty.
5. Return the `Report`.

The writer is a plain template on purpose. The real writing comes with the ADK agents
in A5.

## Tests

`tests/test_passages.py`:

- empty chunks are dropped
- `None` budget keeps everything unchanged
- a small budget trims the last kept chunk and drops the rest
- the kept chunks keep their `paper_id` and `source_url`
- a budget of `0` returns an empty list
- the input chunks are not modified

`tests/test_baseline.py` (use fake `search_fn` functions, no network):

- returns a `Report` with the same question and `verified` equal to `False`
- every kept `paper_id` appears in `sources` and in `markdown`, without duplicates
- `compress_budget_words=None` keeps all matched passages
- `compress_budget_words=0` gives no sources and the "No sources" message
- an empty search result gives the "No sources" message
- `cfg.hybrid` is passed to `search_fn` (the fake records it)
- works with the default stub: `answer("low-rank matrices")` has source `2106.09685`

## When the stage is finished

Follow "When a stage is finished" in the [index](README.md): green `python -m pytest`,
rewrite `docs/person_a/a3-baseline-pipeline.md` as documentation (both new modules and
both test files, top to bottom), set A3 to `done` in `docs/person_a/README.md`, print
the commit message.

## Commit message

```
feat: add baseline pipeline
```
