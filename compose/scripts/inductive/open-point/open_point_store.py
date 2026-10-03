#!/usr/bin/env python3
"""Unique writer for Open-point opens, state, batches, receipts, and txn.

The caller must already hold ``compose_state_lock`` on the working slice.
This module never takes the lock. Extra txn targets may include
``g4-recompose-report.json`` and slice ``inductive-gate-state.json``.
``None`` deletes a target after recording before/after digests.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_INDUCTIVE = _HERE.parent
_COMPOSE_SCRIPTS = _INDUCTIVE.parent
_KERNEL = _COMPOSE_SCRIPTS / "_kernel"
_SESSION = _COMPOSE_SCRIPTS / "schema" / "session"
_REGISTRY = _COMPOSE_SCRIPTS / "schema" / "section" / "registry"
_TEMPLATES = _COMPOSE_SCRIPTS / "templates"
_SCHEMA_DIRS = (
    _INDUCTIVE / "schema" / "gate",
    _INDUCTIVE / "schema" / "topic",
    _INDUCTIVE / "schema" / "open-point",
    _INDUCTIVE / "schema" / "recompose",
)
for _path in (_HERE, *_SCHEMA_DIRS, _KERNEL, _SESSION, _REGISTRY, _TEMPLATES):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from compose_state_lock import canonical_digest, durable_unlink, durable_write_json  # noqa: E402
from recompose_report_schema import normalize_report, validate_report  # noqa: E402
from inductive_gate_state_schema import normalize_gate_state, validate_gate_state  # noqa: E402
from execution_state_schema import is_revision_root, load_execution_state  # noqa: E402
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
    slice_kw_rows,
    validate_lens_frontier,
)
from open_point_config_schema import detect_skip_clean_enabled  # noqa: E402
from open_point_detect_receipt_schema import (  # noqa: E402
    empty_open_point_receipts,
    load_open_point_receipts,
    mint_receipt_id,
    next_receipt_seq,
    normalize_open_point_receipts,
    open_point_receipts_path,
    parse_detect_verdicts,
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
_SKILL_TEMPLATE_ERRORS = {
    "section-registry": "section-registry missing from SKILL",
    "section-kw-criteria": "KW criteria missing from SKILL",
}

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


class RepairRequiredError(OpenPointError):
    def __init__(self, message: str = "repair_required") -> None:
        super().__init__(message)


def assert_slice_writable(slice_dir: Path) -> None:
    """Refuse writes once the owning revision's execution is Completed."""
    root = Path(slice_dir).resolve().parent
    if not is_revision_root(root):
        return
    state = load_execution_state(root)
    if state["state"] == "Completed":
        raise OpenPointError("execution is Completed; writes refused")


def _read_json(path: Path) -> Any | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _json_or_list(path: Path) -> Any:
    data = _read_json(path)
    return [] if data is None else data


def facts_snapshot(slice_dir: Path) -> Any:
    return _json_or_list(Path(slice_dir) / FACTS_BASENAME)


def _skill_template_error(
    role: str, cause: BaseException | None = None
) -> ValueError:
    base = _SKILL_TEMPLATE_ERRORS.get(role, f"{role} missing from SKILL")
    detail = str(cause).strip() if cause is not None else ""
    if detail and detail != base:
        return ValueError(f"{base}: {detail}")
    return ValueError(base)


def _skill_profile_binding(
    slice_dir: Path, project_root: Path
) -> tuple[str, Path]:
    """Resolve session profile so framework templates load from that mapping."""
    from workflow_paths import (  # noqa: WPS433
        load_profile_json,
        read_session_profile_path,
        resolve_revision_runtime_profile,
    )

    root = Path(project_root).resolve()
    try:
        runtime = resolve_revision_runtime_profile(Path(slice_dir), root)
        return runtime.profile_id, Path(runtime.profile_path)
    except (OSError, ValueError, FileNotFoundError):
        pass
    candidate = Path(slice_dir).resolve()
    for _ in range(8):
        if (candidate / "session-state.md").is_file():
            profile_path = read_session_profile_path(candidate)
            data = load_profile_json(profile_path)
            profile_id = str(data.get("profile_id") or "").strip()
            if profile_id:
                return profile_id, Path(profile_path)
            break
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    raise FileNotFoundError("session-state.md not found for SKILL template fetch")


