# Person A: core and orchestration

This folder tracks the work on part A of Research Copilot, one file per stage.
Update the files as the work progresses, so the whole team can see where we are.
Commit messages and branch names follow [CONTRIBUTING.md](../CONTRIBUTING.md).

## Scope

- Agents: Searcher, Reader, Writer.
- Orchestration in ADK (`SequentialAgent`, `ParallelAgent`) and one Critic revision.
- Time budget and skipping of the Planner and the Critic.
- `RunConfig` switches that drive the ablation (E0..E4).
- `answer(question, cfg) -> Report`, the function the evaluation harness calls.

Not in scope: retrieval and the Planner (B); compression, the Critic and the
evaluation tooling (C).

## Stages

| Stage | File | Status | Depends on |
|-------|------|--------|------------|
| A0 | [Setup](a0-setup.md) | done | nothing |
| A1 | [Contracts](a1-contracts.md) | done | A0 |
| A2 | [Stubs](a2-stubs.md) | done | A1 |
| A3 | [Baseline pipeline](a3-baseline-pipeline.md) | done | A2 |
| A4 | [Time budget and skipping](a4-time-budget.md) | done | A3 |
| A5 | [ADK agents](a5-adk-agents.md) | done | A3 |
| A6 | [ADK orchestration](a6-orchestration.md) | done | A4, A5 |
| A7 | [Integration with B and C](a7-integration.md) | done | A6 |
| A8 | [Cache and retries](a8-cache-and-retries.md) | done | A6 |
| A9 | [Evaluation hand-off](a9-evaluation-handoff.md) | done | A7, A8 |
| A10 | [Demo and cleanup](a10-demo-and-cleanup.md) | done | A9 |

The instructions for building each stage are in
[implementation/](implementation/README.md), one plan per stage.

## Integration with B and C

B's and C's parts are merged and wired in. Checklist:

- [x] Search: `default_search` in `agents/pipeline.py` is B's retrieval through the
      adapter `agents/retrieval_search.py` (it fits `SearchFn`). The app needs the
      corpus: `python -m retrieval fetch ...` and `python -m retrieval index`, or
      `python main.py`, which builds it by itself.
- [x] Planner: `answer` creates B's Planner (`agents/planner.py`) when `cfg.use_planner`
      is on, and the demo does the same. Its output is a JSON array of strings, which
      `normalize_sub_questions` accepts, also inside a Markdown code fence.
- [x] Tests: the search (`test_default_search_is_b_retrieval_through_the_adapter`,
      `tests/test_retrieval_search.py`), the Planner (`tests/test_planner.py`, the flow
      tests with a fake model) and the parser (`tests/test_skip_callbacks.py`).
- [x] Manual check with a real key: `python main.py "What problem does
      retrieval-augmented generation address?"` gave a report citing `2005.11401` and
      `Verified: yes`. It also found a bug in `agents/cache.py` (the Critic's output
      schema class could not be hashed), now fixed and tested. That run was made before
      the Planner was merged.
- [x] Docs: the stage files are up to date and all stages are `done`.

### Open items

- [ ] A whole run with the Planner. The Planner's own output was checked with a real call
      (its instruction and `MODEL_LIGHT`, outside ADK) on "How does BERT build on the
      Transformer architecture, and how does LoRA make fine-tuning such models
      cheaper?": a clean JSON array of two sub-questions, no code fence, and
      `normalize_sub_questions` read it as two items. A whole run through the pipeline
      was not seen: the API answered `503` (high demand) on every try that day, while
      one-line requests to both models worked. Do it once with `python main.py` and the
      same question, and look at the sub-questions in the `adk web` interface.
- [ ] `PLANNER_MIN_LEFT_S` is still an example value and needs a measurement now that
      the Planner exists. `CRITIC_MIN_LEFT_S` was measured (see
      [a4-time-budget.md](a4-time-budget.md)).

## Branch and commits

All stages are developed on one branch, `feat/person-a`. Each stage ends with one
commit that contains the code, its tests and the updated stage file in this folder.
Commit messages follow [CONTRIBUTING.md](../CONTRIBUTING.md) and do not carry a
stage number.

A stage file starts as a plan (planned files, dependencies, the commit message).
When the stage is done, it is rewritten as documentation: every file that was added
or changed, described from top to bottom.

## Dependencies on the others

| Need | From | Status | Workaround until it is ready |
|------|------|--------|------------------------------|
| `search()` returning `Chunk` with arXiv ids | B | integrated | `retrieval/` is merged. `agents/retrieval_search.py` adapts it to `SearchFn`, and `agents/pipeline.py` uses it. The stub in `stubs/` stays for tests, `agents/baseline.py` and `agents/runner.py` |
| Planner agent | B | integrated | `agents/planner.py`, created in `agents/pipeline.py` and in the demo |
| `compress()` | C | integrated | already merged (`context/compression.py`) |
| Critic agent | C | integrated | already merged (`agents/critic.py`), wired in `agents/pipeline.py` |

Nothing is missing. What is still open is in "Open items" above.

## Decisions so far

- Free tier only. No billing on the Google project.
- Model names live in `.env`, never in the code.
- Older models (`gemini-2.5-*`) return `404` for new accounts, so we use 3.5.
- `compress()` counts whitespace-separated words, not model tokens, so the budget in
  `RunConfig` is `compress_budget_words`.
- `Chunk.paper_id` is an arXiv id, because the evaluation metrics compare arXiv ids.
- `Report.verified` is true only when `CriticResult.approved is True`.
- `python main.py` runs the test suite first and needs at least 80% coverage, so every
  stage ships with tests.
