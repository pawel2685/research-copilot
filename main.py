"""Entry point. Always run the app through this file: `python main.py "<question>"`."""

import sys

from agents.pipeline import answer
from quality_gate import run_gate

USAGE = 'Usage: python main.py "<research question>"'


def run_app(argv: list[str] | None = None) -> int:
    question = " ".join(sys.argv[1:] if argv is None else argv).strip()
    if not question:
        print(USAGE)
        return 2

    try:
        report = answer(question)
    except RuntimeError as error:  # for example a model name missing in .env
        print(f"Error: {error}")
        return 1
    print(report.markdown)
    print()
    print(f"Verified: {'yes' if report.verified else 'no'}")
    return 0


def main() -> int:
    if run_gate() != 0:
        print("Tests failed or coverage is below the threshold. The app was not started.")
        return 1
    return run_app()


if __name__ == "__main__":
    sys.exit(main())