def _skill_template_text(
    role: str, slice_dir: Path, project_root: Path | str | None
) -> str:
    """Read a compose framework template from the SKILL install. Never the slice."""
    if not project_root:
        raise _skill_template_error(role)
    try:
        from compose_template_loader import (  # noqa: WPS433
            ComposeTemplateLoadError,
            load_compose_template,
        )
    except ImportError as exc:
        raise _skill_template_error(role) from exc
    try:
        root = Path(project_root).resolve()
        profile_id, profile_path = _skill_profile_binding(Path(slice_dir), root)
        text = load_compose_template(
            role,
            root,
            profile_id=profile_id,
            profile_path=profile_path,
        )
    except (
        OSError,
        ValueError,
        FileNotFoundError,
        ComposeTemplateLoadError,
    ) as exc:
        raise _skill_template_error(role, exc) from exc
    if not str(text).strip():
        raise _skill_template_error(role)
    return text


def lens_snapshot(
    slice_dir: Path, project_root: Path | str | None = None
) -> dict[str, Any]:
    try:
        from section_registry_schema import registry_from_data  # noqa: WPS433

        data = registry_from_data(
            json.loads(
                _skill_template_text("section-registry", slice_dir, project_root)
            )
        )
    except json.JSONDecodeError as exc:
        raise _skill_template_error("section-registry", exc) from exc
    except ValueError as exc:
        raise _skill_template_error("section-registry", exc) from exc
    if not registry_lens_keys(data):
        raise _skill_template_error("section-registry")
    return data


def facts_digest(slice_dir: Path) -> str:
    return canonical_digest(facts_snapshot(slice_dir))


def registry_lens_keys(snapshot: Any) -> list[str]:
    if not isinstance(snapshot, dict):
        return []
    from section_registry_schema import lens_key_sequence  # noqa: WPS433

    return [str(item).strip().upper() for item in lens_key_sequence(snapshot) if str(item).strip()]


def detect_lens_registry(snapshot: Any) -> list[dict[str, str]]:
    """Project registry entries to Detect-needed fields, registry order."""
    sections = snapshot.get("sections") if isinstance(snapshot, dict) else {}
    if not isinstance(sections, dict):
        sections = {}
    out: list[dict[str, str]] = []
    for key in registry_lens_keys(snapshot):
        entry = sections.get(key) or sections.get(key.lower()) or {}
        if not isinstance(entry, dict):
            entry = {}
        item = {"lens": key}
        for field in ("heading", "intent", "intent_boundary"):
            value = entry.get(field)
            item[field] = value.strip() if isinstance(value, str) else ""
        out.append(item)
    return out


def facts_for_lens(facts: Any, lens: str) -> list[Any]:
    """Return full facts whose ``lens`` is ``lens``. Facts without one drop."""
    key = str(lens).strip().upper()
    if not key or not isinstance(facts, list):
        return []
    return [
        item
        for item in facts
        if isinstance(item, dict)
        and str(item.get("lens") or "").strip().upper() == key
    ]


def detect_lens_registry_entry(snapshot: Any, lens: str) -> dict[str, str]:
    key = str(lens).strip().upper()
    if not key:
        raise ValueError("unknown lens")
    for item in detect_lens_registry(snapshot):
        if item["lens"] == key:
            return item
    raise ValueError(f"unknown lens {key}")


