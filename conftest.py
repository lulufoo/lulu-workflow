"""Cross-tree pytest hooks for lulu-workflow (compose import hygiene)."""

from __future__ import annotations

from pathlib import Path


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


def pytest_configure(config) -> None:
    _refresh_compose_paths()


def pytest_collect_directory(path, parent):
    if path.as_posix().endswith("compose/scripts/tests"):
        _refresh_compose_paths()
    return None
