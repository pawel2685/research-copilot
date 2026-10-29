# A9: Evaluation hand-off, implementation plan

Status: to do. Depends on A7 and A8.

## Goal

C can run the experiments E0 to E4 on the real pipeline and get the numbers its metrics
need.

## Read first

- `evals/metrics.py` (C): `EvaluationRecord` needs `configuration`, `question_id`,
  `retrieved_source_ids`, `expected_source_ids`, `report_quality_score`, `llm_calls`,
  `input_tokens`, `output_tokens`, `latency_seconds`. `EXPERIMENT_CONFIGS` is
  `("E0", "E1", "E2", "E3", "E4")`.
- `evals/questions.py` (C): the five questions.
- `agents/pipeline.py` and `agents/runner.py` (A6, A7)

## Files to create or change

- `evals/experiment_configs.py` (new)
- `agents/stats.py` (new)
- `agents/pipeline.py` and `agents/runner.py` (change)
- `tests/test_experiment_configs.py` and `tests/test_stats.py` (new)

## Instructions

### `evals/experiment_configs.py`

`EXPERIMENT_RUN_CONFIGS: dict[str, RunConfig]` with these cumulative settings:

| Name | `hybrid` | `compress_budget_words` | `use_planner` | `use_critic` |
|------|----------|-------------------------|---------------|--------------|
| E0 | `False` | `None` | `False` | `False` |
| E1 | `True` | `None` | `False` | `False` |
| E2 | `True` | `3000` | `False` | `False` |
| E3 | `True` | `3000` | `True` | `False` |
| E4 | `True` | `3000` | `True` | `True` |

Open decision for C: E0 is described as "one LLM, vector search, no compression, no
optional agents". Agree with C whether E0 runs through the same pipeline with all
switches off (this table) or through a separate single-call baseline. Write the outcome
into the documentation.

`get_run_config(name) -> RunConfig` returns a copy and raises `ValueError` for an
unknown name.

### `agents/stats.py`

`RunStats`, a frozen dataclass: `retrieved_source_ids: tuple[str, ...]`, `llm_calls:
int`, `input_tokens: int`, `output_tokens: int`, `latency_seconds: float`.

- `answer_with_stats(question, cfg) -> tuple[Report, RunStats]` in `agents/pipeline.py`:
  runs the pipeline like `answer()` and also collects the stats.
- `llm_calls`, `input_tokens` and `output_tokens` come from the ADK events produced by
  the run (each model response carries usage metadata). The exact attribute is not
  verified yet: inspect an event from a real run, then count one call per event with
  usage data and sum its prompt and candidate token counts.
- `retrieved_source_ids`: the `paper_id` values the Searchers returned, in order.
- `latency_seconds`: wall-clock time of the run (`time.perf_counter`).

Cached responses must not count as measured runs (see A8). When `LLM_CACHE` is not
`off`, `answer_with_stats` should log a warning.

`answer()` can be a thin wrapper that returns only the `Report`.

## Tests

- `tests/test_experiment_configs.py`: each name maps to the table above; the configs
  are cumulative (each adds one thing to the previous); `get_run_config` returns a
  copy, so changing it does not change the table; an unknown name raises `ValueError`.
- `tests/test_stats.py`: with a fake runner that yields events with usage data, the
  stats add up; with events without usage data the counts are zero; latency is
  non-negative.

## When the stage is finished

Follow "When a stage is finished" in the [index](README.md). Tell C (the user does)
that `answer_with_stats` and `get_run_config` are ready, and what E0 means.

## Commit message

```
feat: add experiment configs and run stats
```
