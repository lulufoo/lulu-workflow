#!/usr/bin/env python3
"""Tests for Open-point store transitions, digests, and crash recovery."""

from __future__ import annotations

import hashlib
import hashlib
import json
import sys
from pathlib import Path

import pytest

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
_SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_INDUCTIVE_DIR))
for _name in ("gate", "g2", "g3", "g4"):
    sys.path.insert(0, str(_INDUCTIVE_DIR / "schema" / _name))
sys.path.insert(0, str(_SCRIPTS / "templates"))
sys.path.insert(0, str(_SCRIPTS / "_kernel"))

from compose_state_lock import canonical_digest, durable_write_json  # noqa: E402
from lens_frontier_schema import (  # noqa: E402
    default_lens_entry,
    lens_frontier_path,
    load_lens_frontier,
)
from open_point_store import (  # noqa: E402
    RepairRequiredError,
    add_opens,
    check_close,
    defer_open,
    detect_lens_context,
    detect_lens_registry,
    detect_lens_registry_entry,
    detect_opens_snapshot,
    facts_for_lens,
    ensure_frontier,
    lens_snapshot,
    load_bundle,
    reconcile,
    reject_open,
    set_frontier,
    settle_open,
    skip_open,
)
from open_point_transaction_schema import open_point_txn_path  # noqa: E402
from opens_schema import opens_path  # noqa: E402

_FIXTURE_REGISTRY = {
    "version": "1",
    "document_preamble": "test",
    "section_order": ["I"],
    "sections": {
        "I": {"heading": "Intent", "intent": "constraints", "presence": "required"}
    },
}
_FIXTURE_KW = (
    "## I\n\n| KW | Verifiable intent attributes |\n|----|------------------------------|\n"
    "| KW0 | unnamed |\n| KW1 | readable |\n| KW2 | traceable |\n| KW3 | boundary-clear |\n"
)
_PLAN_PROFILE = (
    Path(__file__).resolve().parents[3] / "lulu-plan" / "compose-profile.json"
)


_LIVE_SKILL_TESTS = {
    "test_lens_snapshot_reads_skill_not_slice",
    "test_lens_snapshot_raises_when_skill_missing",
    "test_lens_snapshot_fetches_installed_lulu_plan",
}


