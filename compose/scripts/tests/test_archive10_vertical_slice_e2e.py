#!/usr/bin/env python3
"""Archive-1.0 critical gates: vertical-slice E2E + M11 anti-whole-package Seed.

C5: no-split decision-package → project scope-package → convert → Seed L1 =
    main fact; design-package omits ``order``.

C6: M11-style synthetic corpus — multi-L scope with a fat upstream fact must
    never Seed-absorb the whole package / sibling L facts.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
_WORKFLOW_ROOT = _SCRIPTS.parents[1]
_INDUCTIVE = _SCRIPTS / "inductive"
_SECTION_CTL = _INDUCTIVE / "inductive_g3_section_control.py"
_DESIGN_START = _WORKFLOW_ROOT / "lulu-design" / "scripts" / "start"

for _p in (
    _SCRIPTS,
    _SCRIPTS / "core",
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
    resolve_l_seed_fact_path,
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


def _unit_fact(path: Path, text: str, *, n_units: int = 1) -> Path:
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
    _unit_fact(root / "main" / "decision-fact.json", "main pick")
    (root / "main" / "decision-doc.md").write_text("# main\n", encoding="utf-8")
    save_decision_package(
        root,
        build_decision_package(
            main={
                "decision_fact_path": "main/decision-fact.json",
                "decision_doc_path": "main/decision-doc.md",
            },
            slices=[],
        ),
    )
    return root


def _run_seed(out_dir: Path, *args: str) -> tuple[int, dict]:
    res = subprocess.run(
        [sys.executable, str(_SECTION_CTL), "--out-dir", str(out_dir), *args],
        capture_output=True,
        text=True,
    )
    try:
        payload = json.loads(res.stdout)
    except json.JSONDecodeError:
        payload = {"ok": False, "raw": res.stdout, "stderr": res.stderr}
    return res.returncode, payload


def _init_pointer(out_dir: Path) -> None:
    code, payload = _run_seed(
        out_dir, "init-pointer", "--sections", "I,ST", "--mandatory", ""
    )
    assert code == 0, payload
    code, payload = _run_seed(out_dir, "activate-section", "--section", "I")
    assert code == 0, payload


def test_vertical_slice_no_split_e2e(tmp_path: Path) -> None:
    """C5: package → scope-package → convert → L1 Seed = main fact; no order."""
    approach = _seed_no_split_approach(tmp_path)
    pkg_path = approach / "decision-package.json"
    main_fact = (approach / "main" / "decision-fact.json").resolve()

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
    assert loaded["slices"][0]["fact_path"] == str(main_fact)
    assert loaded["slices"][0]["source_id"] == "main"

    convert_scope_package(rev, scope_package_path=scope_path)
    assert resolve_l_seed_fact_path(rev, "L1") == str(main_fact)

    l1 = rev / "L1"
    _init_pointer(l1)
    code, payload = _run_seed(
        l1,
        "seed-decision",
        "--section",
        "I",
        "--lens-tags",
        "I",
        "--text",
        "main pick-1",
    )
    assert code == 0, payload
    facts = json.loads((l1 / "_facts.json").read_text(encoding="utf-8"))
    refs = facts[0]["origin"]["ref"]
    assert str(main_fact) in refs
    assert "scope-package" not in "".join(refs)
    assert "decision-package" not in "".join(refs)

    # design-package / compose package: slices SSOT, no order field.
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


def test_m11_seed_does_not_absorb_whole_package(tmp_path: Path) -> None:
    """C6: fat upstream fact + sibling L — Seed L1 only sees L1 fact_path.

    Synthetic stand-in for corpus feature-20260724105005-345eefe1 (M11):
    a many-unit approach fact must not be absorbed wholesale when Seed runs
    under a multi-L scope-package.
    """
    approach = tmp_path / "approach"
    # Poison: 40-unit "whole package" fact that must never be Seed origin.
    whole = _unit_fact(approach / "whole" / "decision-fact.json", "WHOLE", n_units=40)
    f1 = _unit_fact(approach / "D1" / "decision-fact.json", "auth", n_units=2)
    f2 = _unit_fact(approach / "D2" / "decision-fact.json", "billing", n_units=3)

    rev = tmp_path / "design" / "revision1"
    rev.mkdir(parents=True)
    # Project via adapter path would need a real decision-package; here we
    # write the scope-package that StartAdapter would emit after projection.
    from scope_package_schema import build_scope_package, save_scope_package

    pkg = build_scope_package(
        slices=[
            {
                "id": "L1",
                "title": "Auth",
                "fact_path": str(f1.resolve()),
                "source_id": "D1",
            },
            {
                "id": "L2",
                "title": "Billing",
                "fact_path": str(f2.resolve()),
                "source_id": "D2",
            },
        ]
    )
    scope_path = save_scope_package(rev, pkg)
    # Place the poison whole-fact path into revision resolved index temptation.
    convert_scope_package(rev, scope_package_path=scope_path)

    assert resolve_l_seed_fact_path(rev, "L1") == str(f1.resolve())
    assert resolve_l_seed_fact_path(rev, "L2") == str(f2.resolve())

    l1 = rev / "L1"
    _init_pointer(l1)
    index_path = l1 / "inductive-scope" / "_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    # Tempt Seed with whole-package + scope-package paths in index.
    index["scope_ref"] = str(whole.resolve())
    index_path.write_text(json.dumps(index), encoding="utf-8")

    code, payload = _run_seed(
        l1,
        "seed-decision",
        "--section",
        "I",
        "--lens-tags",
        "I",
        "--text",
        "auth-1",
    )
    assert code == 0, payload
    facts = json.loads((l1 / "_facts.json").read_text(encoding="utf-8"))
    refs = "".join(facts[0]["origin"]["ref"])
    assert str(f1.resolve()) in refs
    assert str(whole.resolve()) not in refs
    assert str(f2.resolve()) not in refs
    assert scope_path.name not in refs
    # Unit-count gate: L1 fact has 2 units — Seed must not pull 40-unit whole.
    whole_units = json.loads(whole.read_text(encoding="utf-8"))["gates"]["D"]
    assert len(whole_units) == 40
    seeded_text = json.dumps(facts)
    assert "WHOLE-" not in seeded_text
