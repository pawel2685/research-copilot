# A9: Evaluation hand-off

Status: done (B stubbed). The code and tests are finished. Real experiment results need
B's retrieval and Planner (see "Open dependency on B").

Goal: C can run the experiments E0 to E4 on the pipeline and get the numbers the
metrics need.

**Open dependency on B.** A7 is done with B's search and Planner stubbed (see "Waiting
for B" in [README.md](README.md)). Experiments run before that measure the stub, not
the real retrieval, so they are only a test of the harness. Repeat them after B is
integrated.

## For C: how to use it

```python
from agents.pipeline import answer_with_stats
from evals.experiment_configs import get_run_config
from evals.metrics import EvaluationRecord

report, stats = answer_with_stats(question.question, get_run_config("E4"))
record = EvaluationRecord(
    configuration="E4",
    question_id=question.id,
    retrieved_source_ids=stats.retrieved_source_ids,
    expected_source_ids=question.expected_source_ids,
    llm_calls=stats.llm_calls,
    input_tokens=stats.input_tokens,
    output_tokens=stats.output_tokens,
    latency_seconds=stats.latency_seconds,
)
```

- Set `LLM_CACHE=off` for every measured run. A cached answer returns at once and costs
  no tokens (A8). `answer_with_stats` logs a warning when the cache is on.
- Run the questions one after another. The free tier has low rate limits, and the
  retries wait on a `429` or `503`, which counts into the latency.
- `report_quality_score` is not produced here: it is a manual score.

## Files

### `evals/experiment_configs.py` (new)

A new file in C's folder, as the plan asks. No existing file of C was edited.

- **`EXPERIMENT_RUN_CONFIGS`.** The `RunConfig` of each experiment, with the same names
  as `EXPERIMENT_CONFIGS` in `evals/metrics.py`. The settings are cumulative, each
  experiment changes one thing:

  | Name | `hybrid` | `compress_budget_words` | `use_planner` | `use_critic` |
  |------|----------|-------------------------|---------------|--------------|
  | E0 | `False` | `None` | `False` | `False` |
  | E1 | `True` | `None` | `False` | `False` |
  | E2 | `True` | `3000` | `False` | `False` |
  | E3 | `True` | `3000` | `True` | `False` |
  | E4 | `True` | `3000` | `True` | `True` |

- **`get_run_config(name)`.** Returns a copy, so changing it does not change the table.
  An unknown name raises `ValueError`.
- **What E0 means (open decision for C).** E0 runs through the same pipeline as the
  others, with every switch off: vector search only, no compression, no Planner, no
  Critic. It still makes several model calls (Searcher, Reader, Writer). It is not a
  separate single-call baseline. If C wants "one LLM call, no tools" for E0, that needs
  its own function and has to be agreed first. The docstring of the module says the
  decision is not agreed yet.

### `agents/stats.py` (new)

- **`RunStats`.** A frozen dataclass: `retrieved_source_ids` (tuple), `llm_calls`,
  `input_tokens`, `output_tokens`, `latency_seconds`. The names match
  `EvaluationRecord`.
- **`UsageCounter`.** Adds up the ADK events of a run. An event with `usage_metadata`
  counts as one model call. Its `prompt_token_count` goes to the input tokens, its
  `candidates_token_count` plus `thoughts_token_count` to the output tokens (thinking
  tokens count against the limits, so they are output). Events without usage data
  (tool results, skipped agents) and partial streaming chunks are not counted, and a
  missing count is zero.
- **`RecordingSearch`.** Wraps the search function and remembers the `paper_id` of every
  returned passage, in order, each once.

### `agents/runner.py` (changed)

- `PipelineResult` has four new fields with default values: `retrieved_source_ids`,
  `llm_calls`, `input_tokens`, `output_tokens`.
- `_run_agent` takes a `UsageCounter` and adds every event to it. The revision run
  adds to the same counter, so a revised answer is measured with both runs.
- `run_pipeline` wraps `search_fn` in a `RecordingSearch` and fills the new fields.

### `agents/pipeline.py` (changed)

- **`answer_with_stats(question, cfg=None, *, search_fn, planner, critic)`.** Returns
  `(Report, RunStats)`. The latency is the wall-clock time of the run
  (`time.perf_counter`), including the creation of the Critic. It logs a warning when
  `LLM_CACHE` is not `off`.
- **`answer(...)`.** Returns only the report and does not warn, because the cache is
  meant for the app and for development. Both call the same private `_run`.

### `tests/fake_llm.py` (changed)

`FakeLlm` has `prompt_tokens` and `completion_tokens`. When set, every response carries
usage data.

### `tests/test_experiment_configs.py` (new)

- The names are the ones of the evaluation (`EXPERIMENT_CONFIGS`).
- Each name maps to its row of the table.
- The configurations are cumulative: neighbours differ in exactly one switch.
- `get_run_config` returns a copy. The time budget is the same everywhere.
- Unknown names (`E5`, `e1`, empty, `baseline`) raise `ValueError`.

### `tests/test_stats.py` (new)

- `UsageCounter`: sums over events, zero for events without usage data, zero for
  missing counts, thinking tokens as output, partial chunks ignored.
- `RecordingSearch`: papers in order, once each, and `k` and `hybrid` passed on.
- Runner with a fake `Runner` that yields events with usage data: the counts add up,
  silent events give zeros, the revision run is counted too, and the retrieved papers
  are listed in rank order.
- The whole flow on the real ADK runner with `FakeLlm`: 4 model calls with the expected
  tokens, so the real events do carry the usage data. Retrieval is recorded before
  compression.
- `answer_with_stats`: report and stats, the latency from the clock, zero stats without
  usage data, the warning with the cache on and no warning with it off, no warning in
  `answer`, and the search function is passed on.

## Not checked

- Usage data of real Gemini responses. The shape (`prompt_token_count`,
  `candidates_token_count`, `thoughts_token_count` on `Event.usage_metadata`) was
  checked in the installed ADK and with the real runner and a fake model. A first real
  run should confirm that the numbers are plausible.
- The `retrieved_source_ids` are the output of the search function before
  compression, because Recall@k is about the ranking of the retrieval. If C prefers
  the papers that survived compression, that is a one-line change.

## Commit

```
feat: add experiment configs and run stats
```
