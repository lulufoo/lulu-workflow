#!/usr/bin/env python3
"""lulu-design corpus identity constants. Eval loads ComposeEvalAdapter + contributor."""

from __future__ import annotations

import sys
from pathlib import Path

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_KERNEL_CORE = _WORKFLOW_ROOT / "compose" / "scripts" / "core"
if str(_KERNEL_CORE) not in sys.path:
    sys.path.insert(0, str(_KERNEL_CORE))

from compose_corpus_versions import compose_corpus_ref  # noqa: E402

TECH_DESIGN_COMPOSED_CORPUS_ID = "lulu-design-composed"
TECH_DESIGN_COMPOSED_CORPUS_VERSION = "3"
TECH_DESIGN_COMPOSED_CORPUS_REF = compose_corpus_ref("lulu-design")
