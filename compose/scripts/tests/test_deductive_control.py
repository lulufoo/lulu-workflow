#!/usr/bin/env python3
"""Tests for deductive_control pending gate + quarantine-unref."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
_CORE = _SCRIPTS / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))
from workflow_paths import seed_revision_profile_pointer  # noqa: E402
_CTL = _SCRIPTS / "deductive" / "deductive_control.py"
_REPO = Path(__file__).resolve().parents[4]


def _prepare(tmp_path: Path) -> Path:
    rev = tmp_path / "revision1"
    rev.mkdir()
    seed_revision_profile_pointer(rev)
    (rev / "L1").mkdir(parents=True, exist_ok=True)
    return rev


def _run(args: list[str], revision_dir: Path) -> subprocess.CompletedProcess[str]:
    seed_revision_profile_pointer(revision_dir)
    return subprocess.run(
        [
            sys.executable,
            str(_CTL),
            "--revision-dir",
            str(revision_dir),
            "--project-root",
            str(_REPO),
            *args,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_pending_init_add_resolve_gate(tmp_path: Path) -> None:
    rev = _prepare(tmp_path)
    (rev / "L1" / "_facts.json").write_text(
        json.dumps(
            [{"id": "F-1", "text": "ar", "lens_tags": ["AR"]}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    init = _run(["pending-init"], rev)
    assert init.returncode == 0
    assert json.loads(init.stdout)["ok"] is True

    add = _run(
        [
            "pending-add",
            "--kind",
            "edge_hole",
            "--lens",
            "T",
            "--summary",
            "uncovered SK",
            "--upstream-ref",
            "F-1",
        ],
        rev,
    )
    assert add.returncode == 0
    pid = json.loads(add.stdout)["id"]

    gate = _run(["gate-check"], rev)
    assert gate.returncode == 0
    assert json.loads(gate.stdout)["ok"] is True

    resolve = _run(
        ["pending-resolve", "--id", pid, "--status", "resolved"],
        rev,
    )
    assert resolve.returncode == 0

    gate2 = _run(["gate-check"], rev)
    assert gate2.returncode == 0
    assert json.loads(gate2.stdout)["ok"] is True


def test_open_pending_kinds_do_not_block_gate(tmp_path: Path) -> None:
    rev = _prepare(tmp_path)
    (rev / "L1" / "_facts.json").write_text(
        json.dumps(
            [{"id": "F-1", "text": "ar", "lens_tags": ["AR"]}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    assert _run(["pending-init"], rev).returncode == 0
    assert (
        _run(
            [
                "pending-add",
                "--kind",
                "edge_hole",
                "--lens",
                "T",
                "--summary",
                "uncovered SK",
                "--upstream-ref",
                "F-1",
            ],
            rev,
        ).returncode
        == 0
    )
    add_kw = _run(
        [
            "pending-add",
            "--kind",
            "kw_shortfall",
            "--lens",
            "T",
            "--summary",
            "KW table rows not met",
        ],
        rev,
    )
    assert add_kw.returncode == 0
    both_open = _run(["gate-check"], rev)
    assert both_open.returncode == 0
    assert json.loads(both_open.stdout)["ok"] is True


def test_kw_shortfall_pending_does_not_block_gate(tmp_path: Path) -> None:
    rev = _prepare(tmp_path)
    (rev / "L1" / "_facts.json").write_text(
        json.dumps(
            [{"id": "F-1", "text": "task thin", "lens_tags": ["T"]}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    assert _run(["pending-init"], rev).returncode == 0
    add = _run(
        [
            "pending-add",
            "--kind",
            "kw_shortfall",
            "--lens",
            "T",
            "--summary",
            "KW table rows not met for Change Overview depth",
        ],
        rev,
    )
    assert add.returncode == 0, add.stderr
    assert _run(["gate-check"], rev).returncode == 0
    gate = _run(["gate-check"], rev)
    assert json.loads(gate.stdout)["ok"] is True


def test_gate_check_fails_when_pending_file_missing(tmp_path: Path) -> None:
    rev = _prepare(tmp_path)
    (rev / "L1" / "_facts.json").write_text(
        json.dumps(
            [{"id": "F-1", "text": "ar", "lens_tags": ["AR"]}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out = _run(["gate-check"], rev)
    assert out.returncode != 0
    assert "deductive-pending.json missing" in out.stderr


def test_gate_check_passes_on_unsettled_unref_quarantine(tmp_path: Path) -> None:
    rev = _prepare(tmp_path)
    (rev / "L1" / "_facts.json").write_text(
        json.dumps(
            [
                {
                    "id": "F-1",
                    "text": "quarantine orphan",
                    "lens_tags": [],
                    "derivation": {
                        "disposition": "quarantined",
                        "upstream_ref": ["U-1"],
                    },
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    assert _run(["pending-init"], rev).returncode == 0
    out = _run(["gate-check"], rev)
    assert out.returncode == 0
    assert json.loads(out.stdout)["ok"] is True


def test_gate_check_passes_when_unref_quarantine_settled(tmp_path: Path) -> None:
    rev = _prepare(tmp_path)
    (rev / "L1" / "_facts.json").write_text(
        json.dumps(
            [
                {
                    "id": "F-1",
                    "text": "quarantine orphan",
                    "lens_tags": [],
                    "derivation": {
                        "disposition": "quarantined",
                        "upstream_ref": ["U-1"],
                    },
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    assert _run(["pending-init"], rev).returncode == 0
    add = _run(
        [
            "pending-add",
            "--kind",
            "quarantine_unref",
            "--summary",
            "F-1 out of scope",
            "--upstream-ref",
            "F-1",
        ],
        rev,
    )
    assert add.returncode == 0
    pid = json.loads(add.stdout)["id"]
    assert (
        _run(
            ["pending-resolve", "--id", pid, "--status", "out_of_scope"],
            rev,
        ).returncode
        == 0
    )
    out = _run(["gate-check"], rev)
    assert out.returncode == 0


def test_quarantine_unref_lists_uncited(tmp_path: Path) -> None:
    rev = _prepare(tmp_path)
    (rev / "L1" / "_facts.json").write_text(
        json.dumps(
            [
                {
                    "id": "F-1",
                    "text": "cited quarantine",
                    "lens_tags": [],
                    "derivation": {
                        "disposition": "quarantined",
                        "upstream_ref": ["U-1"],
                    },
                },
                {
                    "id": "F-2",
                    "text": "uses F-1",
                    "lens_tags": ["T"],
                    "origin": {"type": "derived", "ref": ["F-1"]},
                },
                {
                    "id": "F-3",
                    "text": "still uncited quarantine",
                    "lens_tags": [],
                    "derivation": {
                        "disposition": "quarantined",
                        "upstream_ref": ["U-2"],
                    },
                },
                {
                    "id": "F-4",
                    "text": "not_needed excluded from unref list",
                    "lens_tags": [],
                    "derivation": {
                        "disposition": "not_needed",
                        "upstream_ref": ["U-3"],
                        "rule_id": "D-DEC",
                    },
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _run(["pending-init"], rev)
    out = _run(["quarantine-unref"], rev)
    assert out.returncode == 0
    payload = json.loads(out.stdout)
    assert payload["ok"] is True
    assert payload["unreferenced_ids"] == ["F-3"]


def test_disposition_patch_validate_and_apply(tmp_path: Path) -> None:
    rev = _prepare(tmp_path)
    (rev / "L1" / "_facts.json").write_text(
        json.dumps(
            [
                {
                    "id": "F-1",
                    "text": "should carry",
                    "lens_tags": [],
                    "derivation": {
                        "disposition": "quarantined",
                        "upstream_ref": ["doc#a"],
                    },
                },
                {
                    "id": "F-2",
                    "text": "keep quarantine",
                    "lens_tags": [],
                    "derivation": {
                        "disposition": "quarantined",
                        "upstream_ref": ["doc#b"],
                    },
                },
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    patch = {
        "version": "1",
        "counts": {"carried": 0, "quarantined": 2, "not_needed": 0},
        "ops": [
            {
                "op": "promote",
                "fact_id": "F-1",
                "lens_tags": ["CTX"],
                "note": "selected-path constraint",
            }
        ],
    }
    patch_path = rev / "deductive-disposition-review.patch"
    patch_path.write_text(
        json.dumps(patch, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    seed_revision_profile_pointer(rev)
    out = subprocess.run(
        [
            sys.executable,
            str(_CTL),
            "--revision-dir",
            str(rev),
            "--project-root",
            str(_REPO),
            "disposition-patch-validate",
            "--patch-file",
            str(patch_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert out.returncode == 0, out.stderr
    apply = subprocess.run(
        [
            sys.executable,
            str(_CTL),
            "--revision-dir",
            str(rev),
            "--project-root",
            str(_REPO),
            "disposition-patch-apply",
            "--patch-file",
            str(patch_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert apply.returncode == 0, apply.stderr
    facts = json.loads((rev / "L1" / "_facts.json").read_text(encoding="utf-8"))
    assert facts[0]["derivation"]["disposition"] == "carried"
    assert facts[0]["lens_tags"] == ["CTX"]
    assert facts[1]["derivation"]["disposition"] == "quarantined"


def _pending_items(revision_dir: Path) -> list[dict]:
    path = revision_dir / "L1" / "deductive-pending.json"
    return json.loads(path.read_text(encoding="utf-8"))["items"]


def test_pending_replace_swaps_open_edge_holes(tmp_path: Path) -> None:
    rev = _prepare(tmp_path)
    (rev / "L1" / "_facts.json").write_text(
        json.dumps([{"id": "F-1", "text": "ar", "lens_tags": ["AR"]}]),
        encoding="utf-8",
    )
    assert _run(["pending-init"], rev).returncode == 0
    first = _run(
        [
            "pending-add",
            "--kind",
            "edge_hole",
            "--lens",
            "T",
            "--summary",
            "old leftover",
            "--upstream-ref",
            "F-9",
        ],
        rev,
    )
    assert first.returncode == 0
    out = _run(
        [
            "pending-replace",
            "--kind",
            "edge_hole",
            "--items-json",
            json.dumps(
                [
                    {"lens": "T", "uncovered": ["F-1", "F-2"]},
                    {"lens": "SK", "uncovered": ["F-3"]},
                ]
            ),
        ],
        rev,
    )
    assert out.returncode == 0, out.stderr
    payload = json.loads(out.stdout)
    assert payload["ok"] is True
    assert payload["command"] == "pending-replace"
    assert payload["removed"] == 1
    assert len(payload["ids"]) == 2
    items = _pending_items(rev)
    open_holes = [i for i in items if i["status"] == "open" and i["kind"] == "edge_hole"]
    assert [i["lens"] for i in open_holes] == ["T", "SK"]
    assert open_holes[0]["summary"] == "uncovered F-1, F-2"
    assert open_holes[0]["upstream_ref"] == ""
    assert open_holes[1]["summary"] == "uncovered F-3"
    assert open_holes[1]["upstream_ref"] == "F-3"
    assert _run(["gate-check"], rev).returncode == 0


def test_pending_replace_keeps_resolved_and_other_kinds(tmp_path: Path) -> None:
    rev = _prepare(tmp_path)
    (rev / "L1" / "_facts.json").write_text(
        json.dumps([{"id": "F-1", "text": "ar", "lens_tags": ["AR"]}]),
        encoding="utf-8",
    )
    assert _run(["pending-init"], rev).returncode == 0
    add_old = _run(
        [
            "pending-add",
            "--kind",
            "edge_hole",
            "--lens",
            "T",
            "--summary",
            "old",
            "--upstream-ref",
            "F-1",
        ],
        rev,
    )
    pid = json.loads(add_old.stdout)["id"]
    assert (
        _run(
            ["pending-resolve", "--id", pid, "--status", "resolved"],
            rev,
        ).returncode
        == 0
    )
    add_kw = _run(
        [
            "pending-add",
            "--kind",
            "kw_shortfall",
            "--lens",
            "T",
            "--summary",
            "thin",
        ],
        rev,
    )
    assert add_kw.returncode == 0
    out = _run(
        [
            "pending-replace",
            "--kind",
            "edge_hole",
            "--items-json",
            json.dumps([{"lens": "SK", "uncovered": ["F-2"]}]),
        ],
        rev,
    )
    assert out.returncode == 0, out.stderr
    items = _pending_items(rev)
    by_id = {i["id"]: i for i in items}
    assert by_id[pid]["status"] == "resolved"
    assert by_id[pid]["kind"] == "edge_hole"
    kw = [i for i in items if i["kind"] == "kw_shortfall"]
    assert len(kw) == 1
    assert kw[0]["status"] == "open"
    open_holes = [i for i in items if i["kind"] == "edge_hole" and i["status"] == "open"]
    assert [i["lens"] for i in open_holes] == ["SK"]


def test_pending_replace_empty_list_clears_open_edge_holes(tmp_path: Path) -> None:
    rev = _prepare(tmp_path)
    (rev / "L1" / "_facts.json").write_text(
        json.dumps([{"id": "F-1", "text": "ar", "lens_tags": ["AR"]}]),
        encoding="utf-8",
    )
    assert _run(["pending-init"], rev).returncode == 0
    assert (
        _run(
            [
                "pending-add",
                "--kind",
                "edge_hole",
                "--lens",
                "T",
                "--summary",
                "old",
            ],
            rev,
        ).returncode
        == 0
    )
    out = _run(
        ["pending-replace", "--kind", "edge_hole", "--items-json", "[]"],
        rev,
    )
    assert out.returncode == 0, out.stderr
    payload = json.loads(out.stdout)
    assert payload["removed"] == 1
    assert payload["ids"] == []
    items = _pending_items(rev)
    assert [i for i in items if i["kind"] == "edge_hole" and i["status"] == "open"] == []


def test_pending_replace_rejects_bad_kind_and_json(tmp_path: Path) -> None:
    rev = _prepare(tmp_path)
    (rev / "L1" / "_facts.json").write_text(
        json.dumps([{"id": "F-1", "text": "ar", "lens_tags": ["AR"]}]),
        encoding="utf-8",
    )
    assert _run(["pending-init"], rev).returncode == 0
    bad_kind = _run(
        [
            "pending-replace",
            "--kind",
            "kw_shortfall",
            "--items-json",
            json.dumps([{"lens": "T", "uncovered": ["F-1"]}]),
        ],
        rev,
    )
    assert bad_kind.returncode != 0
    assert "edge_hole" in bad_kind.stderr
    bad_json = _run(
        ["pending-replace", "--kind", "edge_hole", "--items-json", "{}"],
        rev,
    )
    assert bad_json.returncode != 0
    assert "must be an array" in bad_json.stderr
