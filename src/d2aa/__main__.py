"""Allow ``python -m d2aa`` and act as the PyInstaller entry point."""

from __future__ import annotations

import sys

from .cli import run

if __name__ == "__main__":
    sys.exit(run())
