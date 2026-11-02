"""Run with python -m retrieval fetch|index|search."""

import argparse
import json
from pathlib import Path

from .corpus import fetch_papers, load_corpus, save_corpus
from .search import DEFAULT_DATA, Retriever


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    commands = parser.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser("fetch")
    fetch.add_argument("--query", required=True)
    fetch.add_argument("--max-results", type=int, default=100)
    commands.add_parser("index")
    search = commands.add_parser("search")
    search.add_argument("query")
    search.add_argument("--mode", choices=["bm25", "vector", "hybrid"], default="hybrid")
    search.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args(argv)
    corpus = args.data_dir / "corpus.jsonl"
    if args.command == "fetch":
        papers = fetch_papers(args.query, args.max_results)
        if not papers:
            parser.error("arXiv returned no papers; the existing corpus was preserved")
        save_corpus(papers, corpus)
        print(f"Saved {len(papers)} papers to {corpus}")
    else:
        if not corpus.exists():
            parser.error("Corpus is missing. Run the fetch command first.")
        retriever = Retriever(load_corpus(corpus), args.data_dir / "chroma")
        if args.command == "index":
            retriever.build_vectors()
            print(f"Indexed {len(retriever.papers)} papers")
        else:
            print(json.dumps(retriever.search(args.query, args.top_k, args.mode),
                             ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
