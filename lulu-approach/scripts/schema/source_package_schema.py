#!/usr/bin/env python3
"""Compatibility import for the shared decision source-package schema."""

import sys
from pathlib import Path

_DECISION_SCRIPTS = Path(__file__).resolve().parents[3] / "decision" / "scripts"
if str(_DECISION_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DECISION_SCRIPTS))

from dec_source_package_schema import (
    PACKAGE_VERSION,
    SOURCE_PACKAGE_FILENAME,
    build_source_package,
    is_source_package_path,
    load_source_package,
    save_source_package,
    validate_source_package,
)
