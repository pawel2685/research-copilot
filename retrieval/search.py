"""BM25, dense and reciprocal-rank-fusion retrieval over the same corpus."""

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re

from rank_bm25 import BM25Okapi

from .corpus import Paper, load_corpus

DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_DATA = Path(__file__).resolve().parents[1] / "data"


def tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.casefold())


class Retriever:
    """One abstract per chunk; lazy embeddings, with a persistent Chroma cache.

    Pass an encoder implementing encode(texts, **kwargs) in offline tests.
    A corpus/model fingerprint isolates changed corpora from old vector indexes.
    """

    def __init__(self, papers: list[Paper], persist_directory: str | Path,
                 model_name: str = DEFAULT_MODEL, encoder=None):
        self.papers = list(papers)
        ids = [p.arxiv_id for p in papers]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate arXiv IDs in corpus")
        if any(not tokenize(p.text) for p in papers):
            raise ValueError("Papers must contain searchable text")
        self.tokens = [tokenize(p.text) for p in papers]
        self.bm25 = BM25Okapi(self.tokens) if papers else None
        self.persist_directory = str(persist_directory)
        self.model_name = model_name
        self.encoder = encoder
        self.collection = None
        payload = json.dumps([model_name, [asdict(p) for p in papers]], sort_keys=True)
        self.collection_name = "arxiv-" + hashlib.sha256(payload.encode()).hexdigest()[:32]

    def _encode(self, texts):
        if self.encoder is None:
            from sentence_transformers import SentenceTransformer
            self.encoder = SentenceTransformer(self.model_name)
        return self.encoder.encode(texts, normalize_embeddings=True,
                                   show_progress_bar=False).tolist()

    def build_vectors(self) -> None:
        if not self.papers or self.collection is not None:
            return
        import chromadb

        client = chromadb.PersistentClient(path=self.persist_directory)
        collection = client.get_or_create_collection(
            self.collection_name, embedding_function=None,
            configuration={"hnsw": {"space": "cosine"}})
        existing = set(collection.get(include=[])["ids"])
        missing = [p for p in self.papers if p.arxiv_id not in existing]
        for start in range(0, len(missing), 64):
            batch = missing[start:start + 64]
            collection.upsert(ids=[p.arxiv_id for p in batch],
                              embeddings=self._encode([p.text for p in batch]))
        self.collection = collection

    def search(self, query: str, top_k: int = 5, mode: str = "hybrid") -> list[dict]:
        """Return JSON-compatible chunks with citation metadata and scores.

        Scores are BM25, cosine similarity or RRF (k=60), depending on mode.
        They are ranking signals, not confidence probabilities.
        """
        if mode not in {"bm25", "vector", "hybrid"}:
            raise ValueError("mode must be bm25, vector or hybrid")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
            raise ValueError("top_k must be a positive integer")
        query_tokens = tokenize(query)
        if not query_tokens or not self.papers:
            return []
        count = min(len(self.papers), max(top_k * 4, 20))
        lexical, dense = [], []
        if mode != "vector":
            scores = self.bm25.get_scores(query_tokens)
            # Keep actual matches even when Okapi IDF is zero/negative in tiny corpora.
            lexical = sorted(((p.arxiv_id, float(scores[i]))
                              for i, p in enumerate(self.papers)
                              if set(query_tokens).intersection(self.tokens[i])),
                             key=lambda item: (-item[1], item[0]))[:count]
        if mode != "bm25":
            self.build_vectors()
            result = self.collection.query(query_embeddings=self._encode([query]),
                                           n_results=count, include=["distances"])
            dense = [(key, 1.0 - float(distance)) for key, distance in
                     zip(result["ids"][0], result["distances"][0])]
        if mode == "hybrid":
            fused = {}
            for ranking in (lexical, dense):
                for rank, (key, _) in enumerate(ranking, 1):
                    fused[key] = fused.get(key, 0.0) + 1.0 / (60 + rank)
            ranking = sorted(fused.items(), key=lambda item: (-item[1], item[0]))
        else:
            ranking = lexical if mode == "bm25" else dense
        lookup = {p.arxiv_id: p for p in self.papers}
        return [dict(asdict(lookup[key]), chunk_id=f"{key}:abstract",
                     text=lookup[key].text, score=score, mode=mode)
                for key, score in ranking[:top_k]]


def search(query: str, top_k: int = 5, mode: str = "hybrid",
           data_dir: str | Path = DEFAULT_DATA) -> list[dict]:
    """Convenience entry point; keep a Retriever instance for repeated queries."""
    data_dir = Path(data_dir)
    return Retriever(load_corpus(data_dir / "corpus.jsonl"), data_dir / "chroma").search(
        query, top_k, mode)