def detect_lens_context(
    slice_dir: Path, lens: str, project_root: Path | str | None = None
) -> dict[str, Any]:
    """Everything one lens's Detect judges from, in one payload.

    KW rows still to judge (below the ledger frontier and KW0 dropped),
    one registry row, and ``id``/``text`` of facts whose ``lens`` is the given key.
    """
    key = str(lens).strip().upper()
    if not key:
        raise ValueError("unknown lens")
    entry = detect_lens_registry_entry(lens_snapshot(slice_dir, project_root), key)
    sliced = slice_kw_criteria(load_published_kw_raw(slice_dir, project_root), key)
    if sliced is None:
        raise ValueError(f"KW criteria missing for {key}")
    start = _frontier_kw(frontier_snapshot(slice_dir), key)
    return {
        "kw_criteria": slice_kw_rows(sliced, start),
        "lens_registry": entry,
        "facts_snapshot": [
            {"id": item.get("id"), "text": item.get("text")}
            for item in facts_for_lens(facts_snapshot(slice_dir), key)
        ],
    }


def detect_lens_digest(
    slice_dir: Path, lens: str, project_root: Path | str | None = None
) -> str:
    """Fingerprint of one lens's Detect payload; the ``clean`` value."""
    return canonical_digest(detect_lens_context(slice_dir, lens, project_root))


def detect_opens_snapshot(opens: Any) -> list[dict[str, str]]:
    """Project opens to Detect duplicate-check fields."""
    if not isinstance(opens, list):
        return []
    out: list[dict[str, str]] = []
    for item in opens:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "id": str(item.get("id", "")).strip(),
                "status": str(item.get("status", "")).strip(),
                "question": str(item.get("question", "")).strip(),
                "basis": str(item.get("basis", "")).strip(),
                "lens": str(item.get("lens", "")).strip().upper(),
            }
        )
    return out


def registry_supply(snapshot: Any, lens: str) -> str:
    from section_registry_schema import SUPPLY_DEFAULT, SUPPLY_VALUES  # noqa: WPS433

    if not isinstance(snapshot, dict):
        return SUPPLY_DEFAULT
    sections = snapshot.get("sections")
    if not isinstance(sections, dict):
        return SUPPLY_DEFAULT
    entry = sections.get(lens) or sections.get(str(lens).upper())
    if isinstance(entry, dict):
        supply = str(entry.get("supply") or SUPPLY_DEFAULT).strip().lower()
        if supply in SUPPLY_VALUES:
            return supply
    return SUPPLY_DEFAULT


def payable_lenses(snapshot: Any, frontier: dict[str, Any]) -> list[str]:
    entries = frontier.get("lenses") if isinstance(frontier, dict) else {}
    if not isinstance(entries, dict):
        entries = {}
    out: list[str] = []
    for lens in registry_lens_keys(snapshot):
        if registry_supply(snapshot, lens) != "ask":
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
) -> str:
    return _skill_template_text("section-kw-criteria", slice_dir, project_root)


def detect_skip_clean(
    slice_dir: Path | None = None,
    project_root: Path | str | None = None,
) -> bool:
    """Compose ``config/compose-config.json`` switch; default false."""
    del slice_dir, project_root
    return detect_skip_clean_enabled()


def pending_lenses(
    slice_dir: Path, project_root: Path | str | None = None
) -> list[str]:
    """Registry-ordered lens keys due for Detect.

    Only ``supply: ask`` lenses are asked. With ``detect_skip_clean`` on, a lens
    whose ``clean`` fingerprint still matches its current Detect payload is omitted.
    """
    frontier_lenses = frontier_snapshot(slice_dir).get("lenses") or {}
    skip = detect_skip_clean(slice_dir, project_root)
    snapshot = lens_snapshot(slice_dir, project_root)
    out: list[str] = []
    for lens in registry_lens_keys(snapshot):
        if registry_supply(snapshot, lens) != "ask":
            continue
        entry = frontier_lenses.get(lens) or default_lens_entry()
        clean = entry.get("clean")
        if skip and clean and clean == detect_lens_digest(slice_dir, lens, project_root):
            continue
        out.append(lens)
    return out


def require_detect_ruler(
    slice_dir: Path, project_root: Path | str | None = None
) -> tuple[list[str], str]:
    """Return registry keys and KW raw text, or raise if the ruler is missing."""
    keys = registry_lens_keys(lens_snapshot(slice_dir, project_root))
    if not lens_frontier_path(slice_dir).is_file():
        raise ValueError("lens-frontier missing")
    return keys, load_published_kw_raw(slice_dir, project_root)


