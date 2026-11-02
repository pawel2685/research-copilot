# arXiv corpus and retrieval (Person B)

Implemented scope: arXiv ingestion, BM25, sentence-transformers embeddings,
persistent ChromaDB and hybrid search. Planner and UI are separate future work.
No Gemini key is required. Run commands from `research-copilot/` after installing
`requirements.txt`.

## Build and query

```powershell
python -m retrieval fetch --query 'cat:cs.CL AND (all:compression OR all:quantization OR all:distillation)' --max-results 100
python -m retrieval index
python -m retrieval search "large language model compression" --mode bm25
python -m retrieval search "kompresja modeli jezykowych" --mode vector
python -m retrieval search "large language model compression" --mode hybrid --top-k 5
```

`fetch` replaces `data/corpus.jsonl` only after a successful nonempty download.
It collects titles, abstracts, authors, dates, versioned IDs and source URLs;
it does **not** download PDF full texts. One title plus abstract is one chunk.
The arXiv client paginates, retries three times and waits at least three seconds
between requests. Keep the JSONL snapshot when comparing experiments because
live API results can change. Different topics can use `--data-dir PATH` before
the subcommand. Downloaded data is excluded from Git.

The first vector operation downloads
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`; later runs use the
local model cache. It supports multilingual queries; BM25 is literal Unicode
word matching without translation or stemming, so English queries fit arXiv best.
The encoder truncates inputs at its model token limit: this initial abstract
retriever does not promise full abstract coverage for unusually long entries.

Embeddings are normalized and indexed with cosine distance. The Chroma collection
name fingerprints the complete corpus and model name. Repeating indexing reuses
existing IDs and resumes missing batches; changing the corpus/model creates a new
collection, so stale papers cannot leak into results. Old collections remain on
disk. Pin a local model snapshot via `Retriever(model_name=...)` for reproducible
model weights. Do not mutate a retriever's corpus after construction.

## Searcher integration

```python
from retrieval import search, Retriever, load_corpus

chunks = search("model quantization", top_k=5, mode="hybrid")
# For repeated calls, load once and reuse:
retriever = Retriever(load_corpus("data/corpus.jsonl"), "data/chroma")
chunks = retriever.search("knowledge distillation", mode="vector")
texts = [chunk["text"] for chunk in chunks]  # input for context.compress()
```

Each result is a JSON-compatible dictionary with `chunk_id`, `arxiv_id`, `title`,
`abstract`, `authors`, `published`, `url`, `text`, `score`, and `mode`.
No shared contracts file is changed. Modes `vector` and `hybrid` permit E0/E1
comparisons using the same corpus. BM25 returns only lexical matches; vector
search returns nearest neighbors even when relevance is weak. Hybrid merges up
to `max(20, 4 * top_k)` candidates per ranking with reciprocal rank fusion
`sum(1 / (60 + rank))`. Scores differ between modes and are not probabilities.
Blank queries and empty corpora return `[]`; invalid mode/top_k raise `ValueError`.
A missing corpus raises `FileNotFoundError` in Python (CLI explains the fetch step).

## Verification

`python -m pytest` runs the existing suite and the retrieval tests, including real
temporary Chroma indexes with deterministic test embeddings. Network ingestion is
mocked in unit tests; live downloads and real model inference are separate smoke
checks. Tests cover citation metadata, BM25 matching, RRF, persistence, corpus
isolation, empty input, invalid arguments and the CLI.

References: [arxiv client](https://lukasschwab.me/arxiv.py/arxiv.html),
[Chroma configuration](https://docs.trychroma.com/docs/collections/configure),
[sentence-transformers](https://sbert.net/docs/package_reference/sentence_transformer/model.html),
[rank_bm25](https://github.com/dorianbrown/rank_bm25).
