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
| A7 | [Integration with B and C](a7-integration.md) | done (B stubbed) | A6 |
| A8 | [Cache and retries](a8-cache-and-retries.md) | to do | A6 |
| A9 | [Evaluation hand-off](a9-evaluation-handoff.md) | to do | A7, A8 |
| A10 | [Demo and cleanup](a10-demo-and-cleanup.md) | to do | A9 |

The instructions for building each stage are in
[implementation/](implementation/README.md), one plan per stage.

## Waiting for B

A7 is done with B's parts stubbed, so the later stages can go on. When B's work is
merged into `main` (the user pulls it into `feat/person-a`), do these and tick them
off. Until then the app runs on the stub search without a Planner.

- [ ] Search: set `default_search` in `agents/pipeline.py` to B's function from
      `retrieval/` (it must fit `SearchFn`). Replaces `stubs/search.py` as the default.
- [ ] Planner: pass B's Planner agent as the default `planner` of `answer` in
      `agents/pipeline.py`. Check that its output matches `normalize_sub_questions`
      (a list of strings, a dict with a `questions` list, or a JSON string of either).
- [ ] Tests: add a test that `answer` uses B's search by default, and one run with the
      Planner. Keep the fake-model tests.
- [ ] Manual check with a real key: `python main.py "What problem does
      retrieval-augmented generation address?"`. The cited sources should include
      `2005.11401` (see `evals/questions.py`).
- [ ] Docs: update `a7-integration.md` and set its status to `done`.

Other open items that need the real API key: the manual run from
[a6-orchestration.md](a6-orchestration.md) and the example thresholds
`PLANNER_MIN_LEFT_S` and `CRITIC_MIN_LEFT_S`.

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
| `search()` returning `Chunk` with arXiv ids | B | **missing**: `retrieval/` is empty | stub in `stubs/` (A2), used by `agents/pipeline.py` |
| Planner agent | B | **missing** | `planner=None`: the Planner is left out and the original question is searched |
| `compress()` | C | integrated | already merged (`context/compression.py`) |
| Critic agent | C | integrated | already merged (`agents/critic.py`), wired in `agents/pipeline.py` |

What to do when the missing parts arrive is in "Waiting for B" above.

**Effect on the later stages.** Until B's parts are integrated, anything measured or
shown runs on the stub search (five fixed passages) and without a Planner. Results of
A9 (the experiments E0 to E4) and the demo of A10 are not final then. The ablation of
the Planner (E-configs with `use_planner`) and of hybrid search cannot show a real
effect, because the stub ignores `hybrid` and there is no Planner.

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
