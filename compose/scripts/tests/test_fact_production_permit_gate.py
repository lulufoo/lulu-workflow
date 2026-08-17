"""P1 permit-gated fact production regressions."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_COMPOSE = Path(__file__).resolve().parents[2]
_FACT_CTL = _COMPOSE / "fact-store-runner" / "scripts" / "fact_production_control.py"


def _run(*args: str) -> tuple[int, dict, str]:
    if "--revision-dir" in args:
        idx = list(args).index("--revision-dir")
        from init_working_helpers import ensure_l1_revision  # noqa: WPS433

        ensure_l1_revision(Path(args[idx + 1]))
    result = subprocess.run(
        [sys.executable, str(_FACT_CTL), *args],
        capture_output=True,
        text=True,
    )
    try:
        payload = json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {"raw": result.stdout}
    return result.returncode, payload, result.stderr


def _ack_and_consume(revision_dir: Path, proposal: dict) -> tuple[int, dict, str]:
    permit_id = proposal["permit_id"]
    slice_key = proposal["slice_key"]
    code, _, err = _run(
        "ack",
        "--revision-dir",
        str(revision_dir),
        "--permit-id",
        permit_id,
        "--slice-key",
        slice_key,
        "--digest",
        proposal["digest"],
        "--human-ack",
    )
    assert code == 0, err
    return _run(
        "consume",
        "--revision-dir",
        str(revision_dir),
        "--permit-id",
        permit_id,
        "--slice-key",
        slice_key,
    )


def test_append_requires_digest_bound_ack_before_consume(tmp_path: Path):
    facts_json = json.dumps([{"text": "A settled fact", "lens_tags": ["I"]}])
    code, proposal, err = _run(
        "propose",
        "--revision-dir",
        str(tmp_path),
        "--kind",
        "append",
        "--facts-json",
        facts_json,
    )
    assert code == 0, err
    assert proposal["preview"]["facts_after"][0]["id"] == "F-1"
    assert not (tmp_path / "L1" / "_facts.json").exists()

    code, _, err = _run(
        "ack",
        "--revision-dir",
        str(tmp_path),
        "--permit-id",
        proposal["permit_id"],
        "--slice-key",
        proposal["slice_key"],
        "--digest",
        "wrong",
        "--human-ack",
    )
    assert code != 0
    assert not (tmp_path / "L1" / "_facts.json").exists()

    code, payload, err = _ack_and_consume(tmp_path, proposal)
    assert code == 0, err
    assert payload["fact_ids"] == ["F-1"]
    assert payload["stale_signal"] is True

    code, _, _ = _run(
        "consume",
        "--revision-dir",
        str(tmp_path),
        "--permit-id",
        proposal["permit_id"],
        "--slice-key",
        proposal["slice_key"],
    )
    assert code != 0


def test_delete_preserves_surviving_stable_ids(tmp_path: Path):
    (tmp_path / "L1").mkdir(parents=True, exist_ok=True)
    (tmp_path / "L1" / "_facts.json").write_text(
        json.dumps(
            [
                {"id": "F-1", "text": "one", "lens_tags": ["I"]},
                {"id": "F-2", "text": "remove", "lens_tags": ["I"]},
                {"id": "F-3", "text": "three", "lens_tags": ["ST"]},
            ]
        ),
        encoding="utf-8",
    )
    code, proposal, err = _run(
        "propose",
        "--revision-dir",
        str(tmp_path),
        "--kind",
        "delete",
        "--id",
        "F-2",
    )
    assert code == 0, err
    assert proposal["preview"]["deleted"]["id"] == "F-2"

    code, payload, err = _ack_and_consume(tmp_path, proposal)
    assert code == 0, err
    assert payload["deleted"] == "F-2"
    facts = json.loads((tmp_path / "L1" / "_facts.json").read_text(encoding="utf-8"))
    assert [fact["id"] for fact in facts] == ["F-1", "F-3"]


def test_consume_rejects_changed_facts_baseline(tmp_path: Path):
    code, proposal, err = _run(
        "propose",
        "--revision-dir",
        str(tmp_path),
        "--kind",
        "append",
        "--facts-json",
        json.dumps([{"text": "permit fact", "lens_tags": ["I"]}]),
    )
    assert code == 0, err
    (tmp_path / "L1" / "_facts.json").write_text(
        json.dumps([{"id": "F-1", "text": "external fact", "lens_tags": ["I"]}]),
        encoding="utf-8",
    )

    code, _, err = _ack_and_consume(tmp_path, proposal)
    assert code != 0
    assert "baseline" in err.lower()


def test_only_one_active_permit_and_revoke_unblocks_next_proposal(tmp_path: Path):
    code, proposal, err = _run(
        "propose",
        "--revision-dir",
        str(tmp_path),
        "--kind",
        "append",
        "--facts-json",
        json.dumps([{"text": "first", "lens_tags": ["I"]}]),
    )
    assert code == 0, err
    code, _, err = _run(
        "propose",
        "--revision-dir",
        str(tmp_path),
        "--kind",
        "append",
        "--facts-json",
        json.dumps([{"text": "second", "lens_tags": ["I"]}]),
    )
    assert code != 0
    assert "active permit" in err.lower()

    code, _, err = _run(
        "revoke",
        "--revision-dir",
        str(tmp_path),
        "--permit-id",
        proposal["permit_id"],
        "--slice-key",
        proposal["slice_key"],
    )
    assert code == 0, err
    code, _, err = _run(
        "propose",
        "--revision-dir",
        str(tmp_path),
        "--kind",
        "append",
        "--facts-json",
        json.dumps([{"text": "second", "lens_tags": ["I"]}]),
    )
    assert code == 0, err


def _open_item(open_id: str = "O-1", **overrides: object) -> dict:
    item = {
        "id": open_id,
        "status": "open",
        "source": {"actor": "ai", "means": "detect"},
        "question": "q",
        "basis": "evidence",
        "blocking": True,
        "lens": "I",
    }
    item.update(overrides)
    return item


def _seed_open_loop(
    slice_dir: Path,
    *,
    opens: list[dict] | None = None,
    active_open_id: str = "O-1",
) -> None:
    slice_dir.mkdir(parents=True, exist_ok=True)
    items = opens if opens is not None else [_open_item()]
    (slice_dir / "inductive-opens.json").write_text(
        json.dumps(items),
        encoding="utf-8",
    )
    (slice_dir / "open-point-state.json").write_text(
        json.dumps(
            {
                "version": 1,
                "phase": "processing",
                "active_batch_id": "B-1",
                "active_open_id": active_open_id,
            }
        ),
        encoding="utf-8",
    )
    (slice_dir / "open-point-batches.json").write_text(
        json.dumps(
            {
                "version": 1,
                "batches": [
                    {
                        "id": "B-1",
                        "status": "active",
                        "detect_receipt_id": None,
                        "open_ids": [item["id"] for item in items],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _propose_settle(revision_dir: Path, open_id: str = "O-1") -> tuple[int, dict, str]:
    return _run(
        "propose",
        "--revision-dir",
        str(revision_dir),
        "--kind",
        "settle_open",
        "--open-id",
        open_id,
        "--facts-json",
        json.dumps([{"text": "settled from open", "lens_tags": ["I"]}]),
    )


def _ack(revision_dir: Path, proposal: dict) -> tuple[int, dict, str]:
    return _run(
        "ack",
        "--revision-dir",
        str(revision_dir),
        "--permit-id",
        proposal["permit_id"],
        "--slice-key",
        proposal["slice_key"],
        "--digest",
        proposal["digest"],
        "--human-ack",
    )


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _import_fact_control():
    sys.path.insert(0, str(_COMPOSE / "scripts"))
    sys.path.insert(0, str(_COMPOSE / "scripts" / "inductive"))
    sys.path.insert(0, str(_COMPOSE / "fact-store-runner" / "scripts"))
    import fact_production_control as fpc  # noqa: WPS433

    return fpc


def test_settle_open_consumes_exact_open_precondition(tmp_path: Path):
    _seed_open_loop(tmp_path / "L1")
    code, proposal, err = _propose_settle(tmp_path)
    assert code == 0, err
    permit = _read_json(tmp_path / "L1" / "_fact-production-permits.json")["permits"][0]
    for key in (
        "facts_after",
        "facts_file_exists_after",
        "opens_after",
        "opens_file_exists_after",
        "state_after",
        "state_file_exists_after",
        "batches_after",
        "batches_file_exists_after",
        "settled",
        "fact_ids",
    ):
        assert key in permit["payload"]
    for key in (
        "facts_before",
        "facts_file_exists_before",
        "opens_before",
        "opens_file_exists_before",
        "state_before",
        "state_file_exists_before",
        "batches_before",
        "batches_file_exists_before",
    ):
        assert key in permit["snapshot"]
    for key in (
        "facts_digest",
        "facts_file_exists",
        "opens_digest",
        "opens_file_exists",
        "state_digest",
        "state_file_exists",
        "batches_digest",
        "batches_file_exists",
    ):
        assert key in permit["precondition"]

    code, payload, err = _ack_and_consume(tmp_path, proposal)
    assert code == 0, err
    assert payload["settled"] == "O-1"
    facts = _read_json(tmp_path / "L1" / "_facts.json")
    assert facts[0]["id"] == "F-1"
    opens = _read_json(tmp_path / "L1" / "inductive-opens.json")
    assert opens[0]["status"] == "settled"
    assert opens[0]["resolved_by"] == ["F-1"]
    state = _read_json(tmp_path / "L1" / "open-point-state.json")
    assert state["phase"] == "idle"
    assert state["active_batch_id"] is None
    assert state["active_open_id"] is None
    batches = _read_json(tmp_path / "L1" / "open-point-batches.json")
    assert batches["batches"][0]["status"] == "completed"


def test_settle_open_two_open_batch_advances_active_open(tmp_path: Path):
    _seed_open_loop(
        tmp_path / "L1",
        opens=[_open_item("O-1"), _open_item("O-2", question="q2")],
        active_open_id="O-1",
    )
    code, proposal, err = _propose_settle(tmp_path, "O-1")
    assert code == 0, err
    code, payload, err = _ack_and_consume(tmp_path, proposal)
    assert code == 0, err
    assert payload["settled"] == "O-1"
    opens = _read_json(tmp_path / "L1" / "inductive-opens.json")
    assert opens[0]["status"] == "settled"
    assert opens[0]["resolved_by"] == ["F-1"]
    assert opens[1]["status"] == "open"
    state = _read_json(tmp_path / "L1" / "open-point-state.json")
    assert state["phase"] == "processing"
    assert state["active_open_id"] == "O-2"
    batches = _read_json(tmp_path / "L1" / "open-point-batches.json")
    assert batches["batches"][0]["status"] == "active"


def test_propose_settle_fails_when_open_is_not_active(tmp_path: Path):
    _seed_open_loop(
        tmp_path / "L1",
        opens=[_open_item("O-1"), _open_item("O-2", question="q2")],
        active_open_id="O-1",
    )
    code, _, err = _propose_settle(tmp_path, "O-2")
    assert code != 0
    assert "active" in err.lower()

    (tmp_path / "L1" / "open-point-state.json").write_text(
        json.dumps(
            {
                "version": 1,
                "phase": "idle",
                "active_batch_id": None,
                "active_open_id": None,
            }
        ),
        encoding="utf-8",
    )
    code, _, err = _propose_settle(tmp_path, "O-1")
    assert code != 0


def test_consume_rejects_state_or_batches_digest_drift(tmp_path: Path):
    _seed_open_loop(tmp_path / "L1")
    code, proposal, err = _propose_settle(tmp_path)
    assert code == 0, err
    code, _, err = _ack(tmp_path, proposal)
    assert code == 0, err

    state_path = tmp_path / "L1" / "open-point-state.json"
    original_state = state_path.read_text(encoding="utf-8")
    state_path.write_text(
        json.dumps(
            {
                "version": 1,
                "phase": "idle",
                "active_batch_id": None,
                "active_open_id": None,
            }
        ),
        encoding="utf-8",
    )
    code, _, err = _run(
        "consume",
        "--revision-dir",
        str(tmp_path),
        "--permit-id",
        proposal["permit_id"],
        "--slice-key",
        proposal["slice_key"],
    )
    assert code != 0
    assert "baseline" in err.lower()

    state_path.write_text(original_state, encoding="utf-8")
    batches_path = tmp_path / "L1" / "open-point-batches.json"
    batches = _read_json(batches_path)
    batches["batches"].append(
        {
            "id": "B-2",
            "status": "completed",
            "detect_receipt_id": None,
            "open_ids": ["O-1"],
        }
    )
    batches_path.write_text(json.dumps(batches), encoding="utf-8")
    code, _, err = _run(
        "consume",
        "--revision-dir",
        str(tmp_path),
        "--permit-id",
        proposal["permit_id"],
        "--slice-key",
        proposal["slice_key"],
    )
    assert code != 0
    assert "baseline" in err.lower()


def test_settle_open_failure_reconciles_to_acknowledged(tmp_path: Path, monkeypatch):
    _seed_open_loop(tmp_path / "L1")
    code, proposal, err = _propose_settle(tmp_path)
    assert code == 0, err
    code, _, err = _ack(tmp_path, proposal)
    assert code == 0, err

    fpc = _import_fact_control()

    def _boom(*_args, **_kwargs):  # noqa: ANN001
        raise OSError("permission denied")

    monkeypatch.setattr(fpc, "apply_loop_after", _boom)
    code = fpc.main(
        [
            "consume",
            "--revision-dir",
            str(tmp_path),
            "--permit-id",
            proposal["permit_id"],
            "--slice-key",
            proposal["slice_key"],
        ]
    )
    assert code != 0
    assert not (tmp_path / "L1" / "_facts.json").exists()
    store = _read_json(tmp_path / "L1" / "_fact-production-permits.json")
    assert store["permits"][0]["state"] == "acknowledged"
    opens = _read_json(tmp_path / "L1" / "inductive-opens.json")
    assert opens[0]["status"] == "open"
    state = _read_json(tmp_path / "L1" / "open-point-state.json")
    assert state["phase"] == "processing"
    assert state["active_open_id"] == "O-1"


def test_settle_crash_facts_after_loop_before_requires_repair(tmp_path: Path):
    _seed_open_loop(tmp_path / "L1")
    code, proposal, err = _propose_settle(tmp_path)
    assert code == 0, err
    code, _, err = _ack(tmp_path, proposal)
    assert code == 0, err

    store_path = tmp_path / "L1" / "_fact-production-permits.json"
    store = _read_json(store_path)
    permit = store["permits"][0]
    (tmp_path / "L1" / "_facts.json").write_text(
        json.dumps(permit["payload"]["facts_after"]),
        encoding="utf-8",
    )
    permit["state"] = "consuming"
    store_path.write_text(json.dumps(store), encoding="utf-8")

    code, payload, err = _run(
        "reconcile",
        "--revision-dir",
        str(tmp_path),
        "--permit-id",
        proposal["permit_id"],
        "--slice-key",
        proposal["slice_key"],
    )
    assert code == 0, err
    assert payload["state"] == "repair_required"

    before_opens = _read_json(tmp_path / "L1" / "inductive-opens.json")
    before_state = _read_json(tmp_path / "L1" / "open-point-state.json")
    before_batches = _read_json(tmp_path / "L1" / "open-point-batches.json")
    code, payload, err = _run(
        "recover",
        "--revision-dir",
        str(tmp_path),
        "--permit-id",
        proposal["permit_id"],
        "--slice-key",
        proposal["slice_key"],
        "--resolution",
        "restore_before",
        "--human-ack",
    )
    assert code == 0, err
    assert payload["state"] == "acknowledged"
    assert not (tmp_path / "L1" / "_facts.json").exists()
    assert _read_json(tmp_path / "L1" / "inductive-opens.json") == before_opens
    assert _read_json(tmp_path / "L1" / "open-point-state.json") == before_state
    assert _read_json(tmp_path / "L1" / "open-point-batches.json") == before_batches


def test_repair_required_recovery_restores_exact_before_state(tmp_path: Path):
    code, proposal, err = _run(
        "propose",
        "--revision-dir",
        str(tmp_path),
        "--kind",
        "append",
        "--facts-json",
        json.dumps([{"text": "permit fact", "lens_tags": ["I"]}]),
    )
    assert code == 0, err
    code, _, err = _run(
        "ack",
        "--revision-dir",
        str(tmp_path),
        "--permit-id",
        proposal["permit_id"],
        "--slice-key",
        proposal["slice_key"],
        "--digest",
        proposal["digest"],
        "--human-ack",
    )
    assert code == 0, err
    (tmp_path / "L1" / "_facts.json").write_text(
        json.dumps([{"id": "F-1", "text": "unrelated", "lens_tags": ["I"]}]),
        encoding="utf-8",
    )
    store_path = tmp_path / "L1" / "_fact-production-permits.json"
    store = json.loads(store_path.read_text(encoding="utf-8"))
    store["permits"][0]["state"] = "consuming"
    store_path.write_text(json.dumps(store), encoding="utf-8")

    code, payload, err = _run(
        "reconcile",
        "--revision-dir",
        str(tmp_path),
        "--permit-id",
        proposal["permit_id"],
        "--slice-key",
        proposal["slice_key"],
    )
    assert code == 0, err
    assert payload["state"] == "repair_required"

    code, payload, err = _run(
        "recover",
        "--revision-dir",
        str(tmp_path),
        "--permit-id",
        proposal["permit_id"],
        "--slice-key",
        proposal["slice_key"],
        "--resolution",
        "restore_before",
        "--human-ack",
    )
    assert code == 0, err
    assert payload["state"] == "acknowledged"
    assert not (tmp_path / "L1" / "_facts.json").exists()
