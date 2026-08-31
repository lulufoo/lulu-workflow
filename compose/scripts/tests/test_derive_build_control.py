#!/usr/bin/env python3
"""Tests for derive-runner derive_build_control context + lens-bundle."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_CTL = (
    Path(__file__).resolve().parents[2]
    / "deductive-runner"
    / "derive-runner"
    / "scripts"
    / "derive_build_control.py"
)
_REPO = Path(__file__).resolve().parents[4]
_PLAN_KW = (
    _REPO / "lulu-dev-workflow" / "lulu-plan" / "templates" / "section-kw-criteria.md"
)


_CORE = _REPO / "lulu-dev-workflow" / "compose" / "scripts" / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))
from workflow_paths import seed_revision_profile_pointer  # noqa: E402


def _revision(tmp_path: Path) -> Path:
    rev = tmp_path / "revision1"
    rev.mkdir(parents=True, exist_ok=True)
    seed_revision_profile_pointer(rev)
    return rev


def _load_ctl():
    spec = importlib.util.spec_from_file_location("derive_build_control", _CTL)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_context_help():
    proc = subprocess.run(
        [sys.executable, str(_CTL), "context", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "intake-eval" in (proc.stdout or "").lower() or "context" in (proc.stdout or "")


def test_lens_bundle_help():
    proc = subprocess.run(
        [sys.executable, str(_CTL), "lens-bundle", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "--lens" in (proc.stdout or "")


def test_context_fails_without_eval_gate(tmp_path: Path):
    mod = _load_ctl()
    rev = _revision(tmp_path)
    ns = type(
        "Args",
        (),
        {
            "revision_dir": str(rev),
            "project_root": str(tmp_path),
            "cycle_id": "",
        },
    )()
    code = mod.cmd_context(ns)
    assert code != 0


def test_context_fails_when_eval_not_done(tmp_path: Path):
    mod = _load_ctl()
    rev = _revision(tmp_path)
    gate = rev / "fact-intake-eval"
    gate.mkdir(parents=True)
    (gate / "evaluate-state.md").write_text(
        "eval_status: running\n",
        encoding="utf-8",
    )
    ns = type(
        "Args",
        (),
        {
            "revision_dir": str(rev),
            "project_root": str(tmp_path),
            "cycle_id": "",
        },
    )()
    code = mod.cmd_context(ns)
    assert code != 0


def test_slice_kw_criteria_h2_blocks():
    mod = _load_ctl()
    raw = _PLAN_KW.read_text(encoding="utf-8")
    ctx = mod.slice_kw_criteria(raw, "CTX")
    assert ctx is not None
    assert "KW0" in ctx
    assert "## GO" not in ctx
    go = mod.slice_kw_criteria(raw, "go")
    assert go is not None
    assert "KW0" in go
    assert mod.slice_kw_criteria(raw, "NOPE") is None


def test_design_registry_has_section_order_no_lens_v2():
    path = (
        _REPO
        / "lulu-dev-workflow"
        / "lulu-design"
        / "templates"
        / "section-registry.json"
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "_lens_v2" not in data
    assert data["section_order"] == list(data["sections"].keys())


def test_lens_bundle_cli_stdout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    mod = _load_ctl()
    rev = _revision(tmp_path)
    (rev / "L1" / "_facts.json").write_text(
        json.dumps(
            [
                {
                    "id": "F-1",
                    "text": "carried ctx",
                    "lens_tags": ["CTX"],
                    "derivation": {
                        "disposition": "carried",
                        "upstream_ref": ["doc#1"],
                    },
                },
                {
                    "id": "F-2",
                    "text": "quarantined ctx",
                    "lens_tags": [],
                    "derivation": {
                        "disposition": "quarantined",
                        "upstream_ref": ["doc#2"],
                    },
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    def _fake_fetch(kind: str, _root, profile_id=None, cycle_id=None, **_kwargs):
        if kind == "section-registry":
            return json.dumps(
                {
                    "section_order": ["CTX", "GO"],
                    "sections": {
                        "CTX": {"presence": "required"},
                        "GO": {"presence": "required"},
                    },
                }
            )
        if kind == "section-kw-criteria":
            return "## CTX\n\nkw-body-ctx\n\n## GO\n\nkw-body-go\n"
        raise AssertionError(kind)

    monkeypatch.setattr(mod, "load_compose_template", _fake_fetch)
    monkeypatch.setattr(
        mod,
        "_require_intake_eval",
        lambda _rev: ({"eval_status": "done"}, None),
    )
    ns = type(
        "Args",
        (),
        {
            "lens": "CTX",
            "revision_dir": str(rev),
            "project_root": str(tmp_path),
            "cycle_id": "",
        },
    )()
    from io import StringIO
    import contextlib

    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        code = mod.cmd_lens_bundle(ns)
    assert code == 0
    payload = json.loads(buf.getvalue())
    assert payload["ok"] is True
    assert payload["command"] == "lens-bundle"
    assert payload["lens"] == "CTX"
    assert "kw-body-ctx" in payload["kw_criteria"]
    assert payload["facts"] == [{"id": "F-1", "text": "carried ctx"}]


def test_lens_bundle_fails_missing_kw_heading(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    mod = _load_ctl()
    rev = _revision(tmp_path)
    (rev / "L1" / "_facts.json").write_text("[]", encoding="utf-8")

    def _fake_fetch(kind: str, _root, profile_id=None, cycle_id=None, **_kwargs):
        if kind == "section-registry":
            return json.dumps(
                {
                    "section_order": ["CTX"],
                    "sections": {"CTX": {"presence": "required"}},
                }
            )
        if kind == "section-kw-criteria":
            return "## GO\n\nonly go\n"
        raise AssertionError(kind)

    monkeypatch.setattr(mod, "load_compose_template", _fake_fetch)
    monkeypatch.setattr(
        mod,
        "_require_intake_eval",
        lambda _rev: ({"eval_status": "done"}, None),
    )
    ns = type(
        "Args",
        (),
        {
            "lens": "CTX",
            "revision_dir": str(rev),
            "project_root": str(tmp_path),
            "cycle_id": "",
        },
    )()
    assert mod.cmd_lens_bundle(ns) != 0
