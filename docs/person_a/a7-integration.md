# A7: Integration with B and C

Status: done (Planner stubbed). B's search is integrated: `answer` searches B's corpus
through `agents/retrieval_search.py`. B's Planner does not exist yet, so "no Planner"
stands in for it. The checklist for what is left is in "Waiting for B" in
[README.md](README.md).

Goal: the real modules replace the stand-ins, `answer()` is the one public entry point,
and `python main.py "<question>"` answers a question.

## Files

### `agents/pipeline.py` (new)

- **Module docstring.** Says that this is the public entry point, used by the
  evaluation harness and `main.py`.
- **`default_search`.** The search function used when none is given. It is B's
  retrieval through the adapter `agents/retrieval_search.py` (see below). It was the
  stub from `stubs/search.py` until B's retrieval was merged. The app and the demo now
  need the corpus built with `python -m retrieval`; tests pass a search function
  explicitly and never touch the corpus.
- **`cited_paper_ids(result)`.** The unique arXiv ids cited in the notes of the four
  branches (`reading_notes_1` to `reading_notes_4`), in order of appearance. An id is
  written in square brackets, as the Reader does (`[2005.11401]`). Other brackets such
  as `[1]` are ignored, and a version suffix (`v2`) is dropped.
- **`to_report(question, result)`.** Converts a `PipelineResult` into a `Report`: the
  question, the report Markdown, the cited ids as `sources`, and `verified` from
  `result.verified`. That is true only when the Critic ran and approved the report. A
  skipped, rejecting or revised result is unverified.
- **`answer(question, cfg=None, *, search_fn=default_search, planner=None,
  critic=None)`.** Runs `run_pipeline` with `asyncio.run` and returns `to_report(...)`.
  When `cfg.use_critic` is on and no critic is given, it creates C's
  `create_critic_agent()`. When the switch is off, no critic is created. The Planner is
  `None` for now, which means the Planner is left out and the original question is
  searched.

### `agents/retrieval_search.py` (new, added when B's retrieval was merged)

The adapter that makes B's retrieval fit `SearchFn`. B's `retrieval.Retriever.search`
returns dictionaries and takes `top_k` and `mode`. The pipeline expects
`search(query, k, hybrid) -> list[Chunk]`. B's code is not changed.

- **`_retriever(data_dir)`.** Loads `corpus.jsonl` from the data directory and builds one
  `Retriever` per directory (cached, because building the BM25 index is slow). When the
  corpus does not exist it raises a `RuntimeError` that names the commands that build it
  (`python -m retrieval fetch ...` and `python -m retrieval index`). `main.py` already
  prints a `RuntimeError` as `Error: ...`.
- **`to_chunk(item)`.** Converts one result into a `Chunk`: `arxiv_id` becomes
  `paper_id` without the version suffix (`2005.11401v4` becomes `2005.11401`, because the
  evaluation metrics compare plain ids), `text` and `url` are copied, `score` becomes a
  float.
- **`search(query, k=8, hybrid=True, *, data_dir=DEFAULT_DATA)`.** The `SearchFn`.
  `hybrid=True` uses B's `"hybrid"` mode (BM25 and vector search fused). `hybrid=False`
  uses `"vector"`, which is the baseline E0 (vector search only, see
  `evals/experiment_configs.py`). The keyword-only `data_dir` is for tests and does not
  break the contract.

It is the default search of `answer` and `answer_with_stats` (`agents/pipeline.py`).
`agents/baseline.py` and `agents/runner.py` keep the stub as their default, so the plain
Python baseline and `run_pipeline` still work without a corpus.

### `main.py` (changed)

- **Module docstring and `USAGE`.** The command is now `python main.py "<question>"`.
- **`run_app(argv=None)`.** Joins the arguments (default: `sys.argv[1:]`) into the
  question. Without a question it prints the usage line and returns `2`. Otherwise it
  calls `answer(question)`, prints the Markdown report, an empty line and
  `Verified: yes` or `Verified: no`, and returns `0`. A `RuntimeError` (for example a
  model name missing in `.env`) is printed as `Error: ...` and returns `1`.
- **`main()`.** Unchanged: the quality gate still runs first.

### `README.md` (changed)

The "Running the app and tests" section shows the new command with a question.

### `tests/test_pipeline.py` (new)

`run_pipeline` is replaced by a fake that records its arguments, so no model is called.

- `cited_paper_ids`: unique and in order, other brackets and versions, no notes, and
  only the notes count (not the search results).
- `to_report`: copies question, Markdown and sources. `verified` is true only for an
  approving Critic, not for a skipped, rejecting or revised result.
- `answer`: passes the config, the search function and the Planner on, uses the default
  config, creates C's Critic only when the switch is on, and accepts its own search
  function, Planner and Critic.
- Two runs of the whole flow on the real ADK runner with `FakeLlm`: an approving Critic
  gives a verified report, and a tiny time budget skips the Critic and gives an
  unverified report.

### `tests/test_retrieval_search.py` (new)

Uses a real `Retriever` on a two-paper corpus in `tmp_path`, with a deterministic
encoder in place of the embedding model, so nothing is downloaded.

- `to_chunk`: maps the fields, drops the version, keeps an id without one.
- `search`: returns `Chunk`s with plain arXiv ids, `k` limits the results, a blank query
  returns an empty list.
- `hybrid` selects the `"hybrid"` or `"vector"` mode (fake retriever records the mode).
- The corpus is loaded once per directory.
- A missing corpus raises a `RuntimeError` that names `python -m retrieval fetch`.
- The adapter fits `SearchFn`, and its default data directory is B's.

### `tests/test_pipeline.py` and `tests/test_demo.py` (changed)

- `test_pipeline.py`: a new test checks that `default_search` is the adapter of B's
  retrieval. The test of the whole flow with a fake model now passes the stub search
  explicitly, because the default needs a corpus on disk. The flow it checks is the same.
- `test_demo.py`: the same for the demo test with the real ADK runner and a fake model,
  which builds its search tool from the stub.

### `tests/test_main.py` (changed)

The test of the old placeholder is replaced. New tests, with a fake `answer`:

- The report is printed with `Verified: yes`, and with `Verified: no`.
- The question is read from the command line.
- No question (nothing, empty, blanks) prints the usage and returns non-zero.
- A `RuntimeError` from `answer` is printed and returns `1`.

The three tests of the quality gate are unchanged.

## Still missing (placeholders)

Left to do (same list as "Waiting for B" in [README.md](README.md)):

- B's Planner agent. Then pass it as the default `planner` in `answer`. Its output
  must match what `normalize_sub_questions` accepts (see the findings in
  [a6-orchestration.md](a6-orchestration.md)).
- The manual check with a real key, after building the corpus (`python -m retrieval
  fetch ...` and `python -m retrieval index`): `python main.py "What problem does
  retrieval-augmented generation address?"`, and compare the cited sources with
  `evals/questions.py` (`2005.11401`). The corpus query must include that paper.

Until the Planner exists, the app runs end to end on B's search with real Gemini calls,
with the Critic from C and without a Planner.

## Commit

```
feat: integrate retrieval, compression and critic
```
