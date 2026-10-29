# A2: Stubs

Status: done.

Goal: a stand-in for the search function that B is building, so the pipeline and the
evaluation can run without it.

## Files

### `stubs/sample_chunks.json`

A JSON list of five passages. Each item has the same four fields as `Chunk`:
`paper_id`, `text`, `score` (always `0.0` in the file) and `source_url`. There is one
passage per paper used in `evals/questions.py`, in this order:

- `2005.11401`: retrieval-augmented generation combines a parametric language model
  with a non-parametric memory.
- `1706.03762`: the Transformer is based solely on attention, without recurrence and
  convolutions.
- `1810.04805`: BERT pre-trains deep bidirectional representations.
- `2106.09685`: LoRA freezes the model weights and trains low-rank matrices.
- `2201.11903`: chain-of-thought prompting uses examples with intermediate reasoning
  steps.

Every `source_url` is `https://arxiv.org/abs/<paper_id>`. The passages are short
paraphrases written for the stub, not quotes from the papers.

### `stubs/search.py`

Read top to bottom:

- **Module docstring.** Says the module stands in for the real retrieval.
- **`_FIXTURE`.** The path of `sample_chunks.json`, next to the module.
- **`_STOPWORDS`.** A frozen set of 23 common words (`the`, `of`, `how`, `what`, ...)
  that are ignored when comparing words.
- **`_load_chunks()`.** Reads the JSON file once (the result is cached) and returns a
  tuple of `Chunk` objects.
- **`_words(text)`.** Lowercases the text, splits it into letters and digits (so
  `low-rank` becomes `low` and `rank`), and removes the stop words. Returns a set.
- **`search(query, k=8, hybrid=True)`.** The function that fits `SearchFn`:
  1. Takes the words of the query.
  2. For each passage, the score is the number of words it shares with the query.
  3. Keeps only passages with a score above zero, as copies of the chunk with the
     `score` field set (the cached chunks are never modified).
  4. Sorts them by score, best first. Passages with equal scores keep the order from
     the file.
  5. Returns at most `k` of them.

  `hybrid` is accepted to match the contract and is ignored. A query that shares no
  words with any passage returns an empty list.

### `tests/test_stub_search.py`

Eight tests, top to bottom:

- `search` returns `Chunk` objects for `language model`.
- The best match comes first: `low-rank matrices` returns `2106.09685` first.
- The scores are not increasing along the result list.
- `k=1` returns exactly one result.
- A query with no match (`zzz`) returns an empty list.
- The `hybrid` flag does not change the result.
- Every `source_url` is the arXiv link of its `paper_id`.
- The stub fits the `SearchFn` contract: `attention` with `k=1` returns `1706.03762`.

## Commit

```
feat: add search stub
```
