"""Tests for archive-1.0 P4.antiseep (Seed uses L-local fact_path mirror only)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
_INDUCTIVE = _SCRIPTS / "inductive"
_SECTION_CTL = _INDUCTIVE / "inductive_g3_section_control.py"

if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from discussion_pointer_schema import load_discussion_pointer  # noqa: E402
from scope_package_convert import (  # noqa: E402
    ScopePackageAntiseepError,
    convert_scope_package,
    focus_seed_fact_path,
    resolve_l_seed_fact_path,
    seed_fact_path_for_out_dir,
)
from scope_package_schema import (  # noqa: E402
    build_scope_package,
    save_scope_package,
    write_scope_ref_mirror,
)


def _pkg_multi(f1: str, f2: str) -> dict:
    return build_scope_package(
        slices=[
            {"id": "L1", "title": "Auth", "fact_path": f1, "source_id": "D1"},
            {"id": "L2", "title": "Billing", "fact_path": f2, "source_id": "D2"},
        ]
    )


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


def test_resolve_l_seed_fact_path_uses_mirror(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    f1 = "/abs/D1/decision-fact.json"
    f2 = "/abs/D2/decision-fact.json"
    pkg_path = save_scope_package(rev, _pkg_multi(f1, f2))
    convert_scope_package(rev, scope_package_path=pkg_path)

    assert resolve_l_seed_fact_path(rev, "L1") == f1
    assert resolve_l_seed_fact_path(rev, "L2") == f2
    assert load_discussion_pointer(rev)["focus"] == "L1"
    assert focus_seed_fact_path(rev) == f1


def test_missing_mirror_fails_without_package_fallback(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    f1 = "/abs/D1/decision-fact.json"
    f2 = "/abs/D2/decision-fact.json"
    pkg_path = save_scope_package(rev, _pkg_multi(f1, f2))
    convert_scope_package(rev, scope_package_path=pkg_path)
    (rev / "L1" / "scope-ref.json").unlink()

    with pytest.raises(ScopePackageAntiseepError, match="missing L fact_path mirror"):
        resolve_l_seed_fact_path(rev, "L1")
    with pytest.raises(ScopePackageAntiseepError, match="missing L fact_path mirror"):
        focus_seed_fact_path(rev)
    with pytest.raises(ScopePackageAntiseepError, match="missing L fact_path mirror"):
        seed_fact_path_for_out_dir(rev / "L1")


def test_seed_decision_uses_l_mirror_not_scope_package(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    f1 = str((tmp_path / "D1" / "decision-fact.json").resolve())
    f2 = str((tmp_path / "D2" / "decision-fact.json").resolve())
    (tmp_path / "D1").mkdir()
    (tmp_path / "D2").mkdir()
    for path, unit in (
        (f1, {"id": "U1", "slot": "D.a", "text": "auth only"}),
        (f2, {"id": "U2", "slot": "D.b", "text": "billing only"}),
    ):
        Path(path).write_text(
            json.dumps({"version": 1, "gates": {"D": [unit]}}),
            encoding="utf-8",
        )
    pkg_path = save_scope_package(rev, _pkg_multi(f1, f2))
    convert_scope_package(rev, scope_package_path=pkg_path)

    l1 = rev / "L1"
    _init_pointer(l1)
    # Poison index.scope_ref with whole scope-package — must not become origin.
    index_path = l1 / "inductive-scope" / "_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["scope_ref"] = pkg_path.resolve().as_posix()
    index_path.write_text(json.dumps(index), encoding="utf-8")

    code, payload = _run_seed(
        l1,
        "seed-decision",
        "--section",
        "I",
        "--lens-tags",
        "I",
        "--text",
        "auth only",
    )
    assert code == 0, payload
    facts = json.loads((l1 / "_facts.json").read_text(encoding="utf-8"))
    assert facts[0]["origin"]["type"] == "seed"
    refs = facts[0]["origin"]["ref"]
    assert f1 in refs
    assert pkg_path.name not in "".join(refs)
    assert pkg_path.resolve().as_posix() not in refs
    assert f2 not in refs


def test_seed_decision_fails_when_mirror_missing(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    f1 = "/abs/D1/decision-fact.json"
    f2 = "/abs/D2/decision-fact.json"
    pkg_path = save_scope_package(rev, _pkg_multi(f1, f2))
    convert_scope_package(rev, scope_package_path=pkg_path)
    (rev / "L1" / "scope-ref.json").unlink()

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
        "should fail",
    )
    assert code == 1
    assert payload.get("ok") is False
    err = str(payload.get("error", ""))
    assert "missing L fact_path mirror" in err
    assert "P4.antiseep" in err
    assert not (l1 / "_facts.json").is_file()


def test_seed_decision_rejects_index_scope_package_without_mirror(
    tmp_path: Path,
) -> None:
    """index.scope_ref=scope-package with no L mirror contract → hard fail."""
    out = tmp_path / "out"
    out.mkdir()
    # Package lives outside out_dir so revision_uses_scope_package(out) is false;
    # seed must still refuse defaulting origin_ref to that package path.
    pkg = tmp_path / "scope-package.json"
    pkg.write_text(
        json.dumps(
            build_scope_package(
                slices=[
                    {
                        "id": "L1",
                        "title": "Only",
                        "fact_path": "/x/fact.json",
                        "source_id": "main",
                    }
                ]
            )
        ),
        encoding="utf-8",
    )
    _init_pointer(out)
    index_path = out / "inductive-scope" / "_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["scope_ref"] = pkg.resolve().as_posix()
    index_path.write_text(json.dumps(index), encoding="utf-8")

    code, payload = _run_seed(
        out,
        "seed-decision",
        "--section",
        "I",
        "--lens-tags",
        "I",
        "--text",
        "no package seed",
    )
    assert code == 1
    assert payload.get("ok") is False
    err = str(payload.get("error", ""))
    assert "P4.antiseep" in err
    assert "scope-package" in err
    assert not (out / "_facts.json").is_file()


def test_seed_fact_path_for_out_dir_none_without_contract(tmp_path: Path) -> None:
    out = tmp_path / "plain"
    out.mkdir()
    assert seed_fact_path_for_out_dir(out) is None


def test_begin_inductive_scope_ref_is_l_mirror_fact_path(tmp_path: Path) -> None:
    """begin-inductive dispatch SCOPE_REF = focus L mirror fact_path, not package."""
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
    f1 = str((tmp_path / "D1" / "decision-fact.json").resolve())
    f2 = str((tmp_path / "D2" / "decision-fact.json").resolve())
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

    result = l_step_control.begin_inductive(cycle, tmp_path, profile_id=profile)
    assert result["ok"] is True, result
    dispatch = result["dispatch_input"]
    assert f"SCOPE_REF:            {Path(f1).as_posix()}" in dispatch
    assert "scope-package.json" not in dispatch.split("SCOPE_REF:", 1)[1].split("\n", 1)[0]
    assert f2 not in dispatch.split("SCOPE_REF:", 1)[1].split("\n", 1)[0]


def test_begin_inductive_fails_when_l_mirror_missing(tmp_path: Path) -> None:
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
    f1 = "/abs/D1/decision-fact.json"
    f2 = "/abs/D2/decision-fact.json"
    for name in ("dependency-tree.json", "discussion-pointer.json", "slice-rulers.json"):
        p = rev / name
        if p.is_file():
            p.unlink()
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

    result = l_step_control.begin_inductive(cycle, tmp_path, profile_id=profile)
    assert result["ok"] is False
    assert "P4.antiseep" in result["reason"]
    assert "missing L fact_path mirror" in result["reason"]


def test_l2_mirror_seed_path_independent(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    f1 = "/abs/D1/decision-fact.json"
    f2 = "/abs/D2/decision-fact.json"
    pkg_path = save_scope_package(rev, _pkg_multi(f1, f2))
    convert_scope_package(rev, scope_package_path=pkg_path)
    write_scope_ref_mirror(rev, "L2", fact_path=f2)  # already present; assert stable

    l2 = rev / "L2"
    _init_pointer(l2)
    code, payload = _run_seed(
        l2,
        "seed-decision",
        "--section",
        "I",
        "--lens-tags",
        "I",
        "--text",
        "billing only",
    )
    assert code == 0, payload
    facts = json.loads((l2 / "_facts.json").read_text(encoding="utf-8"))
    refs = facts[0]["origin"]["ref"]
    assert f2 in refs
    assert f1 not in refs
    assert "scope-package.json" not in "".join(refs)
