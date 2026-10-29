# A9: Evaluation hand-off

Status: to do.

Goal: C can run the experiments E0 to E4 on the real pipeline.

## Planned files

- `evals/experiment_configs.py`: maps each of E0 to E4 to a `RunConfig`.
- `tests/test_experiment_configs.py`: tests of the mapping.

C then runs the harness on the real pipeline, and A fixes what it finds.

## Depends on

A7.

## Commit

One commit when the stage is done:

```
feat: add experiment configs
```

## Done when

All five configurations run and produce results.
