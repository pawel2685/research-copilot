"""Entry point. Always run the app through this file: `python main.py`."""

import sys

from quality_gate import run_gate


def run_app() -> int:
    print("Research Copilot: agents are not implemented yet.")
    return 0


def main() -> int:
    if run_gate() != 0:
        print("Tests failed or coverage is below the threshold. The app was not started.")
        return 1
    return run_app()


if __name__ == "__main__":
    sys.exit(main())
