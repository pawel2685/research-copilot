# A7: Integration with B and C

Status: done. B's search is integrated: `answer` searches B's corpus through
`agents/retrieval_search.py`. B's Planner (`agents/planner.py`) is integrated too: `answer`
creates it when `cfg.use_planner` is on. What is still open is in "Open items" at the end
of this file.

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
  `create_critic_agent()`. When `cfg.use_planner` is on and no planner is given, it
  creates B's `create_planner_agent()`. When a switch is off, that agent is not created
  and the pipeline leaves it out (a missing Planner means the original question is
  searched). The `RunStats` of the run also say whether the Planner or the Critic was
  skipped because of the time budget (`planner_skipped_by_deadline`,
  `critic_skipped_by_deadline`, see [a9-evaluation-handoff.md](a9-evaluation-handoff.md)).

### `agents/planner.py` (B's file, used as it is)

`create_planner_agent(model=None)` returns an `LlmAgent` named `planner` on `MODEL_LIGHT`
(read with `load_models()`, never a hard-coded name). Its instruction asks for up to four
focused sub-questions as a JSON array of strings, in the language of the question, and
the answer is stored in the state under `sub_questions`. That is what the search branches
read. `normalize_sub_questions` (`agents/skipping.py`) turns the text into a list, also
when the model puts the JSON in a Markdown code fence, and falls back to the original
question when the text is not usable. Nothing is called when the agent is created.

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
- **`main(argv=None)`.** The quality gate still runs first. Then a question on the
  command line goes to `run_app`, and no question (nothing, empty, blanks) starts the web
  interface with `launch_web()`. So `python main.py` is the one entry point for both: the
  interface in the browser, or one question in the terminal. `USAGE` mentions both.

### `launcher.py` (new)

Everything `python main.py` needs to start the web interface, so `main.py` stays short.

- **Constants.** `ROOT`, `DATA_DIR` (`data/`, where B keeps the corpus), `HOST` and `PORT`
  (`127.0.0.1:8000`), `AGENTS_DIR` (`demo`, the directory `adk web` serves).
- **`CORPUS_QUERY`.** The arXiv query that fetches the five papers behind the evaluation
  questions by title, the same one as in the README (step 6).
- **`config_problems()`.** Loads `.env` and returns what is missing as messages:
  `GOOGLE_API_KEY` (also the placeholder from `.env.example`), `MODEL_LIGHT` and
  `MODEL_HEAVY`. An empty list means the configuration is complete. It does not check that
  the key is valid or that the quota is left.
- **`ensure_corpus(data_dir=DATA_DIR)`.** Runs B's CLI as a subprocess (`python -m
  retrieval`), only for what is missing: `fetch` when `corpus.jsonl` is missing and
  `index` when `chroma/` is missing. The query goes in as one argument of the argument
  list, so it needs no shell quoting (the problem of Windows PowerShell 5.1 in the
  README). B's code is used as it is, not edited. Returns `0` when both exist at the
  end, `1` when a step failed.
- **`launch_web()`.** Stops with the messages of `config_problems()` and a pointer to the
  README when `.env` is incomplete, stops when the corpus cannot be prepared, otherwise
  prints the address and serves `demo/` with `python -m google.adk.cli web --no-reload`.
  Ctrl+C ends it cleanly (return code `0`).

### `README.md` (changed)

The "Running the app and tests" section describes both modes of `python main.py`. Step 6
(the corpus) says that the web mode builds it by itself.

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

### `tests/test_launcher.py` (new)

`subprocess.run` and `subprocess.call` are replaced by recorders, `.env` is not read, and
nothing is downloaded.

- `config_problems`: a complete `.env` has no problems, every missing setting is named,
  the placeholder key counts as missing.
- `ensure_corpus`: nothing runs when the corpus and the index exist, a missing corpus is
  fetched and indexed (the query is one argument, with the data directory), only the
  index is built when the corpus exists, a failed fetch stops before the index, a failed
  index returns `1`.
- The corpus query names all five evaluation papers (checked against
  `evals/questions.py`).
- `launch_web`: stops on a bad `.env` and on a corpus that cannot be prepared (the server
  is not started), serves `demo` on `127.0.0.1:8000` with its return code, and Ctrl+C
  ends cleanly. The `demo/research_copilot/agent.py` file that `adk web` looks for exists.

### `tests/test_main.py` (changed)

`main()` is tested with a question (goes to `run_app`), without one (starts the web
interface, even for empty and blank arguments), with the command line by default, and
with a failing gate (nothing starts). The tests of `run_app` are unchanged: a fake
`answer`, `Verified: yes` and `no`, the question from the command line, no question
(usage, non-zero), and a `RuntimeError` (printed, `1`). The three tests of the quality
gate are unchanged.

## Open items

- The Planner's output was checked with one real call outside ADK: a clean JSON array of
  two sub-questions, which the parser reads as two items. A whole run through the
  pipeline was not seen (the API answered `503` on every try that day). The parser also
  accepts an object with `questions` and both forms inside a code fence. See
  [README.md](README.md).
- `PLANNER_MIN_LEFT_S` is still an example value, see
  [a4-time-budget.md](a4-time-budget.md).

## Manual check (done)

With a corpus of 41 papers built from title queries of the five evaluation papers
(`python -m retrieval fetch ...`, then `index`), `python main.py "What problem does
retrieval-augmented generation address?"` printed a report with three claims, all cited
`[2005.11401]`, and `Verified: yes`. The whole run, including the test suite that the
app runs first, took 33 s. The run found a bug in `agents/cache.py`: the cache key
could not be built for the Critic, because its output schema is a class in the request
config. It is fixed (see [a8-cache-and-retries.md](a8-cache-and-retries.md)).

That run was made before the Planner was merged, so it did not include the Planner.

## Commit

```
feat: integrate retrieval, compression and critic
```
