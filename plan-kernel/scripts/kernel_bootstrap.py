"""Insert plan-kernel core + section directories onto sys.path."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_CORE = _SCRIPTS / "core"
_SECTION = _SCRIPTS / "section"


def ensure_kernel_paths() -> None:
    for p in (_SCRIPTS, _CORE, _SECTION):
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)
