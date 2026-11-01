"""ADK tools backed by the local retrieval corpus."""

import asyncio
from threading import Lock

from retrieval import Retriever, load_corpus
from retrieval.search import DEFAULT_DATA

_lock = Lock()
_cached = None
_signature = None


def _search(query: str, mode: str, top_k: int) -> dict:
    global _cached, _signature
    if not query.strip():
        return {"status": "error", "message": "Enter a nonempty research query."}
    if mode not in {"bm25", "vector", "hybrid"} or type(top_k) is not int or not 1 <= top_k <= 10:
        return {"status": "error", "message": "Use bm25, vector or hybrid and top_k from 1 to 10."}
    try:
        with _lock:
            corpus = DEFAULT_DATA / "corpus.jsonl"
            stat = corpus.stat()
            signature = (str(corpus), stat.st_mtime_ns, stat.st_size)
            if _cached is None or signature != _signature:
                _cached = Retriever(load_corpus(corpus), DEFAULT_DATA / "chroma")
                _signature = signature
            results = _cached.search(query, top_k, mode)
            return {"status": "success", "query": query, "mode": mode,
                    "corpus_size": len(_cached.papers), "count": len(results),
                    "scope": "Titles and abstracts only, not full papers.",
                    "results": results}
    except FileNotFoundError:
        return {"status": "error", "message": "Corpus missing. Run python -m retrieval fetch first."}
    except Exception:
        # Do not expose environment paths or remote request details to the model.
        import logging
        logging.getLogger(__name__).exception("Local retrieval failed")
        return {"status": "error", "message": "Search failed. Check the server log and run python -m retrieval index. You can also try bm25."}


async def search_papers(query: str, mode: str = "hybrid", top_k: int = 5) -> dict:
    """Search the local arXiv corpus and return ranked abstracts with citations.

    Args:
        query: Research topic or keywords. English works best for BM25.
        mode: Retrieval method: bm25, vector or hybrid (default).
        top_k: Number of papers to return, between 1 and 10 (default 5).
    """
    return await asyncio.to_thread(_search, query, mode, top_k)
