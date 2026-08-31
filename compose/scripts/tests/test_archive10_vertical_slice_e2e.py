#!/usr/bin/env python3
"""Archive-1.0 critical gates: vertical-slice E2E.

C5: no-split decision-package → project scope-package → convert → L1
    source_path; design-package omits ``order``.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
_WORKFLOW_ROOT = _SCRIPTS.parents[1]
_DESIGN_START = _WORKFLOW_ROOT / "lulu-design" / "scripts" / "start"

for _p in (
    _SCRIPTS,
    _SCRIPTS / "_kernel",
    _SCRIPTS / "schema" / "session",
    _DESIGN_START,
    _WORKFLOW_ROOT / "compose" / "scripts" / "tests",
):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import bootstrap  # noqa: F401
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from compose_package_schema import (  # noqa: E402
    build_compose_package,
    save_compose_package,
    validate_compose_package,
)
from delivered_refs_schema import DeliveredRef  # noqa: E402
from scope_package_convert import (  # noqa: E402
    convert_scope_package,
    resolve_l_seed_source_path,
)
from scope_package_schema import load_scope_package  # noqa: E402
from tech_design_start_adapter import TechDesignStartAdapter  # noqa: E402

_dp_path = (
    _WORKFLOW_ROOT
    / "lulu-approach"
    / "scripts"
    / "schema"
    / "decision_package_schema.py"
)
_dp_spec = importlib.util.spec_from_file_location(
    "_e2e_decision_package_schema",
    _dp_path,
)
assert _dp_spec and _dp_spec.loader
_dp_mod = importlib.util.module_from_spec(_dp_spec)
_dp_spec.loader.exec_module(_dp_mod)
build_decision_package = _dp_mod.build_decision_package
save_decision_package = _dp_mod.save_decision_package


def _unit_doc(path: Path, text: str, *, n_units: int = 1) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    units = [
        {"id": f"U{i}", "slot": f"D.u{i}", "text": f"{text}-{i}"}
        for i in range(1, n_units + 1)
    ]
    path.write_text(
        json.dumps({"version": 1, "gates": {"D": units}}),
        encoding="utf-8",
    )
    return path


def _seed_no_split_approach(tmp_path: Path) -> Path:
    root = tmp_path / "approach"
    root.mkdir()
    _unit_doc(root / "main" / "decision-doc.md", "main pick")
    (root / "main" / "decision-doc.md").write_text("# main\n", encoding="utf-8")
    save_decision_package(
        root,
        build_decision_package(
            main={

                "decision_doc_path": "main/decision-doc.md",
            },
            slices=[],
        ),
    )
    return root


def test_vertical_slice_no_split_e2e(tmp_path: Path) -> None:
    """C5: package → scope-package → convert → L1 Seed = main fact; no order."""
    approach = _seed_no_split_approach(tmp_path)
    pkg_path = approach / "decision-package.json"
    main_doc = (approach / "main" / "decision-doc.md").resolve()

    rev = tmp_path / "design" / "revision1"
    rev.mkdir(parents=True)
    adapter = TechDesignStartAdapter()
    scope_refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(
                type="lulu-approach",
                path=str(pkg_path.resolve()),
                artifact="decision-package",
            )
        ],
        revision_dir=rev,
    )
    assert len(scope_refs) == 1
    assert scope_refs[0].artifact == "scope-package"
    scope_path = Path(scope_refs[0].path)
    assert scope_path == rev / "scope-package.json"

    # Projection also available as direct helper (same path write-once).
    loaded = load_scope_package(scope_path)
    assert "order" not in loaded
    assert [s["id"] for s in loaded["slices"]] == ["L1"]
    assert loaded["slices"][0]["source_path"] == str(main_doc)
    assert loaded["slices"][0]["source_id"] == "main"

    convert_scope_package(rev, scope_package_path=scope_path)
    assert resolve_l_seed_source_path(rev, "L1") == str(main_doc)

    l1 = rev / "L1"
    (l1 / "design-doc.md").write_text("# L1 design\n", encoding="utf-8")
    design_pkg = build_compose_package(
        profile_id="lulu-design",
        slices=[{"id": "L1", "title": "Main", "doc_path": "L1/design-doc.md"}],
    )
    assert "order" not in design_pkg
    assert validate_compose_package(design_pkg) == []
    out = save_compose_package(rev, "design-package.json", design_pkg)
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert "order" not in saved
    assert [s["id"] for s in saved["slices"]] == ["L1"]
