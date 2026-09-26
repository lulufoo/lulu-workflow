"""Tests for archive-1.0 P4.antiseep (Seed uses L-local fact_path mirror only)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]

if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from l_ledger_schema import load_l_ledger, save_l_ledger  # noqa: E402
from scope_package_convert import (  # noqa: E402
    ScopePackageAntiseepError,
    convert_scope_package,
    focus_seed_source_path,
    resolve_l_seed_source_path,
    seed_source_path_for_out_dir,
)
from scope_package_schema import (  # noqa: E402
    build_scope_package,
    save_scope_package,
    write_scope_ref_mirror,
)


def _pkg_multi(f1: str, f2: str) -> dict:
    return build_scope_package(
        slices=[
            {"id": "L1", "title": "Auth", "source_path": f1, "source_id": "D1"},
            {"id": "L2", "title": "Billing", "source_path": f2, "source_id": "D2"},
        ]
    )


def test_resolve_l_seed_source_path_uses_mirror(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    f1 = "/abs/D1/decision-doc.md"
    f2 = "/abs/D2/decision-doc.md"
    pkg_path = save_scope_package(rev, _pkg_multi(f1, f2))
    convert_scope_package(rev, scope_package_path=pkg_path)

    assert resolve_l_seed_source_path(rev, "L1") == f1
    assert resolve_l_seed_source_path(rev, "L2") == f2
    assert load_l_ledger(rev)["focus"] == "L1"
    assert focus_seed_source_path(rev) == f1


def test_missing_mirror_fails_without_package_fallback(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    f1 = "/abs/D1/decision-doc.md"
    f2 = "/abs/D2/decision-doc.md"
    pkg_path = save_scope_package(rev, _pkg_multi(f1, f2))
    convert_scope_package(rev, scope_package_path=pkg_path)
    (rev / "L1" / "scope-ref.json").unlink()

    with pytest.raises(ScopePackageAntiseepError, match="missing L source_path mirror"):
        resolve_l_seed_source_path(rev, "L1")
    with pytest.raises(ScopePackageAntiseepError, match="missing L source_path mirror"):
        focus_seed_source_path(rev)
    with pytest.raises(ScopePackageAntiseepError, match="missing L source_path mirror"):
        seed_source_path_for_out_dir(rev / "L1")


def test_seed_source_path_for_out_dir_none_without_contract(tmp_path: Path) -> None:
    out = tmp_path / "plain"
    out.mkdir()
    assert seed_source_path_for_out_dir(out) is None


def test_begin_inductive_scope_ref_is_l_mirror_fact_path(tmp_path: Path) -> None:
    """enter-inductive SCOPE_REF and SOURCE_PATH = L mirror source_path, not package."""
    import bootstrap  # noqa: F401
    import l_step_control  # noqa: E402
    from delivered_refs_schema import DeliveredRef  # noqa: E402
    from init_working_helpers import seed_tech_design_session  # noqa: E402
    from resolved_refs_schema import write_resolved_refs  # noqa: E402
    from workflow_profile_paths import doc_dir  # noqa: E402

    cycle = "feature-antiseep-scope"
    profile = "lulu-design"
    seed_tech_design_session(tmp_path, cycle_id=cycle)
    rev = tmp_path / doc_dir(cycle, 1, profile, tmp_path)
    f1 = str((tmp_path / "D1" / "decision-doc.md").resolve())
    f2 = str((tmp_path / "D2" / "decision-doc.md").resolve())
    (tmp_path / "D1").mkdir()
    (tmp_path / "D2").mkdir()
    for path, unit in (
        (f1, {"id": "U1", "slot": "D.a", "text": "auth"}),
        (f2, {"id": "U2", "slot": "D.b", "text": "bill"}),
    ):
        Path(path).write_text(
            json.dumps({"version": 1, "gates": {"D": [unit]}}),
            encoding="utf-8",
        )
    # Replace locked L1 tree with scope-package convert (multi-L).
    for name in ("dependency-tree.json", "discussion-pointer.json", "slice-rulers.json"):
        p = rev / name
        if p.is_file():
            p.unlink()
    if (rev / "l-ledger.json").is_file():
        (rev / "l-ledger.json").unlink()
    if (rev / "L1").is_dir():
        import shutil

        shutil.rmtree(rev / "L1")
    pkg_path = save_scope_package(rev, _pkg_multi(f1, f2))
    convert_scope_package(rev, scope_package_path=pkg_path)
    write_resolved_refs(
        rev,
        cycle_id=cycle,
        stage=profile,
        run_mode="tech",
        scope_ref=DeliveredRef(type="lulu-approach", path=str(pkg_path.resolve())),
        intent_baseline_refs=[],
        norm_constraint_refs=[],
    )

    ledger = load_l_ledger(rev)
    ledger["by_id"][str(ledger["focus"])]["state"] = "FactIntake"
    save_l_ledger(rev, ledger)
    focus = str(ledger["focus"])
    stamp = rev / focus / "_fact_intake.complete"
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text("ok\n", encoding="utf-8")
    result = l_step_control.enter_inductive(cycle, tmp_path, profile_id=profile)
    assert result["ok"] is True, result
    dispatch = result["dispatch_input"]
    mirror = Path(f1).as_posix()
    assert f"SCOPE_REF:            {mirror}" in dispatch
    assert f"SOURCE_PATH:          {mirror}" in dispatch
    scope_line = dispatch.split("SCOPE_REF:", 1)[1].split("\n", 1)[0]
    source_line = dispatch.split("SOURCE_PATH:", 1)[1].split("\n", 1)[0]
    assert "scope-package.json" not in scope_line
    assert "scope-package.json" not in source_line
    assert f2 not in scope_line
    assert f2 not in source_line


def test_enter_fact_intake_fails_when_l_mirror_missing(tmp_path: Path) -> None:
    import bootstrap  # noqa: F401
    import l_step_control  # noqa: E402
    from delivered_refs_schema import DeliveredRef  # noqa: E402
    from init_working_helpers import seed_tech_design_session  # noqa: E402
    from resolved_refs_schema import write_resolved_refs  # noqa: E402
    from workflow_profile_paths import doc_dir  # noqa: E402

    cycle = "feature-antiseep-missing"
    profile = "lulu-design"
    seed_tech_design_session(tmp_path, cycle_id=cycle)
    rev = tmp_path / doc_dir(cycle, 1, profile, tmp_path)
    f1 = "/abs/D1/decision-doc.md"
    f2 = "/abs/D2/decision-doc.md"
    for name in ("dependency-tree.json", "discussion-pointer.json", "slice-rulers.json"):
        p = rev / name
        if p.is_file():
            p.unlink()
    if (rev / "l-ledger.json").is_file():
        (rev / "l-ledger.json").unlink()
    if (rev / "L1").is_dir():
        import shutil

        shutil.rmtree(rev / "L1")
    pkg_path = save_scope_package(rev, _pkg_multi(f1, f2))
    convert_scope_package(rev, scope_package_path=pkg_path)
    (rev / "L1" / "scope-ref.json").unlink()
    write_resolved_refs(
        rev,
        cycle_id=cycle,
        stage=profile,
        run_mode="tech",
        scope_ref=DeliveredRef(type="lulu-approach", path=str(pkg_path.resolve())),
        intent_baseline_refs=[],
        norm_constraint_refs=[],
    )

    result = l_step_control.enter_fact_intake(cycle, tmp_path, profile_id=profile)
    assert result["ok"] is False
    assert "missing L source_path mirror" in str(result.get("error") or result.get("reason") or "")


def test_l2_mirror_seed_path_independent(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    f1 = "/abs/D1/decision-doc.md"
    f2 = "/abs/D2/decision-doc.md"
    pkg_path = save_scope_package(rev, _pkg_multi(f1, f2))
    convert_scope_package(rev, scope_package_path=pkg_path)
    write_scope_ref_mirror(rev, "L2", source_path=f2)

    assert resolve_l_seed_source_path(rev, "L1") == f1
    assert resolve_l_seed_source_path(rev, "L2") == f2
    assert pkg_path.name not in resolve_l_seed_source_path(rev, "L2")
