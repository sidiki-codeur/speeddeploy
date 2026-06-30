"""Test suite for SpeedDeploy."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENv_SITE_PACKAGES = ROOT / "venv" / "Lib" / "site-packages"

for candidate in (ROOT, VENv_SITE_PACKAGES):
    candidate_str = str(candidate)
    if candidate.exists() and candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)
