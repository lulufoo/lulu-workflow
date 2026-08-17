#!/usr/bin/env python3
"""Tests for Open-point store transitions, digests, and crash recovery."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
_SCHEMA_DIR = _INDUCTIVE_DIR / "schema"
sys.path.insert(0, str(_INDUCTIVE_DIR))
sys.path.insert(0, str(_SCHEMA_DIR))

from compose_state_lock import canonical_digest, durable_write_json  # noqa: E402
from open_point_store import (  # noqa: E402
    RepairRequired,
    StaleError,
    add_opens,
    check_close,
    defer_open,
    ensure_frontier,
    frontier_digest,
    load_bundle,
    reconcile,
    reject_open,
    set_frontier,
    settle_open,
    skip_open,
)
from open_point_transaction_schema import open_point_txn_path  # noqa: E402
from opens_schema import opens_path  # noqa: E402


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


def _detect_meta(slice_dir: Path, raw_candidates, **overrides):
    facts = _json_or_empty(slice_dir / "_facts.json")
    lenses = _json_or_empty(slice_dir / "section-registry.json")
    opens = _json_or_empty(slice_dir / "inductive-opens.json")
    facts_d = canonical_digest(facts)
    lens_d = canonical_digest(lenses)
    opens_d = canonical_digest(opens)
    ensure_frontier(slice_dir)
    frontier_d = frontier_digest(slice_dir)
    meta = {
        "checked_lenses": ["I", "FL"],
        "facts_digest": facts_d,
        "lens_digest": lens_d,
        "opens_digest": opens_d,
        "frontier_digest": frontier_d,
        "raw_candidates": list(raw_candidates),
        "expected_facts_digest": facts_d,
        "expected_lens_digest": lens_d,
        "expected_opens_digest": opens_d,
        "expected_frontier_digest": frontier_d,
        "inert_means": ["intent", "scan"],
    }
    meta.update(overrides)
    return meta


def _json_or_empty(path: Path):
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


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


def test_stale_expected_digest_rejected(tmp_path: Path):
    meta = _detect_meta(tmp_path, [_candidate()])
    meta["expected_facts_digest"] = canonical_digest(["stale"])
    with pytest.raises(StaleError):
        add_opens(tmp_path, opens=[_candidate()], detect=meta)


def test_cleared_and_hard_skip_predicates(tmp_path: Path):
    _write_registry_and_kw(tmp_path)
    ensure_frontier(tmp_path)
    set_frontier(tmp_path, "I", 3)
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
    assert check_close(tmp_path, mode="cleared")["ok"] is False


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
    with pytest.raises(RepairRequired):
        reconcile(tmp_path)
    with pytest.raises(RepairRequired):
        add_opens(tmp_path, opens=[_human_open(question="blocked")])
    assert txn_path.is_file()


def _write_registry_and_kw(slice_dir: Path) -> None:
    (slice_dir / "section-registry.json").write_text(
        json.dumps(
            {
                "version": "1",
                "document_preamble": "test",
                "section_order": ["I"],
                "sections": {
                    "I": {
                        "heading": "Intent",
                        "intent": "constraints",
                        "presence": "required",
                    }
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (slice_dir / "section-kw-criteria.md").write_text(
        "## I\n\n| KW | Verifiable intent attributes |\n|----|------------------------------|\n"
        "| KW0 | unnamed |\n| KW1 | readable |\n| KW2 | traceable |\n| KW3 | boundary-clear |\n",
        encoding="utf-8",
    )


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


def test_cleared_requires_target_and_fresh_frontier(tmp_path: Path):
    _write_registry_and_kw(tmp_path)
    add_opens(tmp_path, opens=[], detect=_detect_meta(tmp_path, []))
    cleared = check_close(tmp_path, mode="cleared")
    assert cleared["ok"] is False
    assert any("below target" in item for item in cleared["reasons"])
    assert check_close(tmp_path, mode="hard-skip")["ok"] is True

    set_frontier(tmp_path, "I", 3)
    stale = check_close(tmp_path, mode="cleared")
    assert stale["ok"] is False
    assert any("frontier digest" in item for item in stale["reasons"])

    add_opens(tmp_path, opens=[], detect=_detect_meta(tmp_path, []))
    assert check_close(tmp_path, mode="cleared")["ok"] is True


def test_detect_rejects_unknown_registry_lens(tmp_path: Path):
    _write_registry_and_kw(tmp_path)
    with pytest.raises(ValueError, match="section-registry"):
        add_opens(
            tmp_path,
            opens=[_candidate(lens="NOPE")],
            detect=_detect_meta(tmp_path, [_candidate(lens="NOPE")]),
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


def test_cleared_fails_without_registry(tmp_path: Path):
    add_opens(tmp_path, opens=[], detect=_detect_meta(tmp_path, []))
    cleared = check_close(tmp_path, mode="cleared")
    assert cleared["ok"] is False
    assert any("section-registry" in item for item in cleared["reasons"])
    assert any("KW criteria missing" in item for item in cleared["reasons"])
