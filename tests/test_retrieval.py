from datetime import datetime, timezone
from types import SimpleNamespace

import numpy as np
import pytest

from retrieval import Paper, Retriever, fetch_papers, load_corpus, save_corpus, search
from retrieval.__main__ import main


@pytest.fixture
def papers():
    return [Paper("1v1", "Quantization", "Compress neural weights", ["A"], "2024", "https://arxiv.org/abs/1v1"),
            Paper("2v1", "Galaxies", "Stars in space", ["B"], "2024", "https://arxiv.org/abs/2v1"),
            Paper("3v1", "Distillation", "Small student neural model", ["C"], "2024", "https://arxiv.org/abs/3v1")]


class Encoder:
    """Deterministic vectors to test real Chroma without downloading weights."""
    def encode(self, texts, **kwargs):
        return np.array([[1., 0., 0.] if "Quantization" in t or "compression" in t
                         else [0., 1., 0.] if "Galaxies" in t else [0., 0., 1.]
                         for t in texts])


def test_corpus_and_bm25(tmp_path, papers):
    save_corpus(papers, tmp_path / "corpus.jsonl")
    assert load_corpus(tmp_path / "corpus.jsonl") == papers
    result = search("QUANTIZATION!", mode="bm25", data_dir=tmp_path)
    assert result[0]["arxiv_id"] == "1v1"
    assert result[0]["chunk_id"] == "1v1:abstract"
    assert "Compress" in result[0]["text"]
    retriever = Retriever(papers, tmp_path)
    assert retriever.search("unmatched", mode="bm25") == []
    assert retriever.search("   ") == []
    assert Retriever([], tmp_path).search("query") == []
    Retriever([], tmp_path).build_vectors()
    for kwargs in ({"mode": "wrong"}, {"top_k": 0}, {"top_k": True}):
        with pytest.raises(ValueError):
            retriever.search("query", **kwargs)
    with pytest.raises(ValueError, match="Duplicate"):
        Retriever(papers + papers, tmp_path)
    with pytest.raises(ValueError, match="searchable"):
        Retriever([Paper("x", "", "", [], "", "")], tmp_path)


def test_vector_hybrid_persistence_and_isolation(tmp_path, papers):
    retriever = Retriever(papers, tmp_path, encoder=Encoder())
    assert retriever.search("compression", mode="vector")[0]["arxiv_id"] == "1v1"
    results = retriever.search("Quantization", mode="hybrid", top_k=100)
    assert results[0]["arxiv_id"] == "1v1"
    assert results[0]["score"] == pytest.approx(2 / 61)
    assert len(results) == 3
    again = Retriever(papers, tmp_path, encoder=Encoder())
    again.build_vectors()
    assert again.collection.count() == 3
    assert again.search("compression", mode="vector", top_k=1)[0]["arxiv_id"] == "1v1"
    changed = Retriever(papers[1:], tmp_path, encoder=Encoder())
    assert changed.collection_name != again.collection_name
    assert all(r["arxiv_id"] != "1v1" for r in changed.search("compression"))
    assert Retriever(papers, tmp_path, model_name="other").collection_name != again.collection_name


def test_lazy_encoder(tmp_path, papers, monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "sentence_transformers",
                        SimpleNamespace(SentenceTransformer=lambda name: Encoder()))
    assert Retriever(papers, tmp_path)._encode(["compression"]) == [[1., 0., 0.]]


def test_arxiv_mapping_and_validation(monkeypatch):
    import arxiv
    result = SimpleNamespace(get_short_id=lambda: "1234.5678v2", title="Some\n title",
                             summary="An  abstract", authors=[SimpleNamespace(name="Author")],
                             published=datetime(2024, 1, 1, tzinfo=timezone.utc),
                             entry_id="http://arxiv.org/abs/1234.5678v2")
    captured = {}
    def client(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(results=lambda request: iter([result, result]))
    monkeypatch.setattr(arxiv, "Client", client)
    papers = fetch_papers("cat:cs.CL", 2)
    assert len(papers) == 1
    assert papers[0].title == "Some title"
    assert papers[0].url.startswith("https://")
    assert captured["delay_seconds"] >= 3
    for query, limit in [(" ", 1), ("x", 0)]:
        with pytest.raises(ValueError):
            fetch_papers(query, limit)


def test_cli(tmp_path, papers, monkeypatch, capsys):
    import importlib
    cli = importlib.import_module("retrieval.__main__")
    prefix = ["--data-dir", str(tmp_path)]
    with pytest.raises(SystemExit):
        main(prefix + ["index"])
    monkeypatch.setattr(cli, "fetch_papers", lambda *args: papers)
    main(prefix + ["fetch", "--query", "cat:cs.CL"])
    main(prefix + ["search", "quantization", "--mode", "bm25"])
    assert '"arxiv_id": "1v1"' in capsys.readouterr().out
    monkeypatch.setattr(cli, "Retriever", lambda p, d: Retriever(p, d, encoder=Encoder()))
    main(prefix + ["index"])
    assert "Indexed 3" in capsys.readouterr().out
    monkeypatch.setattr(cli, "fetch_papers", lambda *args: [])
    with pytest.raises(SystemExit):
        main(prefix + ["fetch", "--query", "empty"])
    assert load_corpus(tmp_path / "corpus.jsonl") == papers
