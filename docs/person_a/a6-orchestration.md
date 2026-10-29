# A6: ADK orchestration

Status: to do.

Goal: the agents run as one flow.

## Planned files

- `agents/orchestrator.py`: builds the flow. A `ParallelAgent` runs Searcher and
  Reader over the sub-questions, a `SequentialAgent` chains Planner, the parallel
  step, Writer and Critic. Planner (B) and Critic (C) are attached with the skip
  callbacks from A4. The Critic can send the report back to the Writer once.
- `tests/test_orchestrator.py`: tests of the structure and of skipping.

## Depends on

A4, A5.

## Commit

One commit when the stage is done:

```
feat: add agent orchestration
```

## Done when

A question goes through the whole flow, and skipping works inside ADK.
