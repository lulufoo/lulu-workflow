#!/usr/bin/env python3
"""Compatibility re-export of the shared decision-package schema."""

import sys
from pathlib import Path

_DECISION_SCRIPTS = Path(__file__).resolve().parents[3] / "decision" / "scripts"
if str(_DECISION_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DECISION_SCRIPTS))

from dec_decision_package_schema import (  # noqa: E402
    DECISION_PACKAGE_FILENAME,
    PACKAGE_VERSION,
    build_decision_package,
    is_decision_package_path,
    load_decision_package,
    save_decision_package,
    validate_decision_package,
)
