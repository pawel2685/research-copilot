# A2: Stubs, implementation plan

Status: done. The code is written, the tests pass and the documentation is in
`docs/person_a/a2-stubs.md`.

## Goal

A stand-in for the search function B is building, so the pipeline and the evaluation
can run without it.

## Files (already created)

- `stubs/sample_chunks.json`: five passages, one per paper used in
  `evals/questions.py` (ids `2005.11401`, `1706.03762`, `1810.04805`, `2106.09685`,
  `2201.11903`).
- `stubs/search.py`: `search(query, k=8, hybrid=True) -> list[Chunk]`. Ranks passages
  by the number of words shared with the query (stop words ignored), keeps only
  passages with a score above zero, best first. `hybrid` is ignored.
- `tests/test_stub_search.py`: eight tests.

## Steps

1. Run `python -m pytest`. All tests must pass with coverage of at least 80%.
2. Rewrite `docs/person_a/a2-stubs.md` as documentation of the three files above,
   top to bottom (see "When a stage is finished" in the
   [index](README.md)). Set the status to `done`.
3. Set A2 to `done` in the table in `docs/person_a/README.md`.
4. Print the commit message below.

## Commit message

```
feat: add search stub
```