@pytest.fixture(autouse=True)
def _patch_skill_templates(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    if request.node.name in _LIVE_SKILL_TESTS:
        return

    def _text(role: str, _slice_dir: Path, _project_root: object = None) -> str:
        if role == "section-registry":
            return json.dumps(_FIXTURE_REGISTRY)
        if role == "section-kw-criteria":
            return _FIXTURE_KW
        raise ValueError(f"{role} missing from SKILL")

    monkeypatch.setattr("open_point_store._skill_template_text", _text)


def _candidate(**overrides):
    base = {
        "question": "What breaks first?",
        "basis": "Intent and facts collide on the write path",
        "blocking": True,
        "lens": "I",
        "source": {"actor": "ai", "means": "probe"},
    }
    base.update(overrides)
    return base


def _human_open(**overrides):
    raw = _candidate()
    raw["source"] = {"actor": "human", "means": "direct"}
    raw.update(overrides)
    return raw


def _lens_measurements(slice_dir: Path, checked, raw_candidates):
    path = lens_frontier_path(slice_dir)
    lenses = load_lens_frontier(path)["lenses"] if path.is_file() else {}
    hit = {
        str(item.get("lens", "")).strip().upper()
        for item in raw_candidates
        if isinstance(item, dict) and item.get("lens")
    }
    out = []
    for lens in checked:
        key = str(lens).strip().upper()
        entry = lenses.get(key) or default_lens_entry()
        start = int(entry.get("frontier_kw") or 0)
        out.append(
            {"lens": key, "start_kw": start, "gap_kw": start if key in hit else None}
        )
    return out


def _detect_meta(slice_dir: Path, raw_candidates, **overrides):
    ensure_frontier(slice_dir)
    meta = {
        "checked_lenses": ["I", "FL"],
        "raw_candidates": list(raw_candidates),
    }
    meta.update(overrides)
    if "lens_measurements" not in overrides:
        meta["lens_measurements"] = _lens_measurements(
            slice_dir, meta["checked_lenses"], meta["raw_candidates"]
        )
    return meta


def test_detect_projections_keep_only_needed_fields():
    registry = detect_lens_registry(
        {
            "section_order": ["I", "ST"],
            "sections": {
                "I": {
                    "heading": "Intent",
                    "intent": "constraints",
                    "intent_boundary": "not tasks",
                    "presence": "required",
                    "aliases": ["invariants"],
                },
                "ST": {"heading": "Structure"},
            },
        }
    )
    assert registry == [
        {
            "lens": "I",
            "heading": "Intent",
            "intent": "constraints",
            "intent_boundary": "not tasks",
        },
        {
            "lens": "ST",
            "heading": "Structure",
            "intent": "",
            "intent_boundary": "",
        },
    ]
    assert detect_opens_snapshot(
        [
            {
                "id": "O-1",
                "status": "open",
                "question": "q",
                "basis": "b",
                "lens": "i",
                "blocking": True,
                "source": {"actor": "human", "means": "direct"},
            }
        ]
    ) == [
        {
            "id": "O-1",
            "status": "open",
            "question": "q",
            "basis": "b",
            "lens": "I",
        }
    ]


def test_empty_detect_writes_receipt_only_and_stays_idle(tmp_path: Path):
    result = add_opens(tmp_path, opens=[], detect=_detect_meta(tmp_path, []))
    bundle = load_bundle(tmp_path)
    assert bundle["state"]["phase"] == "idle"
    assert bundle["state"]["active_batch_id"] is None
    assert bundle["batches"]["batches"] == []
    assert bundle["opens"] == []
    receipts = bundle["receipts"]["receipts"]
    assert len(receipts) == 1
    assert receipts[0]["zero_result"] is True
    assert receipts[0]["raw_candidate_count"] == 0
    assert receipts[0]["final_open_ids"] == []
    assert result["receipt"]["id"] == receipts[0]["id"]


def test_nonempty_detect_from_idle_creates_batch_and_processing(tmp_path: Path):
    result = add_opens(
        tmp_path,
        opens=[_candidate(), _candidate(question="Second gap")],
        detect=_detect_meta(tmp_path, [_candidate(), _candidate(question="Second gap")]),
    )
    bundle = load_bundle(tmp_path)
    assert [item["id"] for item in bundle["opens"]] == ["O-1", "O-2"]
    assert bundle["opens"][0]["source"] == {"actor": "ai", "means": "probe"}
    assert bundle["opens"][0]["lens"] == "I"
    assert bundle["state"]["phase"] == "processing"
    assert bundle["state"]["active_open_id"] == "O-1"
    batch = bundle["batches"]["batches"][0]
    assert batch["status"] == "active"
    assert batch["detect_receipt_id"] == result["receipt"]["id"]
    assert batch["open_ids"] == ["O-1", "O-2"]
    assert result["receipt"]["zero_result"] is False
    assert result["receipt"]["final_open_ids"] == ["O-1", "O-2"]


def test_detect_from_processing_errors(tmp_path: Path):
    add_opens(
        tmp_path,
        opens=[_candidate()],
        detect=_detect_meta(tmp_path, [_candidate()]),
    )
    with pytest.raises(ValueError):
        add_opens(
            tmp_path,
            opens=[_candidate(question="late")],
            detect=_detect_meta(tmp_path, [_candidate(question="late")]),
        )


def test_human_add_while_idle_creates_batch_without_receipt(tmp_path: Path):
    add_opens(tmp_path, opens=[_human_open()])
    bundle = load_bundle(tmp_path)
    assert bundle["state"]["phase"] == "processing"
    assert bundle["state"]["active_open_id"] == "O-1"
    batch = bundle["batches"]["batches"][0]
    assert batch["detect_receipt_id"] is None
    assert batch["open_ids"] == ["O-1"]
    assert bundle["receipts"]["receipts"] == []


def test_human_add_while_processing_appends_without_displacing(tmp_path: Path):
    add_opens(tmp_path, opens=[_human_open()])
    add_opens(tmp_path, opens=[_human_open(question="tail item")])
    bundle = load_bundle(tmp_path)
    assert bundle["state"]["active_open_id"] == "O-1"
    assert bundle["batches"]["batches"][0]["open_ids"] == ["O-1", "O-2"]
    assert [item["id"] for item in bundle["opens"]] == ["O-1", "O-2"]


def test_empty_human_add_is_error(tmp_path: Path):
    with pytest.raises(ValueError):
        add_opens(tmp_path, opens=[])


def test_skip_moves_id_to_tail_and_advances(tmp_path: Path):
    add_opens(
        tmp_path,
        opens=[_human_open(), _human_open(question="two"), _human_open(question="three")],
    )
    skip_open(tmp_path, "O-1")
    bundle = load_bundle(tmp_path)
    assert bundle["batches"]["batches"][0]["open_ids"] == ["O-2", "O-3", "O-1"]
    assert bundle["state"]["phase"] == "processing"
    assert bundle["state"]["active_open_id"] == "O-2"
    assert bundle["opens"][0]["status"] == "open"


def test_preview_settle_does_not_write_until_apply(tmp_path: Path):
    from open_point_store import apply_loop_after, preview_settle  # noqa: WPS433

    add_opens(
        tmp_path,
        opens=[_human_open(), _human_open(question="two")],
    )
    before_opens = (tmp_path / "inductive-opens.json").read_text(encoding="utf-8")
    before_state = (tmp_path / "open-point-state.json").read_text(encoding="utf-8")
    preview = preview_settle(tmp_path, "O-1", ["F-1"])
    assert preview["opens"][0]["status"] == "settled"
    assert preview["opens"][0]["resolved_by"] == ["F-1"]
    assert preview["state"]["active_open_id"] == "O-2"
    assert (tmp_path / "inductive-opens.json").read_text(encoding="utf-8") == before_opens
    assert (tmp_path / "open-point-state.json").read_text(encoding="utf-8") == before_state

    apply_loop_after(
        tmp_path,
        opens=preview["opens"],
        state=preview["state"],
        batches=preview["batches"],
    )
    bundle = load_bundle(tmp_path)
    assert bundle["opens"][0]["status"] == "settled"
    assert bundle["state"]["active_open_id"] == "O-2"


def test_settle_advances_and_last_open_completes_batch(tmp_path: Path):
    add_opens(
        tmp_path,
        opens=[_human_open(), _human_open(question="two")],
    )
    settle_open(tmp_path, "O-1", ["F-1"])
    bundle = load_bundle(tmp_path)
    assert bundle["opens"][0]["status"] == "settled"
    assert bundle["opens"][0]["resolved_by"] == ["F-1"]
    assert bundle["state"]["active_open_id"] == "O-2"
    assert bundle["batches"]["batches"][0]["status"] == "active"

    settle_open(tmp_path, "O-2", ["F-2"])
    bundle = load_bundle(tmp_path)
    assert bundle["state"]["phase"] == "idle"
    assert bundle["state"]["active_batch_id"] is None
    assert bundle["state"]["active_open_id"] is None
    assert bundle["batches"]["batches"][0]["status"] == "completed"
    assert bundle["batches"]["batches"][0]["open_ids"] == ["O-1", "O-2"]


def test_defer_and_reject_advance_like_settle(tmp_path: Path):
    add_opens(
        tmp_path,
        opens=[
            _human_open(),
            _human_open(question="two"),
            _human_open(question="three"),
        ],
    )
    defer_open(tmp_path, "O-1", "park")
    reject_open(tmp_path, "O-2", "false positive")
    bundle = load_bundle(tmp_path)
    assert bundle["opens"][0]["status"] == "deferred"
    assert bundle["opens"][1]["status"] == "rejected"
    assert bundle["state"]["active_open_id"] == "O-3"
    assert bundle["batches"]["batches"][0]["status"] == "active"


def test_deleted_detect_candidates_write_nonzero_receipt_no_batch(tmp_path: Path):
    raw = [_candidate(), _candidate(question="dropped")]
    add_opens(tmp_path, opens=[], detect=_detect_meta(tmp_path, raw))
    bundle = load_bundle(tmp_path)
    assert bundle["state"]["phase"] == "idle"
    assert bundle["batches"]["batches"] == []
    assert bundle["opens"] == []
    receipt = bundle["receipts"]["receipts"][0]
    assert receipt["zero_result"] is False
    assert receipt["raw_candidate_count"] == 2
    assert receipt["final_open_ids"] == []


def test_cleared_and_hard_skip_predicates(tmp_path: Path):
    _write_registry_and_kw(tmp_path)
    ensure_frontier(tmp_path)
    add_opens(tmp_path, opens=[], detect=_detect_meta(tmp_path, []))
    cleared = check_close(tmp_path, mode="cleared")
    assert cleared["ok"] is True
    hard = check_close(tmp_path, mode="hard-skip")
    assert hard["ok"] is True

    add_opens(tmp_path, opens=[_human_open()])
    assert check_close(tmp_path, mode="cleared")["ok"] is False
    assert check_close(tmp_path, mode="hard-skip")["ok"] is False

    defer_open(tmp_path, "O-1", "later")
    assert check_close(tmp_path, mode="hard-skip")["ok"] is True
    assert check_close(tmp_path, mode="cleared")["ok"] is True


def test_crash_after_digest_complete_deletes_txn(tmp_path: Path):
    add_opens(tmp_path, opens=[_human_open()])
    after = json.loads(opens_path(tmp_path).read_text(encoding="utf-8"))
    txn_path = open_point_txn_path(tmp_path)
    durable_write_json(
        txn_path,
        {
            "version": 1,
            "operation": "add-opens",
            "targets": {
                "inductive-opens.json": {
                    "existed": False,
                    "before": None,
                    "after_digest": canonical_digest(after),
                }
            },
        },
    )
    reconcile(tmp_path)
    assert not txn_path.is_file()
    assert load_bundle(tmp_path)["opens"][0]["id"] == "O-1"


def test_crash_mixed_restores_before(tmp_path: Path):
    add_opens(tmp_path, opens=[_human_open()])
    before_opens = json.loads(opens_path(tmp_path).read_text(encoding="utf-8"))
    before_state = json.loads(
        (tmp_path / "open-point-state.json").read_text(encoding="utf-8")
    )
    after_opens = list(before_opens) + [
        {
            "id": "O-2",
            "status": "open",
            "source": {"actor": "human", "means": "direct"},
            "question": "ghost",
            "basis": "should roll back",
            "blocking": False,
            "lens": "I",
        }
    ]
    after_state = {
        "version": 1,
        "phase": "idle",
        "active_batch_id": None,
        "active_open_id": None,
    }
    durable_write_json(opens_path(tmp_path), after_opens)
    txn_path = open_point_txn_path(tmp_path)
    durable_write_json(
        txn_path,
        {
            "version": 1,
            "operation": "add-opens",
            "targets": {
                "inductive-opens.json": {
                    "existed": True,
                    "before": before_opens,
                    "after_digest": canonical_digest(after_opens),
                },
                "open-point-state.json": {
                    "existed": True,
                    "before": before_state,
                    "after_digest": canonical_digest(after_state),
                },
            },
        },
    )
    reconcile(tmp_path)
    assert not txn_path.is_file()
    assert [item["id"] for item in load_bundle(tmp_path)["opens"]] == ["O-1"]
    assert load_bundle(tmp_path)["state"]["phase"] == "processing"


def test_crash_neither_sets_repair_required(tmp_path: Path):
    add_opens(tmp_path, opens=[_human_open()])
    before = json.loads(opens_path(tmp_path).read_text(encoding="utf-8"))
    durable_write_json(opens_path(tmp_path), [{"id": "O-99"}])
    txn_path = open_point_txn_path(tmp_path)
    durable_write_json(
        txn_path,
        {
            "version": 1,
            "operation": "add-opens",
            "targets": {
                "inductive-opens.json": {
                    "existed": True,
                    "before": before,
                    "after_digest": canonical_digest([]),
                }
            },
        },
    )
    with pytest.raises(RepairRequiredError):
        reconcile(tmp_path)
    with pytest.raises(RepairRequiredError):
        add_opens(tmp_path, opens=[_human_open(question="blocked")])
    assert txn_path.is_file()


def _write_registry_and_kw(slice_dir: Path) -> None:
    del slice_dir


def test_detect_rejects_legacy_detect_means(tmp_path: Path):
    with pytest.raises(ValueError, match="scan, intent, or probe"):
        add_opens(
            tmp_path,
            opens=[_candidate(source={"actor": "ai", "means": "detect"})],
            detect=_detect_meta(
                tmp_path, [_candidate(source={"actor": "ai", "means": "detect"})]
            ),
        )
    with pytest.raises(ValueError, match="means"):
        add_opens(
            tmp_path,
            opens=[_candidate(source={"actor": "ai", "means": "ai_scan"})],
            detect=_detect_meta(
                tmp_path, [_candidate(source={"actor": "ai", "means": "ai_scan"})]
            ),
        )


def test_add_opens_requires_lens(tmp_path: Path):
    raw = _human_open()
    del raw["lens"]
    with pytest.raises(ValueError, match="lens"):
        add_opens(tmp_path, opens=[raw])


def test_human_add_does_not_filter_by_kw(tmp_path: Path):
    add_opens(
        tmp_path,
        opens=[_human_open(question="What is the sign-off rollback path?")],
    )
    bundle = load_bundle(tmp_path)
    assert bundle["opens"][0]["question"].startswith("What is the sign-off")


def test_cleared_ok_at_kw0_when_no_gap(tmp_path: Path):
    _write_registry_and_kw(tmp_path)
    add_opens(tmp_path, opens=[], detect=_detect_meta(tmp_path, []))
    cleared = check_close(tmp_path, mode="cleared")
    assert cleared["ok"] is True, cleared
    assert load_lens_frontier(lens_frontier_path(tmp_path))["lenses"]["I"][
        "frontier_kw"
    ] == 0
    assert check_close(tmp_path, mode="hard-skip")["ok"] is True


def test_cleared_does_not_require_frontier_digest_match(tmp_path: Path):
    _write_registry_and_kw(tmp_path)
    add_opens(tmp_path, opens=[], detect=_detect_meta(tmp_path, []))
    assert check_close(tmp_path, mode="cleared")["ok"] is True

    set_frontier(tmp_path, "I", 3)
    assert check_close(tmp_path, mode="cleared")["ok"] is True


def test_detect_writes_last_gap_kw(tmp_path: Path):
    _write_registry_and_kw(tmp_path)
    add_opens(
        tmp_path,
        opens=[_candidate()],
        detect=_detect_meta(
            tmp_path,
            [_candidate()],
            checked_lenses=["I"],
            lens_measurements=[{"lens": "I", "start_kw": 0, "gap_kw": 1}],
        ),
    )
    frontier = load_lens_frontier(lens_frontier_path(tmp_path))
    assert frontier["lenses"]["I"]["frontier_kw"] == 1
    receipt = load_bundle(tmp_path)["receipts"]["receipts"][0]
    assert receipt["lens_measurements"][0]["gap_kw"] == 1
    assert "frontier_digest" not in receipt


def test_detect_rejects_start_kw_mismatch(tmp_path: Path):
    _write_registry_and_kw(tmp_path)
    with pytest.raises(ValueError, match="start_kw"):
        add_opens(
            tmp_path,
            opens=[_candidate()],
            detect=_detect_meta(
                tmp_path,
                [_candidate()],
                checked_lenses=["I"],
                lens_measurements=[{"lens": "I", "start_kw": 2, "gap_kw": 2}],
            ),
        )


def test_settle_does_not_reset_frontier_kw(tmp_path: Path):
    _write_registry_and_kw(tmp_path)
    add_opens(
        tmp_path,
        opens=[_candidate()],
        detect=_detect_meta(
            tmp_path,
            [_candidate()],
            checked_lenses=["I"],
            lens_measurements=[{"lens": "I", "start_kw": 0, "gap_kw": 1}],
        ),
    )
    settle_open(tmp_path, "O-1", ["F-1"])
    frontier = load_lens_frontier(lens_frontier_path(tmp_path))
    assert frontier["lenses"]["I"]["frontier_kw"] == 1


def test_detect_rejects_unknown_registry_lens(tmp_path: Path):
    _write_registry_and_kw(tmp_path)
    with pytest.raises(ValueError, match="section-registry"):
        add_opens(
            tmp_path,
            opens=[_candidate(lens="NOPE")],
            detect=_detect_meta(
                tmp_path,
                [_candidate(lens="NOPE")],
                checked_lenses=["I", "NOPE"],
            ),
        )


def test_detect_rejects_inert_means(tmp_path: Path):
    _write_registry_and_kw(tmp_path)
    with pytest.raises(ValueError, match="inert"):
        add_opens(
            tmp_path,
            opens=[_candidate(source={"actor": "ai", "means": "intent"})],
            detect=_detect_meta(
                tmp_path,
                [_candidate(source={"actor": "ai", "means": "intent"})],
            ),
        )


def test_add_opens_detect_requires_frontier_file(tmp_path: Path):
    meta = _detect_meta(tmp_path, [])
    (tmp_path / "lens-frontier.json").unlink()
    with pytest.raises(ValueError, match="lens-frontier"):
        add_opens(tmp_path, opens=[], detect=meta)


def test_cleared_fails_without_skill_templates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    add_opens(tmp_path, opens=[], detect=_detect_meta(tmp_path, []))

    def _boom(role: str, *_args: object, **_kwargs: object) -> str:
        raise ValueError(
            "section-registry missing from SKILL"
            if role == "section-registry"
            else "KW criteria missing from SKILL"
        )

    monkeypatch.setattr("open_point_store._skill_template_text", _boom)
    cleared = check_close(tmp_path, mode="cleared")
    assert cleared["ok"] is False
    assert any("section-registry" in item for item in cleared["reasons"])
    assert any("KW criteria missing" in item for item in cleared["reasons"])


def test_lens_snapshot_reads_skill_not_slice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import compose_template_loader as lct
    import workflow_paths as wp

    fetched = _FIXTURE_REGISTRY
    (tmp_path / "section-registry.json").write_text(
        json.dumps({"section_order": ["NOPE"]}), encoding="utf-8"
    )

    def _fake_fetch(name: str, _root: Path, **_kwargs: object) -> str:
        assert name == "section-registry"
        return json.dumps(fetched)

    monkeypatch.setattr(lct, "load_compose_template", _fake_fetch)
    monkeypatch.setattr(
        wp,
        "resolve_revision_runtime_profile",
        lambda *_args, **_kwargs: type(
            "R", (), {"profile_id": "lulu-plan", "profile_path": tmp_path / "p.json"}
        )(),
    )
    snapshot = lens_snapshot(tmp_path, tmp_path)
    assert snapshot["section_order"] == fetched["section_order"]
    assert "I" in snapshot["sections"]


def test_lens_snapshot_raises_when_skill_missing(tmp_path: Path):
    (tmp_path / "section-registry.json").write_text(
        json.dumps(_FIXTURE_REGISTRY), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="section-registry missing from SKILL"):
        lens_snapshot(tmp_path)
    with pytest.raises(ValueError, match="section-registry missing from SKILL"):
        lens_snapshot(tmp_path, tmp_path)


def test_lens_snapshot_fetches_installed_lulu_plan(tmp_path: Path):
    digest = hashlib.sha256(_PLAN_PROFILE.read_bytes()).hexdigest()
    (tmp_path / "session-state.md").write_text(
        "---\n"
        "version: 2\n"
        "active_doc: 2\n"
        f"profile_path: {_PLAN_PROFILE.resolve()}\n"
        f"profile_digest: {digest}\n"
        "start_id: test\n"
        "holder_finalized: true\n"
        "updated_at: 2024-01-01T00:00:00+00:00\n"
        "---\n",
        encoding="utf-8",
    )
    slice_dir = tmp_path / "revision1" / "L1"
    slice_dir.mkdir(parents=True)
    snapshot = lens_snapshot(slice_dir, tmp_path)
    assert snapshot.get("section_order") == [
        "CTX",
        "GO",
        "SC",
        "AR",
        "I",
        "SK",
        "T",
        "VF",
    ]
    assert not (slice_dir / "section-registry.json").exists()


def test_facts_for_lens_keeps_matching_tags_only():
    facts = [
        {"id": "F-1", "text": "a", "lens_tags": ["CTX"]},
        {"id": "F-2", "text": "b", "lens_tags": ["ctx", "GO"]},
        {"id": "F-3", "text": "c", "lens_tags": []},
        {"id": "F-4", "text": "d"},
        {"id": "F-5", "text": "e", "lens_tags": ["GO"]},
    ]
    assert [item["id"] for item in facts_for_lens(facts, "ctx")] == ["F-1", "F-2"]
    assert facts_for_lens(facts, "NOPE") == []
    assert facts_for_lens(None, "CTX") == []


def test_detect_lens_registry_entry_unknown():
    snapshot = {
        "section_order": ["I"],
        "sections": {"I": {"heading": "Intent", "intent": "c"}},
    }
    assert detect_lens_registry_entry(snapshot, "i")["heading"] == "Intent"
    with pytest.raises(ValueError, match="unknown lens"):
        detect_lens_registry_entry(snapshot, "GO")


def test_detect_lens_context_filters_facts(tmp_path: Path):
    (tmp_path / "_facts.json").write_text(
        json.dumps(
            [
                {"id": "F-I", "text": "intent", "lens_tags": ["I"]},
                {"id": "F-empty", "text": "none", "lens_tags": []},
                {"id": "F-go", "text": "goal", "lens_tags": ["GO"]},
            ]
        ),
        encoding="utf-8",
    )
    payload = detect_lens_context(tmp_path, "I", tmp_path)
    assert payload["lens_registry"]["lens"] == "I"
    assert "KW0" in payload["kw_criteria"]
    assert [item["id"] for item in payload["facts_snapshot"]] == ["F-I"]
    with pytest.raises(ValueError, match="unknown lens"):
        detect_lens_context(tmp_path, "GO", tmp_path)
