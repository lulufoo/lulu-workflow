"""Cross-tree pytest hooks for lulu-workflow (compose import hygiene)."""

from __future__ import annotations

import subprocess
from pathlib import Path

_ORIG_RUN = subprocess.run
_SUBPROCESS_ALIGNED = False


def _refresh_compose_paths() -> None:
    bootstrap_path = (
        Path(__file__).resolve().parent
        / "compose"
        / "scripts"
        / "tests"
        / "bootstrap.py"
    )
    if not bootstrap_path.is_file():
        return
    import importlib.util

    spec = importlib.util.spec_from_file_location("_lulu_compose_bootstrap", bootstrap_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.refresh_compose_import_paths()


def _run(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Align omitted cwd to --project-root. Explicit cwd is left alone."""
    argv = args[0] if args else kwargs.get("args")
    if kwargs.get("cwd") is None and isinstance(argv, (list, tuple)):
        seq = [str(part) for part in argv]
        if "--project-root" in seq:
            index = seq.index("--project-root")
            if index + 1 < len(seq):
                raw = seq[index + 1]
                if raw and Path(raw).exists():
                    kwargs = dict(kwargs)
                    kwargs["cwd"] = raw
    return _ORIG_RUN(*args, **kwargs)


def pytest_configure(config) -> None:
    global _SUBPROCESS_ALIGNED
    _refresh_compose_paths()
    if not _SUBPROCESS_ALIGNED:
        subprocess.run = _run
        _SUBPROCESS_ALIGNED = True


def pytest_collect_directory(path, parent):
    if path.as_posix().endswith("compose/scripts/tests"):
        _refresh_compose_paths()
    return None
