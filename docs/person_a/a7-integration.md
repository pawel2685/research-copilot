# A7: Integration with B and C

Status: in progress. Everything that does not depend on B is done. B's search function
and Planner are not in this branch yet (see "Still missing").

Goal: the real modules replace the stand-ins, `answer()` is the one public entry point,
and `python main.py "<question>"` answers a question.

## Files

### `agents/pipeline.py` (new)

- **Module docstring.** Says that this is the public entry point, used by the
  evaluation harness and `main.py`.
- **`default_search`.** The search function used when none is given. It is still the
  stub from `stubs/search.py`, marked with a `TODO(B)` comment. This is the one line
  to change when B's retrieval is merged.
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

### `tests/test_main.py` (changed)

The test of the old placeholder is replaced. New tests, with a fake `answer`:

- The report is printed with `Verified: yes`, and with `Verified: no`.
- The question is read from the command line.
- No question (nothing, empty, blanks) prints the usage and returns non-zero.
- A `RuntimeError` from `answer` is printed and returns `1`.

The three tests of the quality gate are unchanged.

## Still missing

Needed from B, then this stage can be finished:

- B's search function in `retrieval/` (now only an empty `__init__.py`). Then set
  `default_search` in `agents/pipeline.py` to it.
- B's Planner agent. Then pass it as the default `planner` in `answer`. Its output
  must match what `normalize_sub_questions` accepts (see the findings in
  [a6-orchestration.md](a6-orchestration.md)).
- The manual check with a real key: `python main.py "What problem does
  retrieval-augmented generation address?"`, and compare the cited sources with
  `evals/questions.py` (`2005.11401`).

Until then the app runs end to end on the stub search with real Gemini calls, with the
Critic from C.

## Commit

```
feat: integrate retrieval, compression and critic
```
