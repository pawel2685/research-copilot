"""Validate the project and launch the local ADK Web retrieval demo."""

import os
from pathlib import Path
import subprocess
import sys

from dotenv import load_dotenv
from quality_gate import run_gate


def main() -> int:
    root = Path(__file__).resolve().parent
    os.chdir(root)
    load_dotenv(root / ".env")
    if not os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY") == "your-api-key-here":
        print("Set GOOGLE_API_KEY in .env before starting the Gemini chat demo.")
        return 1
    if not os.getenv("MODEL_LIGHT"):
        print("Set MODEL_LIGHT in .env before starting the demo.")
        return 1
    if not (root / "data" / "corpus.jsonl").exists():
        print("Corpus missing. Run python -m retrieval fetch --query 'cat:cs.CL' first.")
        return 1
    if run_gate() != 0:
        return 1
    print("Open http://127.0.0.1:8000 and select research_demo.", flush=True)
    return subprocess.call([sys.executable, "-m", "google.adk.cli", "web",
                            "--host", "127.0.0.1", "--port", "8000",
                            "--no-reload", "web_agents"])


if __name__ == "__main__":
    sys.exit(main())
