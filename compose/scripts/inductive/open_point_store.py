#!/usr/bin/env python3
"""Unique writer for Open-point opens, state, batches, receipts, and txn.

The caller must already hold ``compose_state_lock`` on the working slice.
This module never takes the lock. Extra txn targets may include
``g4-recompose-report.json`` and slice ``inductive-gate-state.json``.
``None`` deletes a target after recording before/after digests.

Design rationale:
docs/domain/archive/compose/archive-37.0/compose-g3-detect-execution-closure-design.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_SCHEMA = _HERE / "schema"
_SECTION = _HERE.parent / "section"
_SESSION = _HERE.parent / "schema" / "session"
_IO = _HERE.parent / "io"
_CORE = _HERE.parent / "core"
for _path in (_HERE, _SCHEMA, _SECTION, _SESSION, _IO, _CORE):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from compose_state_lock import canonical_digest, durable_unlink, durable_write_json  # noqa: E402
from g4_recompose_report_schema import normalize_report, validate_report  # noqa: E402
from inductive_gate_state_schema import normalize_gate_state, validate_gate_state  # noqa: E402
from l_ledger_schema import l_ledger_path, load_l_ledger  # noqa: E402
from open_point_batch_schema import (  # noqa: E402
    empty_open_point_batches,
    load_open_point_batches,
    mint_batch_id,
    next_batch_seq,
    normalize_open_point_batches,
    open_point_batches_path,
    save_open_point_batches,
    validate_open_point_batches,
)
from lens_frontier_schema import (  # noqa: E402
    FRONTIER_BASENAME,
    default_lens_entry,
    init_frontier_from_keys,
    lens_frontier_path,
    load_lens_frontier,
    merge_missing_keys,
    normalize_lens_frontier,
    save_lens_frontier,
    slice_kw_criteria,
    target_kw_for_slice,
    validate_lens_frontier,
)
from open_point_detect_receipt_schema import (  # noqa: E402
    empty_open_point_receipts,
    load_open_point_receipts,
    mint_receipt_id,
    next_receipt_seq,
    normalize_open_point_receipts,
    open_point_receipts_path,
    save_open_point_receipts,
    validate_open_point_receipts,
)
from open_point_state_schema import (  # noqa: E402
    empty_open_point_state,
    load_open_point_state,
    normalize_open_point_state,
    open_point_state_path,
    save_open_point_state,
    validate_open_point_state,
)
from open_point_transaction_schema import (  # noqa: E402
    load_open_point_txn,
    open_point_txn_path,
    save_open_point_txn,
)
from opens_schema import (  # noqa: E402
    DETECT_MEANS,
    blocking_open_items,
    load_opens,
    mint_open_id,
    next_open_seq,
    normalize_open,
    opens_path,
    save_opens,
    validate_opens,
)

FACTS_BASENAME = "_facts.json"
LENS_BASENAME = "section-registry.json"

_WRITERS = {
    "inductive-opens.json": save_opens,
    "open-point-state.json": save_open_point_state,
    "open-point-batches.json": save_open_point_batches,
    "open-point-detect-receipts.json": save_open_point_receipts,
    FRONTIER_BASENAME: save_lens_frontier,
}
_EXTRA_TARGETS = frozenset(
    {"g4-recompose-report.json", "inductive-gate-state.json"}
)
DELETE_AFTER_DIGEST = canonical_digest(None)


class OpenPointError(ValueError):
    """Base store error."""


class StaleError(OpenPointError):
    def __init__(self, message: str = "stale") -> None:
        super().__init__(message)


class RepairRequired(OpenPointError):
    def __init__(self, message: str = "repair_required") -> None:
        super().__init__(message)


def assert_slice_writable(slice_dir: Path) -> None:
    """Refuse writes when a parent ledger marks the slice frozen or non-focus."""
    root = Path(slice_dir).resolve().parent
    if not l_ledger_path(root).is_file():
        return
    ledger = load_l_ledger(root)
    slice_id = Path(slice_dir).resolve().name
    cell = ledger.get("by_id", {}).get(slice_id)
    if not isinstance(cell, dict):
        return
    if cell.get("frozen") is True:
        raise OpenPointError(f"slice {slice_id} is frozen; writes refused")
    if str(ledger.get("focus")) != slice_id:
        raise OpenPointError(f"slice {slice_id} is not the ledger focus; writes refused")


def _read_json(path: Path) -> Any | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _json_or_list(path: Path) -> Any:
    data = _read_json(path)
    return [] if data is None else data


def facts_snapshot(slice_dir: Path) -> Any:
    return _json_or_list(Path(slice_dir) / FACTS_BASENAME)


def lens_snapshot(slice_dir: Path) -> Any:
    return _json_or_list(Path(slice_dir) / LENS_BASENAME)


def facts_digest(slice_dir: Path) -> str:
    return canonical_digest(facts_snapshot(slice_dir))


def lens_digest(slice_dir: Path) -> str:
    return canonical_digest(lens_snapshot(slice_dir))


def registry_lens_keys(snapshot: Any) -> list[str]:
    if not isinstance(snapshot, dict):
        return []
    order = snapshot.get("section_order")
    if isinstance(order, list) and order:
        return [str(item).strip().upper() for item in order if str(item).strip()]
    sections = snapshot.get("sections")
    if isinstance(sections, dict) and sections:
        return [str(item).strip().upper() for item in sections if str(item).strip()]
    return []


def registry_presence(snapshot: Any, lens: str) -> str:
    if not isinstance(snapshot, dict):
        return "required"
    sections = snapshot.get("sections")
    if not isinstance(sections, dict):
        return "required"
    entry = sections.get(lens) or sections.get(str(lens).upper())
    if isinstance(entry, dict):
        presence = str(entry.get("presence") or "required").strip().lower()
        if presence in {"required", "optional"}:
            return presence
    return "required"


def payable_lenses(snapshot: Any, frontier: dict[str, Any]) -> list[str]:
    entries = frontier.get("lenses") if isinstance(frontier, dict) else {}
    if not isinstance(entries, dict):
        entries = {}
    out: list[str] = []
    for lens in registry_lens_keys(snapshot):
        if registry_presence(snapshot, lens) != "required":
            continue
        entry = entries.get(lens) or {}
        if isinstance(entry, dict) and entry.get("skipped") is True:
            continue
        out.append(lens)
    return out


def frontier_snapshot(slice_dir: Path) -> dict[str, Any]:
    return load_lens_frontier(lens_frontier_path(slice_dir))


def frontier_digest(slice_dir: Path) -> str:
    return canonical_digest(frontier_snapshot(slice_dir))


def load_published_kw_raw(
    slice_dir: Path, project_root: Path | str | None = None
) -> str | None:
    roots: list[Path] = []
    if project_root:
        roots.append(Path(project_root))
    roots.append(Path(slice_dir))
    roots.append(Path(slice_dir).parent)
    for root in roots:
        path = root / "section-kw-criteria.md"
        if path.is_file():
            return path.read_text(encoding="utf-8")
    if not project_root:
        return None
    root = Path(project_root).resolve()
    try:
        from fetch_compose_framework import (  # noqa: WPS433
            FetchComposeFrameworkError,
            fetch_compose_framework,
        )
        from workflow_paths import resolve_revision_runtime_profile  # noqa: WPS433
    except ImportError:
        return None
    try:
        runtime = resolve_revision_runtime_profile(Path(slice_dir), root)
        return fetch_compose_framework(
            "section-kw-criteria",
            root,
            profile_id=runtime.profile_id,
        )
    except (OSError, ValueError, FileNotFoundError, FetchComposeFrameworkError):
        return None


def load_detect_materials(
    slice_dir: Path, project_root: Path | str | None
) -> tuple[list[dict[str, Any]], bool]:
    """Load intent refs and code_grounding. Missing project_root is true inert."""
    if not project_root:
        return [], False
    try:
        from resolved_refs_schema import intent_baseline_from_workflow  # noqa: WPS433
        from workflow_paths import resolve_revision_runtime_profile  # noqa: WPS433

        runtime = resolve_revision_runtime_profile(Path(slice_dir), Path(project_root))
        cycle_id = runtime.session_base.parent.name
        refs = intent_baseline_from_workflow(
            cycle_id, Path(project_root), runtime.profile_id
        )
        pipeline = runtime.profile_data.get("pipeline") or {}
        return [item.to_dict() for item in refs], bool(pipeline.get("code_grounding"))
    except (OSError, ValueError, FileNotFoundError, ImportError, KeyError) as exc:
        raise ValueError(f"detect session resolve failed: {exc}") from exc


def compute_inert_means(
    intent_refs: list[Any], code_grounding: bool
) -> list[str]:
    inert: list[str] = []
    if not intent_refs:
        inert.append("intent")
    if not code_grounding:
        inert.append("scan")
    return inert


def require_detect_ruler(
    slice_dir: Path, project_root: Path | str | None = None
) -> tuple[list[str], str]:
    """Return registry keys and KW raw text, or raise if the ruler is missing."""
    keys = registry_lens_keys(lens_snapshot(slice_dir))
    if not keys:
        raise ValueError("section-registry missing")
    if not lens_frontier_path(slice_dir).is_file():
        raise ValueError("lens-frontier missing")
    kw_raw = load_published_kw_raw(slice_dir, project_root)
    if not kw_raw:
        raise ValueError("KW criteria missing")
    return keys, kw_raw


def ensure_frontier(slice_dir: Path) -> dict[str, Any]:
    keys = registry_lens_keys(lens_snapshot(slice_dir))
    path = lens_frontier_path(slice_dir)
    if path.is_file():
        current = load_lens_frontier(path)
        merged = merge_missing_keys(current, keys)
        if merged != current:
            _commit(slice_dir, "frontier-init", {FRONTIER_BASENAME: merged})
            return merged
        return current
    data = init_frontier_from_keys(keys)
    _commit(slice_dir, "frontier-init", {FRONTIER_BASENAME: data})
    return data


def _file_digest(path: Path) -> str | None:
    data = _read_json(path)
    if data is None:
        return None
    return canonical_digest(data)


def _before_digest(target: dict[str, Any]) -> str | None:
    if not target.get("existed"):
        return None
    return canonical_digest(target.get("before"))


def _classify_target(path: Path, target: dict[str, Any]) -> str:
    current = _file_digest(path)
    if target.get("after_digest") == DELETE_AFTER_DIGEST:
        if current is None:
            return "after"
        if current == _before_digest(target):
            return "before"
        return "neither"
    matches_after = current is not None and current == target["after_digest"]
    matches_before = current == _before_digest(target)
    if matches_after:
        return "after"
    if matches_before:
        return "before"
    return "neither"


def reconcile(slice_dir: Path) -> None:
    txn_path = open_point_txn_path(slice_dir)
    txn = load_open_point_txn(txn_path)
    if txn is None:
        return
    classifications = [
        _classify_target(Path(slice_dir) / key, target)
        for key, target in txn["targets"].items()
    ]
    if all(item == "after" for item in classifications):
        durable_unlink(txn_path)
        return
    if any(item == "neither" for item in classifications):
        raise RepairRequired()
    for key, target in txn["targets"].items():
        path = Path(slice_dir) / key
        if target["existed"]:
            durable_write_json(path, target["before"])
        elif path.is_file():
            durable_unlink(path)
    durable_unlink(txn_path)


def _check_cross_invariants(
    opens: list[dict[str, Any]],
    state: dict[str, Any],
    batches: dict[str, Any],
) -> None:
    errors = validate_open_point_state(state)
    if errors:
        raise ValueError("; ".join(errors))
    active_batch_id = state.get("active_batch_id")
    active_open_id = state.get("active_open_id")
    batch = next(
        (item for item in batches["batches"] if item["id"] == active_batch_id),
        None,
    )
    if state["phase"] == "processing":
        if batch is None or batch.get("status") != "active":
            raise ValueError("processing requires an active batch")
    if active_open_id is None:
        return
    if batch is None or active_open_id not in batch.get("open_ids", []):
        raise ValueError("active_open_id must belong to the active batch")
    current = next((item for item in opens if item["id"] == active_open_id), None)
    if current is None or current.get("status") != "open":
        raise ValueError("active_open_id must reference a status=open item")


def load_bundle(slice_dir: Path) -> dict[str, Any]:
    reconcile(slice_dir)
    opens = load_opens(opens_path(slice_dir))
    state = load_open_point_state(open_point_state_path(slice_dir))
    batches = load_open_point_batches(open_point_batches_path(slice_dir))
    receipts = load_open_point_receipts(open_point_receipts_path(slice_dir))
    _check_cross_invariants(opens, state, batches)
    return {
        "opens": opens,
        "state": state,
        "batches": batches,
        "receipts": receipts,
    }


def _normalize_payload(name: str, value: Any) -> Any:
    if value is None:
        if name not in _WRITERS and name not in _EXTRA_TARGETS:
            raise ValueError(f"unknown open-point target {name!r}")
        return None
    if name == "inductive-opens.json":
        errors = validate_opens(value)
        if errors:
            raise ValueError("; ".join(errors))
        return [normalize_open(item) for item in value]
    if name == "open-point-state.json":
        errors = validate_open_point_state(value)
        if errors:
            raise ValueError("; ".join(errors))
        return normalize_open_point_state(value)
    if name == "open-point-batches.json":
        errors = validate_open_point_batches(value)
        if errors:
            raise ValueError("; ".join(errors))
        return normalize_open_point_batches(value)
    if name == "open-point-detect-receipts.json":
        errors = validate_open_point_receipts(value)
        if errors:
            raise ValueError("; ".join(errors))
        return normalize_open_point_receipts(value)
    if name == FRONTIER_BASENAME:
        errors = validate_lens_frontier(value)
        if errors:
            raise ValueError("; ".join(errors))
        return normalize_lens_frontier(value)
    if name == "g4-recompose-report.json":
        if not isinstance(value, dict):
            raise ValueError("g4-recompose-report must be an object")
        normalized = normalize_report(value)
        errors = validate_report(normalized)
        if errors:
            raise ValueError("; ".join(errors))
        return normalized
    if name == "inductive-gate-state.json":
        if not isinstance(value, dict):
            raise ValueError("inductive-gate-state must be an object")
        normalized = normalize_gate_state(value)
        errors = validate_gate_state(normalized)
        if errors:
            raise ValueError("; ".join(errors))
        return normalized
    raise ValueError(f"unknown open-point target {name!r}")


def _write_target(path: Path, name: str, value: Any) -> None:
    if value is None:
        if path.is_file():
            durable_unlink(path)
        return
    writer = _WRITERS.get(name)
    if writer is not None:
        writer(path, value)
        return
    durable_write_json(path, value)


def _commit(slice_dir: Path, operation: str, files: dict[str, Any]) -> None:
    reconcile(slice_dir)
    assert_slice_writable(slice_dir)
    prepared = {name: _normalize_payload(name, value) for name, value in files.items()}
    targets: dict[str, Any] = {}
    for name, value in prepared.items():
        path = Path(slice_dir) / name
        existed = path.is_file()
        targets[name] = {
            "existed": existed,
            "before": _read_json(path) if existed else None,
            "after_digest": DELETE_AFTER_DIGEST if value is None else canonical_digest(value),
        }
    save_open_point_txn(
        open_point_txn_path(slice_dir),
        {"version": 1, "operation": operation, "targets": targets},
    )
    for name, value in prepared.items():
        _write_target(Path(slice_dir) / name, name, value)
    for name, value in prepared.items():
        path = Path(slice_dir) / name
        if value is None:
            if path.is_file():
                raise ValueError(f"after digest mismatch for {name}")
            continue
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        if canonical_digest(on_disk) != targets[name]["after_digest"]:
            raise ValueError(f"after digest mismatch for {name}")
    durable_unlink(open_point_txn_path(slice_dir))


def apply_targets(slice_dir: Path, operation: str, files: dict[str, Any]) -> None:
    """Commit an explicit target map. ``None`` values delete after recording before."""
    _commit(slice_dir, operation, files)


def ensure_idle_bundle(slice_dir: Path) -> None:
    """Write a fresh idle Open-point bundle for missing files only."""
    files: dict[str, Any] = {}
    if not opens_path(slice_dir).is_file():
        files["inductive-opens.json"] = []
    if not open_point_state_path(slice_dir).is_file():
        files["open-point-state.json"] = empty_open_point_state()
    if not open_point_batches_path(slice_dir).is_file():
        files["open-point-batches.json"] = empty_open_point_batches()
    if not open_point_receipts_path(slice_dir).is_file():
        files["open-point-detect-receipts.json"] = empty_open_point_receipts()
    if not lens_frontier_path(slice_dir).is_file():
        files[FRONTIER_BASENAME] = init_frontier_from_keys(
            registry_lens_keys(lens_snapshot(slice_dir))
        )
    if files:
        _commit(slice_dir, "init-idle", files)


def _mint_opens(
    existing: list[dict[str, Any]],
    incoming: list[Any],
    *,
    default_source: dict[str, str] | None,
    allowed_lenses: list[str] | None = None,
) -> list[dict[str, Any]]:
    seq = next_open_seq(existing)
    minted: list[dict[str, Any]] = []
    allowed = {item.strip().upper() for item in (allowed_lenses or []) if item.strip()}
    for raw in incoming:
        if not isinstance(raw, dict):
            raise ValueError("open must be an object")
        item = dict(raw)
        item.pop("id", None)
        item["id"] = mint_open_id(seq)
        seq += 1
        item.setdefault("status", "open")
        if default_source is not None:
            item.setdefault("source", dict(default_source))
        lens = str(item.get("lens", "")).strip().upper()
        if not lens:
            raise ValueError("open.lens is required")
        item["lens"] = lens
        if allowed and lens not in allowed:
            raise ValueError(f"open.lens {lens!r} is not in section-registry")
        minted.append(item)
    combined = existing + minted
    errors = validate_opens(combined)
    if errors:
        raise ValueError("; ".join(errors))
    return [normalize_open(item) for item in minted]


def _new_batch(
    existing: list[dict[str, Any]],
    *,
    open_ids: list[str],
    detect_receipt_id: str | None,
) -> dict[str, Any]:
    return {
        "id": mint_batch_id(next_batch_seq(existing)),
        "status": "active",
        "detect_receipt_id": detect_receipt_id,
        "open_ids": list(open_ids),
    }


def _replace_batch(
    batches: list[dict[str, Any]], updated: dict[str, Any]
) -> list[dict[str, Any]]:
    return [updated if item["id"] == updated["id"] else item for item in batches]


def _active_batch(bundle: dict[str, Any]) -> dict[str, Any] | None:
    return next(
        (item for item in bundle["batches"]["batches"] if item["status"] == "active"),
        None,
    )


def _expected_digest(detect: dict[str, Any], name: str) -> Any:
    return detect.get(f"expected_{name}") or detect.get(name)


def _build_receipt(
    existing: list[dict[str, Any]],
    *,
    checked_lenses: list[Any],
    facts_d: str,
    lens_d: str,
    opens_d: str,
    frontier_d: str,
    raw_candidates: list[Any],
    final_open_ids: list[str],
) -> dict[str, Any]:
    return {
        "id": mint_receipt_id(next_receipt_seq(existing)),
        "checked_lenses": list(checked_lenses),
        "facts_digest": facts_d,
        "lens_digest": lens_d,
        "opens_digest": opens_d,
        "frontier_digest": frontier_d,
        "raw_candidate_count": len(raw_candidates),
        "raw_candidate_digest": canonical_digest(raw_candidates),
        "final_open_ids": list(final_open_ids),
        "zero_result": len(raw_candidates) == 0,
    }


def prepare_add_opens(
    slice_dir: Path,
    *,
    opens: list[Any],
    detect: dict[str, Any] | None = None,
    project_root: Path | str | None = None,
) -> dict[str, Any]:
    """Compute add-opens after-state without writing."""
    bundle = load_bundle(slice_dir)
    current_facts = facts_digest(slice_dir)
    current_lens = lens_digest(slice_dir)
    current_opens = canonical_digest(bundle["opens"])
    allowed = registry_lens_keys(lens_snapshot(slice_dir))

    if detect is not None:
        if not lens_frontier_path(slice_dir).is_file():
            raise ValueError("lens-frontier missing")
        current_frontier = frontier_digest(slice_dir)
        if bundle["state"]["phase"] != "idle":
            raise ValueError("detect is only legal from idle")
        if _active_batch(bundle) is not None:
            raise ValueError("detect refused: active batch exists")
        if (
            _expected_digest(detect, "facts_digest") != current_facts
            or _expected_digest(detect, "lens_digest") != current_lens
            or _expected_digest(detect, "opens_digest") != current_opens
            or _expected_digest(detect, "frontier_digest") != current_frontier
        ):
            raise StaleError()
        raw_candidates = detect.get("raw_candidates")
        if not isinstance(raw_candidates, list):
            raise ValueError("detect.raw_candidates must be a list")
        checked = detect.get("checked_lenses")
        if not isinstance(checked, list) or not checked:
            raise ValueError("detect.checked_lenses must be a non-empty list")
        intent_refs, code_grounding = load_detect_materials(slice_dir, project_root)
        current_inert = compute_inert_means(intent_refs, code_grounding)
        echoed = detect.get("inert_means")
        if not isinstance(echoed, list):
            raise ValueError("detect.inert_means must be a list")
        echoed_norm = [str(item).strip().lower() for item in echoed]
        if sorted(echoed_norm) != sorted(current_inert):
            raise ValueError("inert_means mismatch")
        for raw in opens:
            if not isinstance(raw, dict):
                raise ValueError("open must be an object")
            source = raw.get("source")
            means = ""
            if isinstance(source, dict):
                means = str(source.get("means", "")).strip().lower()
            if means not in DETECT_MEANS:
                raise ValueError(
                    "detect open source.means must be scan, intent, or probe"
                )
            if means in current_inert:
                raise ValueError(f"detect open source.means {means} is inert")
        registered = _mint_opens(
            bundle["opens"],
            opens,
            default_source=None,
            allowed_lenses=allowed,
        )
        receipt = _build_receipt(
            bundle["receipts"]["receipts"],
            checked_lenses=checked,
            facts_d=current_facts,
            lens_d=current_lens,
            opens_d=current_opens,
            frontier_d=current_frontier,
            raw_candidates=raw_candidates,
            final_open_ids=[item["id"] for item in registered],
        )
        receipts = {
            "version": 1,
            "receipts": bundle["receipts"]["receipts"] + [receipt],
        }
        if not registered:
            return {
                "files": {"open-point-detect-receipts.json": receipts},
                "opens": [],
                "state": bundle["state"],
                "batch": None,
                "receipt": receipt,
            }
        batch = _new_batch(
            bundle["batches"]["batches"],
            open_ids=[item["id"] for item in registered],
            detect_receipt_id=receipt["id"],
        )
        state = {
            "version": 1,
            "phase": "processing",
            "active_batch_id": batch["id"],
            "active_open_id": registered[0]["id"],
        }
        return {
            "files": {
                "inductive-opens.json": bundle["opens"] + registered,
                "open-point-state.json": state,
                "open-point-batches.json": {
                    "version": 1,
                    "batches": bundle["batches"]["batches"] + [batch],
                },
                "open-point-detect-receipts.json": receipts,
            },
            "opens": registered,
            "state": state,
            "batch": batch,
            "receipt": receipt,
        }

    if not opens:
        raise ValueError("human add must include at least one open")
    registered = _mint_opens(
        bundle["opens"],
        opens,
        default_source={"actor": "human", "means": "direct"},
        allowed_lenses=allowed,
    )
    batches = list(bundle["batches"]["batches"])
    active = _active_batch(bundle)
    if active is None:
        batch = _new_batch(
            batches,
            open_ids=[item["id"] for item in registered],
            detect_receipt_id=None,
        )
        batches = batches + [batch]
        state = {
            "version": 1,
            "phase": "processing",
            "active_batch_id": batch["id"],
            "active_open_id": registered[0]["id"],
        }
    else:
        batch = dict(active)
        batch["open_ids"] = list(batch["open_ids"]) + [item["id"] for item in registered]
        batches = _replace_batch(batches, batch)
        state = dict(bundle["state"])
        state["phase"] = "processing"
        state["active_batch_id"] = batch["id"]
        if not state.get("active_open_id"):
            state["active_open_id"] = registered[0]["id"]
    return {
        "files": {
            "inductive-opens.json": bundle["opens"] + registered,
            "open-point-state.json": state,
            "open-point-batches.json": {"version": 1, "batches": batches},
        },
        "opens": registered,
        "state": state,
        "batch": batch,
        "receipt": None,
    }


def add_opens(
    slice_dir: Path,
    *,
    opens: list[Any],
    detect: dict[str, Any] | None = None,
    project_root: Path | str | None = None,
) -> dict[str, Any]:
    prepared = prepare_add_opens(
        slice_dir, opens=opens, detect=detect, project_root=project_root
    )
    _commit(slice_dir, "add-opens", prepared["files"])
    return {
        "opens": prepared["opens"],
        "state": prepared["state"],
        "batch": prepared["batch"],
        "receipt": prepared["receipt"],
    }


def _require_open(bundle: dict[str, Any], open_id: str) -> dict[str, Any]:
    current = next((item for item in bundle["opens"] if item["id"] == open_id), None)
    if current is None:
        raise ValueError(f"unknown open {open_id}")
    return current


def _require_active_open(bundle: dict[str, Any], open_id: str) -> dict[str, Any]:
    current = _require_open(bundle, open_id)
    if bundle["state"].get("active_open_id") != open_id:
        raise ValueError(f"open {open_id} is not the active open")
    return current


def _patch_open(
    opens: list[dict[str, Any]], open_id: str, **fields: Any
) -> list[dict[str, Any]]:
    updated: list[dict[str, Any]] = []
    found = False
    for item in opens:
        if item["id"] != open_id:
            updated.append(item)
            continue
        found = True
        patched = dict(item)
        patched.update(fields)
        updated.append(patched)
    if not found:
        raise ValueError(f"unknown open {open_id}")
    errors = validate_opens(updated)
    if errors:
        raise ValueError("; ".join(errors))
    return [normalize_open(item) for item in updated]


def _advance_after_close(
    bundle: dict[str, Any], open_id: str, opens: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    opens_by_id = {item["id"]: item for item in opens}
    batch = dict(_require_active_batch(bundle))
    open_ids = list(batch["open_ids"])
    index = open_ids.index(open_id)
    next_id = None
    for oid in open_ids[index + 1 :] + open_ids[:index]:
        if opens_by_id.get(oid, {}).get("status") == "open":
            next_id = oid
            break
    if next_id is None:
        batch["status"] = "completed"
        state = empty_open_point_state()
    else:
        state = {
            "version": 1,
            "phase": "processing",
            "active_batch_id": batch["id"],
            "active_open_id": next_id,
        }
    batches = {
        "version": 1,
        "batches": _replace_batch(bundle["batches"]["batches"], batch),
    }
    return state, batches


def _require_active_batch(bundle: dict[str, Any]) -> dict[str, Any]:
    batch = _active_batch(bundle)
    if batch is None:
        raise ValueError("no active batch")
    return batch


def update_open(slice_dir: Path, open_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    allowed = {"question", "basis", "blocking"}
    extra = set(patch) - allowed
    if extra:
        raise ValueError(f"unexpected patch fields {sorted(extra)}")
    bundle = load_bundle(slice_dir)
    current = _require_open(bundle, open_id)
    if current.get("status") != "open":
        raise ValueError("update-open is only legal while status=open")
    opens = _patch_open(bundle["opens"], open_id, **patch)
    _commit(slice_dir, "update-open", {"inductive-opens.json": opens})
    return {"open": next(item for item in opens if item["id"] == open_id)}


def defer_open(slice_dir: Path, open_id: str, note: str) -> dict[str, Any]:
    bundle = load_bundle(slice_dir)
    _require_active_open(bundle, open_id)
    opens = _patch_open(bundle["opens"], open_id, status="deferred", note=note)
    state, batches = _advance_after_close(bundle, open_id, opens)
    _commit(
        slice_dir,
        "defer-open",
        {
            "inductive-opens.json": opens,
            "open-point-state.json": state,
            "open-point-batches.json": batches,
        },
    )
    return {"opens": opens, "state": state, "batches": batches}


def reject_open(slice_dir: Path, open_id: str, reason: str) -> dict[str, Any]:
    bundle = load_bundle(slice_dir)
    _require_active_open(bundle, open_id)
    opens = _patch_open(bundle["opens"], open_id, status="rejected", reason=reason)
    state, batches = _advance_after_close(bundle, open_id, opens)
    _commit(
        slice_dir,
        "reject-open",
        {
            "inductive-opens.json": opens,
            "open-point-state.json": state,
            "open-point-batches.json": batches,
        },
    )
    return {"opens": opens, "state": state, "batches": batches}


def preview_settle(
    slice_dir: Path, open_id: str, resolved_by: list[str]
) -> dict[str, Any]:
    """Compute settle + queue-advance after-state without writing."""
    bundle = load_bundle(slice_dir)
    if bundle["state"].get("phase") != "processing":
        raise ValueError("settle requires phase=processing")
    _require_active_open(bundle, open_id)
    opens = _patch_open(
        bundle["opens"],
        open_id,
        status="settled",
        resolved_by=list(resolved_by),
    )
    state, batches = _advance_after_close(bundle, open_id, opens)
    return {"opens": opens, "state": state, "batches": batches}


def apply_loop_after(
    slice_dir: Path,
    *,
    opens: list[dict[str, Any]],
    state: dict[str, Any],
    batches: dict[str, Any],
    operation: str = "settle-open",
) -> None:
    """Commit a previewed opens/state/batches triple. Does not remint IDs."""
    _commit(
        slice_dir,
        operation,
        {
            "inductive-opens.json": opens,
            "open-point-state.json": state,
            "open-point-batches.json": batches,
        },
    )


def settle_open(
    slice_dir: Path, open_id: str, resolved_by: list[str]
) -> dict[str, Any]:
    preview = preview_settle(slice_dir, open_id, resolved_by)
    apply_loop_after(
        slice_dir,
        opens=preview["opens"],
        state=preview["state"],
        batches=preview["batches"],
        operation="settle-open",
    )
    return preview


def skip_open(slice_dir: Path, open_id: str) -> dict[str, Any]:
    bundle = load_bundle(slice_dir)
    current = _require_active_open(bundle, open_id)
    if current.get("status") != "open":
        raise ValueError("skip requires status=open")
    opens_by_id = {item["id"]: item for item in bundle["opens"]}
    batch = dict(_require_active_batch(bundle))
    open_ids = list(batch["open_ids"])
    open_ids.remove(open_id)
    open_ids.append(open_id)
    batch["open_ids"] = open_ids
    next_id = next(
        (
            oid
            for oid in open_ids
            if opens_by_id.get(oid, {}).get("status") == "open"
        ),
        None,
    )
    state = {
        "version": 1,
        "phase": "processing",
        "active_batch_id": batch["id"],
        "active_open_id": next_id,
    }
    batches = {
        "version": 1,
        "batches": _replace_batch(bundle["batches"]["batches"], batch),
    }
    _commit(
        slice_dir,
        "skip-open",
        {"open-point-state.json": state, "open-point-batches.json": batches},
    )
    return {"state": state, "batch": batch}


def attach_code_refs(
    slice_dir: Path, open_id: str, refs: list[Any]
) -> dict[str, Any]:
    if not isinstance(refs, list) or any(
        not isinstance(item, str) or not item.strip() for item in refs
    ):
        raise ValueError("refs must be a list of non-empty strings")
    bundle = load_bundle(slice_dir)
    current = _require_open(bundle, open_id)
    existing = [str(item) for item in current.get("code_refs") or []]
    seen = set(existing)
    for ref in refs:
        cleaned = ref.strip()
        if cleaned not in seen:
            existing.append(cleaned)
            seen.add(cleaned)
    opens = _patch_open(bundle["opens"], open_id, code_refs=existing)
    _commit(slice_dir, "attach-code-refs", {"inductive-opens.json": opens})
    return {"open": next(item for item in opens if item["id"] == open_id)}


def check_close(
    slice_dir: Path,
    *,
    mode: str,
    project_root: Path | str | None = None,
) -> dict[str, Any]:
    bundle = load_bundle(slice_dir)
    reasons: list[str] = []
    if mode == "cleared":
        receipts = bundle["receipts"]["receipts"]
        frontier = frontier_snapshot(slice_dir)
        if not receipts:
            reasons.append("no detect receipt")
        else:
            latest = receipts[-1]
            if latest.get("zero_result") is not True:
                reasons.append("latest receipt is not zero_result")
            if latest.get("facts_digest") != facts_digest(slice_dir):
                reasons.append("facts digest mismatch")
            if latest.get("lens_digest") != lens_digest(slice_dir):
                reasons.append("lens digest mismatch")
            if latest.get("opens_digest") != canonical_digest(bundle["opens"]):
                reasons.append("opens digest mismatch")
            if latest.get("frontier_digest") != canonical_digest(frontier):
                reasons.append("frontier digest mismatch")
        if any(item.get("status") == "open" for item in bundle["opens"]):
            reasons.append("open items remain")
        snapshot = lens_snapshot(slice_dir)
        keys = registry_lens_keys(snapshot)
        if not keys:
            reasons.append("section-registry missing")
        kw_raw = load_published_kw_raw(slice_dir, project_root)
        if not kw_raw:
            reasons.append("KW criteria missing")
        payable = payable_lenses(snapshot, frontier)
        if payable and kw_raw:
            for lens in payable:
                kw_slice = slice_kw_criteria(kw_raw, lens)
                if kw_slice is None:
                    reasons.append(f"KW criteria missing for {lens}")
                    continue
                try:
                    target = target_kw_for_slice(kw_slice)
                except ValueError:
                    reasons.append(f"KW criteria missing for {lens}")
                    continue
                entry = (frontier.get("lenses") or {}).get(lens) or {}
                current_kw = int(entry.get("frontier_kw") or 0)
                if current_kw < target:
                    reasons.append(f"lens {lens} below target KW{target}")
    elif mode == "hard-skip":
        if blocking_open_items(bundle["opens"]):
            reasons.append("blocking open remains")
    else:
        raise ValueError("mode must be cleared or hard-skip")
    return {"ok": not reasons, "reasons": reasons}


def set_frontier(slice_dir: Path, lens: str, kw: int) -> dict[str, Any]:
    if not isinstance(kw, int) or isinstance(kw, bool) or kw < 0 or kw > 4:
        raise ValueError("frontier_kw must be an int 0..4")
    key = str(lens).strip().upper()
    if not key:
        raise ValueError("lens is required")
    allowed = registry_lens_keys(lens_snapshot(slice_dir))
    if allowed and key not in allowed:
        raise ValueError(f"lens {key!r} is not in section-registry")
    data = ensure_frontier(slice_dir)
    lenses = dict(data["lenses"])
    current = dict(lenses.get(key) or default_lens_entry())
    current["frontier_kw"] = kw
    lenses[key] = current
    updated = {"version": 1, "lenses": lenses}
    _commit(slice_dir, "set-frontier", {FRONTIER_BASENAME: updated})
    return updated


def frontier_skip(slice_dir: Path, lens: str, note: str) -> dict[str, Any]:
    if not isinstance(note, str) or not note.strip():
        raise ValueError("--note is required")
    key = str(lens).strip().upper()
    if not key:
        raise ValueError("lens is required")
    allowed = registry_lens_keys(lens_snapshot(slice_dir))
    if allowed and key not in allowed:
        raise ValueError(f"lens {key!r} is not in section-registry")
    data = ensure_frontier(slice_dir)
    lenses = dict(data["lenses"])
    current = dict(lenses.get(key) or default_lens_entry())
    current["skipped"] = True
    lenses[key] = current
    updated = {"version": 1, "lenses": lenses}
    _commit(slice_dir, "frontier-skip", {FRONTIER_BASENAME: updated})
    return updated


def frontier_unskip(slice_dir: Path, lens: str) -> dict[str, Any]:
    key = str(lens).strip().upper()
    if not key:
        raise ValueError("lens is required")
    data = ensure_frontier(slice_dir)
    lenses = dict(data["lenses"])
    current = dict(lenses.get(key) or default_lens_entry())
    current["skipped"] = False
    lenses[key] = current
    updated = {"version": 1, "lenses": lenses}
    _commit(slice_dir, "frontier-unskip", {FRONTIER_BASENAME: updated})
    return updated


def abandon_active_batch(slice_dir: Path) -> dict[str, Any]:
    bundle = load_bundle(slice_dir)
    active = _active_batch(bundle)
    if active is None:
        return {"state": bundle["state"], "batch": None}
    updated = dict(active)
    updated["status"] = "abandoned"
    state = empty_open_point_state()
    _commit(
        slice_dir,
        "abandon-active-batch",
        {
            "open-point-state.json": state,
            "open-point-batches.json": {
                "version": 1,
                "batches": _replace_batch(bundle["batches"]["batches"], updated),
            },
        },
    )
    return {"state": state, "batch": updated}


def active_batch_of(bundle: dict[str, Any]) -> dict[str, Any] | None:
    return _active_batch(bundle)