def ensure_frontier(
    slice_dir: Path, project_root: Path | str | None = None
) -> dict[str, Any]:
    keys = registry_lens_keys(lens_snapshot(slice_dir, project_root))
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
        raise RepairRequiredError()
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
        files[FRONTIER_BASENAME] = init_frontier_from_keys([])
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


def _frontier_kw(frontier: dict[str, Any], lens: str) -> int:
    entry = (frontier.get("lenses") or {}).get(lens) or {}
    return int(entry.get("frontier_kw") or 0)


def _frontier_after_detect(
    frontier: dict[str, Any],
    verdicts: list[dict[str, Any]],
    clean_digests: dict[str, str],
) -> dict[str, Any] | None:
    """Gap verdicts move frontier_kw and drop clean; null verdicts record clean."""
    before = frontier.get("lenses") or {}
    lenses = {key: dict(entry) for key, entry in before.items()}
    for item in verdicts:
        key = item["lens"]
        current = lenses.setdefault(key, default_lens_entry())
        gap = item["gap_kw"]
        if gap is None:
            current["clean"] = clean_digests[key]
        else:
            current["frontier_kw"] = int(gap)
            current.pop("clean", None)
    if lenses == before:
        return None
    return {"version": 1, "lenses": lenses}


def _build_receipt(
    existing: list[dict[str, Any]],
    *,
    raw_candidate_count: int,
    lens_measurements: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "id": mint_receipt_id(next_receipt_seq(existing)),
        "raw_candidate_count": int(raw_candidate_count),
        "lens_measurements": list(lens_measurements),
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
    allowed = registry_lens_keys(lens_snapshot(slice_dir, project_root))

    if detect is not None:
        if not lens_frontier_path(slice_dir).is_file():
            raise ValueError("lens-frontier missing")
        if bundle["state"]["phase"] != "idle":
            raise ValueError("detect is only legal from idle")
        if _active_batch(bundle) is not None:
            raise ValueError("detect refused: active batch exists")
        pending = pending_lenses(slice_dir, project_root)
        raw_verdicts = detect.get("verdicts")
        if pending:
            verdicts = parse_detect_verdicts(raw_verdicts, registry_lenses=list(pending))
        elif raw_verdicts:
            raise ValueError("verdicts must be empty: no pending lenses")
        else:
            verdicts = []
        current_frontier_data = frontier_snapshot(slice_dir)
        for item in verdicts:
            gap = item["gap_kw"]
            start = _frontier_kw(current_frontier_data, item["lens"])
            if gap is not None and int(gap) < start:
                raise ValueError(
                    f"lens {item['lens']} gap_kw {gap} < frontier {start}"
                )
            for entry in item["candidates"]:
                if "kw" in entry and int(entry["kw"]) < start:
                    raise ValueError(
                        f"lens {item['lens']} candidate kw {entry['kw']} "
                        f"< frontier {start}"
                    )
        judged = {item["lens"]: item["gap_kw"] for item in verdicts}
        measurements = [{"lens": lens, "gap_kw": judged.get(lens)} for lens in allowed]
        raw_candidate_count = sum(len(item["candidates"]) for item in verdicts)
        clean_digests = {
            item["lens"]: detect_lens_digest(slice_dir, item["lens"], project_root)
            for item in verdicts
            if item["gap_kw"] is None
        }
        for raw in opens:
            if not isinstance(raw, dict):
                raise ValueError("open must be an object")
            source = raw.get("source")
            means = ""
            if isinstance(source, dict):
                means = str(source.get("means", "")).strip().lower()
            if means not in DETECT_MEANS:
                raise ValueError("detect open source.means must be probe")
        opens = [{k: v for k, v in raw.items() if k != "kw"} for raw in opens]
        registered = _mint_opens(
            bundle["opens"],
            opens,
            default_source=None,
            allowed_lenses=allowed,
        )
        receipt = _build_receipt(
            bundle["receipts"]["receipts"],
            raw_candidate_count=raw_candidate_count,
            lens_measurements=measurements,
        )
        receipts = {
            "version": 1,
            "receipts": bundle["receipts"]["receipts"] + [receipt],
        }
        files: dict[str, Any] = {"open-point-detect-receipts.json": receipts}
        updated_frontier = _frontier_after_detect(
            current_frontier_data, verdicts, clean_digests
        )
        if updated_frontier is not None:
            files[FRONTIER_BASENAME] = updated_frontier
        if not registered:
            return {
                "files": files,
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
        files.update(
            {
                "inductive-opens.json": bundle["opens"] + registered,
                "open-point-state.json": state,
                "open-point-batches.json": {
                    "version": 1,
                    "batches": bundle["batches"]["batches"] + [batch],
                },
            }
        )
        return {
            "files": files,
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


def _require_open_in_active_batch(
    bundle: dict[str, Any], open_id: str
) -> dict[str, Any]:
    current = _require_open(bundle, open_id)
    batch = _require_active_batch(bundle)
    if open_id not in batch["open_ids"] or current.get("status") != "open":
        raise ValueError(f"open {open_id} is not an open item of the active batch")
    return current


def process_group(bundle: dict[str, Any]) -> dict[str, Any] | None:
    """Open items of the active batch sharing the active Open's lens, active first."""
    active_id = bundle["state"].get("active_open_id")
    if not active_id:
        return None
    batch = _require_active_batch(bundle)
    by_id = {item["id"]: item for item in bundle["opens"]}
    active = by_id[active_id]
    members = [
        by_id[oid]
        for oid in batch["open_ids"]
        if oid != active_id
        and by_id.get(oid, {}).get("status") == "open"
        and by_id[oid].get("lens") == active.get("lens")
    ]
    return {"batch_id": batch["id"], "lens": active.get("lens"), "opens": [active, *members]}


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
    bundle: dict[str, Any], closed_ids: list[str], opens: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Keep the active Open while it stays open; otherwise move to the next."""
    opens_by_id = {item["id"]: item for item in opens}
    batch = dict(_require_active_batch(bundle))
    open_ids = list(batch["open_ids"])
    active = bundle["state"].get("active_open_id")
    next_id = None
    if (
        active not in closed_ids
        and opens_by_id.get(active, {}).get("status") == "open"
    ):
        next_id = active
    else:
        index = open_ids.index(active)
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
    _require_open_in_active_batch(bundle, open_id)
    opens = _patch_open(bundle["opens"], open_id, status="deferred", note=note)
    state, batches = _advance_after_close(bundle, [open_id], opens)
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
    _require_open_in_active_batch(bundle, open_id)
    opens = _patch_open(bundle["opens"], open_id, status="rejected", reason=reason)
    state, batches = _advance_after_close(bundle, [open_id], opens)
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
    state, batches = _advance_after_close(bundle, [open_id], opens)
    return {"opens": opens, "state": state, "batches": batches}


def preview_settle_group(
    slice_dir: Path, resolved_by: dict[str, list[str]]
) -> dict[str, Any]:
    """Settle several Opens of one lens in one active batch, without writing."""
    bundle = load_bundle(slice_dir)
    if bundle["state"].get("phase") != "processing":
        raise ValueError("settle requires phase=processing")
    if not resolved_by:
        raise ValueError("settle group requires at least one open")
    lenses = set()
    for open_id in resolved_by:
        lenses.add(_require_open_in_active_batch(bundle, open_id).get("lens"))
    if len(lenses) > 1:
        raise ValueError("settle group must share one lens")
    opens = bundle["opens"]
    for open_id, fact_ids in resolved_by.items():
        opens = _patch_open(
            opens, open_id, status="settled", resolved_by=list(fact_ids)
        )
    state, batches = _advance_after_close(bundle, list(resolved_by), opens)
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


def skip_open(slice_dir: Path, open_id: str | list[str]) -> dict[str, Any]:
    bundle = load_bundle(slice_dir)
    if isinstance(open_id, str):
        current = _require_active_open(bundle, open_id)
        if current.get("status") != "open":
            raise ValueError("skip requires status=open")
        skipped = [open_id]
    else:
        skipped = list(dict.fromkeys(open_id))
        for oid in skipped:
            _require_open_in_active_batch(bundle, oid)
    opens_by_id = {item["id"]: item for item in bundle["opens"]}
    batch = dict(_require_active_batch(bundle))
    open_ids = [oid for oid in batch["open_ids"] if oid not in skipped]
    open_ids.extend(oid for oid in batch["open_ids"] if oid in skipped)
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
            if latest.get("raw_candidate_count") != 0:
                reasons.append("latest receipt has raw candidates")
        if any(item.get("status") == "open" for item in bundle["opens"]):
            reasons.append("open items remain")
        try:
            snapshot = lens_snapshot(slice_dir, project_root)
            keys = registry_lens_keys(snapshot)
        except ValueError as exc:
            reasons.append(str(exc))
            snapshot = {}
            keys = []
        try:
            kw_raw = load_published_kw_raw(slice_dir, project_root)
        except ValueError as exc:
            reasons.append(str(exc))
            kw_raw = ""
        payable = payable_lenses(snapshot, frontier)
        latest_measurements = {}
        if receipts:
            latest_measurements = {
                str(item.get("lens", "")).strip().upper(): item
                for item in (receipts[-1].get("lens_measurements") or [])
                if isinstance(item, dict)
            }
        if payable and kw_raw:
            for lens in payable:
                item = latest_measurements.get(lens)
                if item is None:
                    reasons.append(f"lens {lens} unmeasured")
                elif item.get("gap_kw") is not None:
                    reasons.append(f"lens {lens} still has a KW gap")
    elif mode == "hard-skip":
        if blocking_open_items(bundle["opens"]):
            reasons.append("blocking open remains")
    else:
        raise ValueError("mode must be cleared or hard-skip")
    return {"ok": not reasons, "reasons": reasons}


def set_frontier(
    slice_dir: Path,
    lens: str,
    kw: int,
    project_root: Path | str | None = None,
) -> dict[str, Any]:
    if not isinstance(kw, int) or isinstance(kw, bool) or kw < 0 or kw > 4:
        raise ValueError("frontier_kw must be an int 0..4")
    key = str(lens).strip().upper()
    if not key:
        raise ValueError("lens is required")
    allowed = registry_lens_keys(lens_snapshot(slice_dir, project_root))
    if allowed and key not in allowed:
        raise ValueError(f"lens {key!r} is not in section-registry")
    data = ensure_frontier(slice_dir, project_root)
    lenses = dict(data["lenses"])
    current = dict(lenses.get(key) or default_lens_entry())
    current["frontier_kw"] = kw
    lenses[key] = current
    updated = {"version": 1, "lenses": lenses}
    _commit(slice_dir, "set-frontier", {FRONTIER_BASENAME: updated})
    return updated


def frontier_skip(
    slice_dir: Path,
    lens: str,
    note: str,
    project_root: Path | str | None = None,
) -> dict[str, Any]:
    if not isinstance(note, str) or not note.strip():
        raise ValueError("--note is required")
    key = str(lens).strip().upper()
    if not key:
        raise ValueError("lens is required")
    allowed = registry_lens_keys(lens_snapshot(slice_dir, project_root))
    if allowed and key not in allowed:
        raise ValueError(f"lens {key!r} is not in section-registry")
    data = ensure_frontier(slice_dir, project_root)
    lenses = dict(data["lenses"])
    current = dict(lenses.get(key) or default_lens_entry())
    current["skipped"] = True
    lenses[key] = current
    updated = {"version": 1, "lenses": lenses}
    _commit(slice_dir, "frontier-skip", {FRONTIER_BASENAME: updated})
    return updated


def frontier_unskip(
    slice_dir: Path,
    lens: str,
    project_root: Path | str | None = None,
) -> dict[str, Any]:
    key = str(lens).strip().upper()
    if not key:
        raise ValueError("lens is required")
    data = ensure_frontier(slice_dir, project_root)
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
