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

### Free-tier limits found with the real API

- **`503` (overload) is on Google's side.** One call in six answered it in a test of single,
  sequential calls, and the errors come in bursts (three questions in a row failed). In a
  run of the five evaluation questions, two were answered and three failed. The pipeline
  makes about ten calls per question, so even a low rate of `503` often hits one of
  them. `answer` therefore repeats a whole run twice (20 s apart), and `main.py` prints a
  readable message instead of a traceback. See [a7-integration.md](a7-integration.md).
- **`MODEL_HEAVY=gemini-3.5-flash` has a quota of 20 requests per day** (shared with
  `gemini-3.6-flash`). The Writer makes one call per question, so it limits a day to about
  20 questions per key, and the 25 runs of the benchmark do not fit. `gemini-3.5-flash-lite`
  showed no such limit. Use it as `MODEL_HEAVY` for a day of experiments (the whole team
  the same). See the README, section "Models".
- **The cache does not replay a question with several sub-questions in full**, see
  [a8-cache-and-retries.md](a8-cache-and-retries.md).
- **The Critic is lenient.** It approved a report whose claim said that RAG works "without
  modifying model weights", while the abstract of the RAG paper describes a fine-tuning
  recipe. In one live run of the demo it also listed `searcher_2`, the name of an agent, as
  the source of two claims that no paper backs (a statement about adapters, and a general
  statement about RAG). Both look like an effect of the prompt in `agents/critic.py` (C's
  file) and of the Critic seeing the conversation of the agents. Worth telling C.

### Checked with the real API

- [x] A whole run with the Planner on "How does BERT build on the Transformer
      architecture, and how does LoRA make fine-tuning such models cheaper?": the Planner
      returned a clean JSON array (no code fence) with two sub-questions, the pipeline
      used both (10 model calls) and the report cited `1810.04805` and `2106.09685`. It
      took 67.6 s, while the API was under load (it answered `503` on earlier tries the
      same day).
- [x] `PLANNER_MIN_LEFT_S` and `CRITIC_MIN_LEFT_S` were measured and kept at 40 s and
      30 s, see [a4-time-budget.md](a4-time-budget.md).

Not checked: the interface in the browser with a real question (the server starts and
lists `research_copilot`, but the chat was not used), and `python main.py` on a machine
without `data/`.

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
