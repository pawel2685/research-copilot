"""Starts the web interface: checks `.env`, prepares the paper corpus, runs `adk web`.

Used by `python main.py` when it is started without a question.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
HOST = "127.0.0.1"
PORT = "8000"
AGENTS_DIR = "demo"

# Titles of the five papers behind the evaluation questions (`evals/questions.py`), so
# the metrics can find the expected sources. Other papers with similar titles come with
# them, which is fine.
CORPUS_QUERY = (
    'ti:"Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"'
    ' OR ti:"Attention Is All You Need"'
    ' OR ti:"BERT: Pre-training of Deep Bidirectional Transformers"'
    ' OR ti:"LoRA: Low-Rank Adaptation of Large Language Models"'
    ' OR ti:"Chain-of-Thought Prompting Elicits Reasoning in Large Language Models"'
)

_KEY_PLACEHOLDER = "your-api-key-here"


def config_problems() -> list[str]:
    """What is missing in the local `.env`, as readable messages. Empty when all is set."""
    load_dotenv(ROOT / ".env")
    problems = []
    key = os.getenv("GOOGLE_API_KEY", "")
    if not key or key == _KEY_PLACEHOLDER:
        problems.append("GOOGLE_API_KEY is missing in .env")
    for name in ("MODEL_LIGHT", "MODEL_HEAVY"):
        if not os.getenv(name):
            problems.append(f"{name} is missing in .env")
    return problems


def _retrieval(data_dir: Path, *args: str) -> int:
    """Run `python -m retrieval ...`. The query is passed as one argument, so it needs
    no shell quoting."""
    command = [sys.executable, "-m", "retrieval", "--data-dir", str(data_dir), *args]
    return subprocess.run(command, cwd=ROOT).returncode


def ensure_corpus(data_dir: Path = DATA_DIR) -> int:
    """Fetch the corpus and build the vector index when they are missing.

    Returns 0 when both exist at the end. Nothing is downloaded when they are there.
    """
    if not (data_dir / "corpus.jsonl").exists():
        print("The paper corpus is missing. Fetching it from arXiv...", flush=True)
        if _retrieval(data_dir, "fetch", "--query", CORPUS_QUERY, "--max-results", "100"):
            return 1
    if not (data_dir / "chroma").exists():
        print(
            "Building the vector index (the first run downloads the embedding model)...",
            flush=True,
        )
        if _retrieval(data_dir, "index"):
            return 1
    return 0


def launch_web() -> int:
    """Check the configuration, prepare the corpus and serve the web interface."""
    problems = config_problems()
    if problems:
        for problem in problems:
            print(f"Error: {problem}")
        print("Fill in .env as described in the README (step 4).")
        return 1
    if ensure_corpus() != 0:
        print("Error: the paper corpus could not be prepared.")
        return 1
    print(f"Open http://{HOST}:{PORT} and select research_copilot. Stop with Ctrl+C.", flush=True)
    command = [
        sys.executable,
        "-m",
        "google.adk.cli",
        "web",
        "--host",
        HOST,
        "--port",
        PORT,
        "--no-reload",
        AGENTS_DIR,
    ]
    try:
        return subprocess.call(command, cwd=ROOT)
    except KeyboardInterrupt:
        return 0
