#!/usr/bin/env python3
"""Schema and I/O for per-section inductive-scope JSON (section-SoT).

Design SSOT: docs/biz/inductive-scope-section-sot-design.md §2 / §14.
AI never hand-writes these files — only scripts via this module (I12).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SECTION_STATUSES = frozenset({"untouched", "active", "cleared", "skipped"})
CONFIDENCES = frozenset({"direct", "inferred"})
TRIGGERS = frozenset({"human", "ai", "seed"})
MEANS = frozenset(
    {"probe", "direct", "view", "ai_scan", "intent_baseline", "scope"}
)

_DECISION_REQUIRED = ("id", "kw", "text", "trigger", "means", "confidence")
_OPEN_REQUIRED = ("id", "kw", "trigger", "means", "blocking", "problem")
_INDEX_REQUIRED = ("version", "cycle_id")

_DECISION_ID_RE = re.compile(r"^([A-Za-z0-9]+)-d(\d+)$")
_OPEN_ID_RE = re.compile(r"^([A-Za-z0-9]+)-o(\d+)$")
_DEFERRED_ID_RE = re.compile(r"^([A-Za-z0-9]+)-x(\d+)$")


def section_dir(out_dir: Path) -> Path:
    return Path(out_dir) / "inductive-scope"


def section_path(out_dir: Path, key: str) -> Path:
    return section_dir(out_dir) / f"{key}.json"


def index_path(out_dir: Path) -> Path:
    return section_dir(out_dir) / "_index.json"


def mint_decision_id(section: str, seq: int) -> str:
    return f"{section}-d{seq}"


def mint_open_id(section: str, seq: int) -> str:
    return f"{section}-o{seq}"


def mint_deferred_id(section: str, seq: int) -> str:
    return f"{section}-x{seq}"


def _max_seq(ids: list[str], pattern: re.Pattern[str], section: str) -> int:
    max_n = 0
    for item_id in ids:
        m = pattern.match(str(item_id))
        if not m:
            continue
        if m.group(1) != section:
            continue
        max_n = max(max_n, int(m.group(2)))
    return max_n


def next_decision_seq(section_doc: dict[str, Any]) -> int:
    key = str(section_doc.get("key", ""))
    ids = [d.get("id", "") for d in section_doc.get("decisions", [])]
    return _max_seq(ids, _DECISION_ID_RE, key) + 1


def next_open_seq(section_doc: dict[str, Any]) -> int:
    key = str(section_doc.get("key", ""))
    ids = [o.get("id", "") for o in section_doc.get("open", [])]
    # Also consider deferred ids that used open-style minting historically.
    ids += [d.get("id", "") for d in section_doc.get("deferred", [])]
    open_max = _max_seq(ids, _OPEN_ID_RE, key)
    deferred_max = _max_seq(ids, _DEFERRED_ID_RE, key)
    return max(open_max, deferred_max) + 1


def _validate_provenance(trigger: str, means: str, where: str) -> list[str]:
    errors: list[str] = []
    if trigger not in TRIGGERS:
        errors.append(f"{where}: invalid trigger {trigger!r}")
    if means not in MEANS:
        errors.append(f"{where}: invalid means {means!r}")
    if trigger == "seed" and means != "scope":
        errors.append(f"{where}: trigger=seed requires means=scope")
    if means == "scope" and trigger != "seed":
        errors.append(f"{where}: means=scope requires trigger=seed")
    return errors


def _validate_decision(d: dict[str, Any], section_key: str) -> list[str]:
    errors: list[str] = []
    where = f"decision {d.get('id')!r}"
    for field in _DECISION_REQUIRED:
        if field not in d:
            errors.append(f"{where}: missing required field {field!r}")

    did = str(d.get("id", ""))
    m = _DECISION_ID_RE.match(did)
    if not m:
        errors.append(f"{where}: id must match <SECTION>-dN, got {did!r}")
    elif m.group(1) != section_key:
        errors.append(
            f"{where}: id section prefix {m.group(1)!r} != section key {section_key!r}"
        )

    conf = str(d.get("confidence", "")).lower()
    if "confidence" in d and conf not in CONFIDENCES:
        errors.append(f"{where}: invalid confidence {conf!r}")

    trigger = str(d.get("trigger", "")).lower()
    means = str(d.get("means", "")).lower()
    errors.extend(_validate_provenance(trigger, means, where))

    if "code_refs" in d and d["code_refs"] is not None:
        if not isinstance(d["code_refs"], list):
            errors.append(f"{where}: code_refs must be a list")

    if "intent_ref" in d and d["intent_ref"] is not None:
        if not isinstance(d["intent_ref"], str):
            errors.append(f"{where}: intent_ref must be a string when present")

    if "kw" in d and not isinstance(d["kw"], (int, str)):
        errors.append(f"{where}: kw must be int or str")

    return errors


def _validate_open(o: dict[str, Any], section_key: str) -> list[str]:
    errors: list[str] = []
    where = f"open {o.get('id')!r}"
    for field in _OPEN_REQUIRED:
        if field not in o:
            errors.append(f"{where}: missing required field {field!r}")

    oid = str(o.get("id", ""))
    m = _OPEN_ID_RE.match(oid)
    if not m:
        errors.append(f"{where}: id must match <SECTION>-oN, got {oid!r}")
    elif m.group(1) != section_key:
        errors.append(
            f"{where}: id section prefix {m.group(1)!r} != section key {section_key!r}"
        )

    if "blocking" in o and not isinstance(o.get("blocking"), bool):
        errors.append(f"{where}: blocking must be a bool")

    if "confidence" in o and o["confidence"] is not None:
        conf = str(o["confidence"]).lower()
        if conf not in CONFIDENCES:
            errors.append(f"{where}: invalid confidence {conf!r}")

    trigger = str(o.get("trigger", "")).lower()
    means = str(o.get("means", "")).lower()
    errors.extend(_validate_provenance(trigger, means, where))

    if "code_refs" in o and o["code_refs"] is not None:
        if not isinstance(o["code_refs"], list):
            errors.append(f"{where}: code_refs must be a list")

    if "intent_ref" in o and o["intent_ref"] is not None:
        if not isinstance(o["intent_ref"], str):
            errors.append(f"{where}: intent_ref must be a string when present")

    if "hangs_under" in o and o["hangs_under"] is not None:
        if not isinstance(o["hangs_under"], str):
            errors.append(f"{where}: hangs_under must be a string when present")

    return errors


def _validate_deferred(x: dict[str, Any], section_key: str) -> list[str]:
    errors: list[str] = []
    where = f"deferred {x.get('id')!r}"
    if "id" not in x:
        errors.append(f"{where}: missing required field 'id'")
        return errors
    xid = str(x["id"])
    m_o = _OPEN_ID_RE.match(xid)
    m_x = _DEFERRED_ID_RE.match(xid)
    if not (m_o or m_x):
        errors.append(
            f"{where}: id must match <SECTION>-oN or <SECTION>-xN, got {xid!r}"
        )
    else:
        prefix = (m_o or m_x).group(1)  # type: ignore[union-attr]
        if prefix != section_key:
            errors.append(
                f"{where}: id section prefix {prefix!r} != section key {section_key!r}"
            )
    if "kw" not in x:
        errors.append(f"{where}: missing required field 'kw'")
    return errors


def validate_section(doc: dict[str, Any]) -> list[str]:
    """Return validation errors for a section document (empty = valid)."""
    errors: list[str] = []

    if "key" not in doc or not str(doc.get("key", "")).strip():
        errors.append("section: missing required field 'key'")
        section_key = ""
    else:
        section_key = str(doc["key"])

    status = str(doc.get("status", "")).lower()
    if "status" not in doc:
        errors.append("section: missing required field 'status'")
    elif status not in SECTION_STATUSES:
        errors.append(f"section: invalid status {status!r}")

    if "frontier_kw" not in doc:
        errors.append("section: missing required field 'frontier_kw'")
    else:
        fk = doc["frontier_kw"]
        if not isinstance(fk, int) or fk < 0 or fk > 4:
            errors.append(f"section: frontier_kw must be int 0..4, got {fk!r}")

    for arr_name in ("decisions", "open", "deferred"):
        if arr_name not in doc:
            errors.append(f"section: missing required field {arr_name!r}")
        elif not isinstance(doc[arr_name], list):
            errors.append(f"section: {arr_name} must be a list")

    if not isinstance(doc.get("decisions"), list):
        return errors
    if not isinstance(doc.get("open"), list):
        return errors
    if not isinstance(doc.get("deferred"), list):
        return errors

    for d in doc["decisions"]:
        if not isinstance(d, dict):
            errors.append("decision: entry must be an object")
            continue
        errors.extend(_validate_decision(d, section_key))

    for o in doc["open"]:
        if not isinstance(o, dict):
            errors.append("open: entry must be an object")
            continue
        errors.extend(_validate_open(o, section_key))

    for x in doc["deferred"]:
        if not isinstance(x, dict):
            errors.append("deferred: entry must be an object")
            continue
        errors.extend(_validate_deferred(x, section_key))

    return errors


def validate_index(doc: dict[str, Any]) -> list[str]:
    """Return validation errors for _index.json (empty = valid)."""
    errors: list[str] = []
    for field in _INDEX_REQUIRED:
        if field not in doc or doc[field] in (None, ""):
            errors.append(f"index: missing required field {field!r}")
    if "version" in doc and str(doc["version"]) not in {"1"}:
        errors.append(f"index: unsupported version {doc.get('version')!r}")
    if "last_checkpoint" in doc and doc["last_checkpoint"] is not None:
        if not isinstance(doc["last_checkpoint"], str):
            errors.append("index: last_checkpoint must be a string or null")
    return errors


def empty_section(key: str, status: str = "untouched", frontier_kw: int = 0) -> dict[str, Any]:
    return {
        "key": key,
        "status": status,
        "frontier_kw": frontier_kw,
        "decisions": [],
        "open": [],
        "deferred": [],
    }


def list_section_keys(out_dir: Path) -> list[str]:
    """Return section keys that have a JSON file on disk (excluding _index)."""
    d = section_dir(out_dir)
    if not d.exists():
        return []
    return sorted(
        p.stem for p in d.glob("*.json") if p.name != "_index.json"
    )


def blocking_open_items(
    out_dir: Path, section: str | None = None
) -> list[dict[str, Any]]:
    """Open items with blocking=True from section JSON (section-SoT Exit predicate)."""
    keys = [section] if section else list_section_keys(out_dir)
    found: list[dict[str, Any]] = []
    for key in keys:
        if not key:
            continue
        path = section_path(out_dir, key)
        if not path.exists():
            continue
        try:
            doc = load_section(out_dir, key)
        except (ValueError, FileNotFoundError):
            continue
        for o in doc.get("open") or []:
            if o.get("blocking") is True:
                item = dict(o)
                item.setdefault("section", key)
                found.append(item)
    return found


def load_section(out_dir: Path, key: str) -> dict[str, Any]:
    path = section_path(out_dir, key)
    if not path.exists():
        raise FileNotFoundError(f"section file not found: {path}")
    doc = json.loads(path.read_text(encoding="utf-8"))
    errs = validate_section(doc)
    if errs:
        raise ValueError(f"invalid section {key}: " + "; ".join(errs))
    return doc


def save_section(out_dir: Path, doc: dict[str, Any]) -> Path:
    errs = validate_section(doc)
    if errs:
        raise ValueError("invalid section: " + "; ".join(errs))
    path = section_path(out_dir, str(doc["key"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def load_index(out_dir: Path) -> dict[str, Any]:
    path = index_path(out_dir)
    if not path.exists():
        raise FileNotFoundError(f"index file not found: {path}")
    doc = json.loads(path.read_text(encoding="utf-8"))
    errs = validate_index(doc)
    if errs:
        raise ValueError("invalid index: " + "; ".join(errs))
    return doc


def save_index(out_dir: Path, doc: dict[str, Any]) -> Path:
    errs = validate_index(doc)
    if errs:
        raise ValueError("invalid index: " + "; ".join(errs))
    path = index_path(out_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def ensure_section(out_dir: Path, key: str) -> dict[str, Any]:
    """Load section or create an empty untouched document on disk."""
    path = section_path(out_dir, key)
    if path.exists():
        return load_section(out_dir, key)
    doc = empty_section(key)
    save_section(out_dir, doc)
    return doc
