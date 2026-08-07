"""P1 permit-gated fact production regressions."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_COMPOSE = Path(__file__).resolve().parents[2]
_FACT_CTL = _COMPOSE / "fact-runner" / "scripts" / "fact_production_control.py"


def _run(*args: str) -> tuple[int, dict, str]:
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
    assert not (tmp_path / "_facts.json").exists()

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
    assert not (tmp_path / "_facts.json").exists()

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
    (tmp_path / "_facts.json").write_text(
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
    facts = json.loads((tmp_path / "_facts.json").read_text(encoding="utf-8"))
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
    (tmp_path / "_facts.json").write_text(
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


def test_settle_open_consumes_exact_open_precondition(tmp_path: Path):
    (tmp_path / "inductive-opens.json").write_text(
        json.dumps(
            [
                {
                    "id": "O-1",
                    "status": "open",
                    "source": {"trigger": "ai", "means": "ai_probe"},
                    "kw": 2,
                    "blocking": True,
                    "problem": "q",
                }
            ]
        ),
        encoding="utf-8",
    )
    code, proposal, err = _run(
        "propose",
        "--revision-dir",
        str(tmp_path),
        "--kind",
        "settle_open",
        "--open-id",
        "O-1",
        "--facts-json",
        json.dumps([{"text": "settled from open", "lens_tags": ["I"]}]),
    )
    assert code == 0, err

    code, payload, err = _ack_and_consume(tmp_path, proposal)
    assert code == 0, err
    assert payload["settled"] == "O-1"
    opens = json.loads((tmp_path / "inductive-opens.json").read_text(encoding="utf-8"))
    assert opens[0]["status"] == "settled"
    assert opens[0]["resolved_by"] == ["F-1"]


def test_settle_open_failure_reconciles_to_acknowledged(tmp_path: Path, monkeypatch):
    (tmp_path / "inductive-opens.json").write_text(
        json.dumps(
            [
                {
                    "id": "O-1",
                    "status": "open",
                    "source": {"trigger": "ai", "means": "ai_probe"},
                    "kw": 2,
                    "blocking": True,
                    "problem": "q",
                }
            ]
        ),
        encoding="utf-8",
    )
    code, proposal, err = _run(
        "propose",
        "--revision-dir",
        str(tmp_path),
        "--kind",
        "settle_open",
        "--open-id",
        "O-1",
        "--facts-json",
        json.dumps([{"text": "settled from open", "lens_tags": ["I"]}]),
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

    sys.path.insert(0, str(_COMPOSE / "scripts"))
    sys.path.insert(0, str(_COMPOSE / "scripts" / "inductive"))
    sys.path.insert(0, str(_COMPOSE / "fact-runner" / "scripts"))
    import fact_production_control as fpc  # noqa: E402

    def _boom(path, opens):  # noqa: ANN001
        raise OSError("permission denied")

    monkeypatch.setattr(fpc, "save_opens", _boom)
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
    assert not (tmp_path / "_facts.json").exists()
    store = json.loads(
        (tmp_path / "_fact-production-permits.json").read_text(encoding="utf-8")
    )
    assert store["permits"][0]["state"] == "acknowledged"


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
    (tmp_path / "_facts.json").write_text(
        json.dumps([{"id": "F-1", "text": "unrelated", "lens_tags": ["I"]}]),
        encoding="utf-8",
    )
    store_path = tmp_path / "_fact-production-permits.json"
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
    assert not (tmp_path / "_facts.json").exists()
