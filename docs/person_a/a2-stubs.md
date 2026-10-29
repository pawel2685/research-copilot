# A2: Stubs

Status: to do.

Goal: a stand-in for the search function B is still building, so the pipeline and
the evaluation can run without waiting.

## Planned files

- `stubs/search.py`: a fake `search(query, k, hybrid)` that ranks a few saved passages
  by simple word overlap with the query and returns `Chunk` objects.
- `stubs/sample_chunks.json`: the saved passages, with arXiv-style ids.
- `tests/test_stub_search.py`: tests of the stub.

## Depends on

A1.

## Commit

One commit when the stage is done:

```
feat: add search stub
```

## Done when

`search("some query")` returns `Chunk` objects ranked by the rule, and the tests pass.
