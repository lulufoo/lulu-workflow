"""Load profile-specific draft_control without sys.modules name collisions."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_SIBLING_MODULES = ("drafting_progress_schema",)


def _clear_shadowed_siblings(drafting_dir: Path) -> None:
    """Drop cached sibling modules that belong to another profile drafting dir."""
    drafting_dir = drafting_dir.resolve()
    for name in _SIBLING_MODULES:
        mod = sys.modules.get(name)
        mod_file = getattr(mod, "__file__", None)
        if mod is not None and mod_file:
            if Path(mod_file).resolve().parent != drafting_dir:
                del sys.modules[name]


def load_draft_control(drafting_dir: Path, *, module_name: str) -> ModuleType:
    """Import draft_control.py from *drafting_dir* under a unique module name."""
    drafting_dir = drafting_dir.resolve()
    path = drafting_dir / "draft_control.py"
    if module_name in sys.modules:
        existing = sys.modules[module_name]
        if getattr(existing, "__file__", None) == str(path):
            return existing

    _clear_shadowed_siblings(drafting_dir)

    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load draft_control from {path}")

    saved_path = list(sys.path)
    sys.path.insert(0, str(drafting_dir))
    try:
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path[:] = saved_path
