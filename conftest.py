"""Cross-tree pytest hooks for lulu-dev-workflow (shared module name hygiene)."""

from __future__ import annotations

import sys
from pathlib import Path


def _refresh_compose_paths() -> None:
    bootstrap_path = (
        Path(__file__).resolve().parent
        / "compose-kernel"
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


def _refresh_tech_code_paths() -> None:
    scripts = Path(__file__).resolve().parent / "tech-code" / "scripts"
    if not scripts.is_dir():
        return
    compose_tests = (
        Path(__file__).resolve().parent
        / "compose-kernel"
        / "scripts"
        / "tests"
        / "bootstrap.py"
    )
    if compose_tests.is_file():
        import importlib.util

        spec = importlib.util.spec_from_file_location("_lulu_compose_bootstrap", compose_tests)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod._deprioritize_other_stage_paths()
        mod._purge_stale_modules()
    entry = str(scripts)
    while entry in sys.path:
        sys.path.remove(entry)
    sys.path.insert(0, entry)
    for name in (
        "workflow_common",
        "workflow_state_schema",
        "session_state_schema",
        "session_control",
    ):
        mod = sys.modules.get(name)
        if mod is None:
            continue
        mod_file = getattr(mod, "__file__", None)
        if not mod_file:
            del sys.modules[name]
            continue
        try:
            Path(mod_file).resolve().relative_to(scripts.resolve())
        except ValueError:
            del sys.modules[name]


def pytest_configure(config) -> None:
    _refresh_compose_paths()


def pytest_collect_directory(path, parent):
    path_str = path.as_posix()
    if path_str.endswith("compose-kernel/scripts/tests"):
        _refresh_compose_paths()
    elif path_str.endswith("tech-code/scripts"):
        _refresh_tech_code_paths()
    return None
