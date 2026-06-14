"""Entry point so `py speeddeploy ...` works on Windows."""

from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap() -> None:
    root = Path(__file__).resolve().parent.parent
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


_bootstrap()

from speeddeploy.cli import app  # noqa: E402


if __name__ == "__main__":
    app()
