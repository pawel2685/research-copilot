"""Quality gate: the test suite must pass with enough coverage before the app starts.

The threshold itself lives in pyproject.toml (`fail_under`).
"""

import subprocess
import sys


def run_gate() -> int:
    """Run pytest with coverage and return its exit code (0 means the gate passed)."""
    return subprocess.run([sys.executable, "-m", "pytest"]).returncode
