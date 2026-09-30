"""Ensure lulu-exec/scripts is on sys.path for tc_* module imports."""

from __future__ import annotations

import sys
from pathlib import Path

_TECH_CODE_SCRIPTS = Path(__file__).resolve().parents[1]

if str(_TECH_CODE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_TECH_CODE_SCRIPTS))
