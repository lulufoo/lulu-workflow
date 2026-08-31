"""Flatten eval/scripts and capability folders onto sys.path."""

from __future__ import annotations

import sys
from pathlib import Path

EVAL_SCRIPTS = Path(__file__).resolve().parent
WORKFLOW_ROOT = EVAL_SCRIPTS.parents[1]

_SKIP_DIR_NAMES = frozenset({"tests", "__pycache__"})


def eval_script_layer_dirs(scripts_root: Path | None = None) -> list[Path]:
    """Return scripts root plus first-level capability folders."""
    root = scripts_root or EVAL_SCRIPTS
    children = sorted(
        path
        for path in root.iterdir()
        if path.is_dir()
        and path.name not in _SKIP_DIR_NAMES
        and not path.name.startswith(".")
    )
    return [root, *children]


def ensure_eval_script_layers(scripts_root: Path | None = None) -> None:
    """Put scripts root and each capability folder at the front of sys.path."""
    for path in reversed(eval_script_layer_dirs(scripts_root)):
        text = str(path)
        while text in sys.path:
            sys.path.remove(text)
        sys.path.insert(0, text)
