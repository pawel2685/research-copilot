"""Entry point. Always run the app through this file.

- `python main.py` starts the web interface (checks `.env`, builds the paper corpus when
  it is missing, then serves it).
- `python main.py "<question>"` answers one question in the terminal.

Both run the test suite first.
"""

import sys

from agents.pipeline import answer
from launcher import launch_web
from quality_gate import run_gate

USAGE = 'Usage: python main.py "<research question>"   (without a question: web interface)'


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


def main(argv: list[str] | None = None) -> int:
    if run_gate() != 0:
        print("Tests failed or coverage is below the threshold. The app was not started.")
        return 1
    args = sys.argv[1:] if argv is None else argv
    if " ".join(args).strip():
        return run_app(args)
    return launch_web()


if __name__ == "__main__":
    sys.exit(main())
