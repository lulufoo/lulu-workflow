#!/usr/bin/env python3
"""Schema and I/O for grounding-notes.json (inductive grounding receipts).

Each receipt is one sweep's shallow (whole-sweep, all unsettled sections) or
deep (single user-chosen open point) grounding result. Facts are distilled —
never source code dumps.

Adjustable thinness limits (schema constants):
  MAX_FACT_CHARS   max length per fact string
  MAX_FACTS        max facts per receipt
  MAX_CODE_REFS    max code_refs per receipt

Required fields per receipt:
  id           GN-NNN (unique, monotone)
  sweep        int — which Gate 3 sweep produced this
  mode         shallow | deep  (legacy receipts may still carry mode=g2 on disk;
               new writes reject g2)
  section      section key (required for shallow/deep)
  frontier_kw  int 0..4 — KW altitude at grounding time
  code_refs    list of "file::symbol (line)" strings
  facts        list of one-line distilled facts
  produced_by  subagent | inline
  created_at   ISO timestamp

Optional:
  ep_id                open point id (e.g. O-1; field name kept for schema compat;
                       open_id accepted as write alias) — required for mode=deep
                        (disambiguates multiple points expanded in the same
                        section within one sweep; unused for shallow)
  need_clarification    str — subagent could not proceed without user input
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Thinness limits — adjust here without changing control logic.
MAX_FACT_CHARS = 200
MAX_FACTS = 8
MAX_CODE_REFS = 12

# Write path (record/append). Legacy mode=g2 is read-tolerated only.
GROUNDING_WRITE_MODES = frozenset({"shallow", "deep"})
# Load/list: allow historical g2 receipts so old ledgers remain readable.
GROUNDING_READ_MODES = frozenset({"shallow", "deep", "g2"})
# Back-compat alias used by callers that only need the write set.
GROUNDING_MODES = GROUNDING_WRITE_MODES
PRODUCED_BY = frozenset({"subagent", "inline"})

_REQUIRED_FIELDS = (
    "id",
    "sweep",
    "mode",
    "section",
    "frontier_kw",
    "code_refs",
    "facts",
    "produced_by",
    "created_at",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def grounding_notes_path(out_dir: Path) -> Path:
    return out_dir / "grounding-notes.json"


def init_ledger() -> dict[str, Any]:
    return {"version": "1", "receipts": [], "updated_at": _now_iso()}


def validate_receipt(
    receipt: dict[str, Any], *, for_write: bool = False
) -> list[str]:
    errors: list[str] = []
    rid = str(receipt.get("id", ""))

    for field in _REQUIRED_FIELDS:
        if field not in receipt:
            errors.append(f"receipt {rid!r}: missing required field {field!r}")

    if rid and not rid.startswith("GN-"):
        errors.append(f"receipt id must start with 'GN-', got {rid!r}")

    mode = str(receipt.get("mode", "")).lower()
    allowed = GROUNDING_WRITE_MODES if for_write else GROUNDING_READ_MODES
    if mode not in allowed:
        errors.append(f"receipt {rid!r}: invalid mode {mode!r}")

    produced = str(receipt.get("produced_by", "")).lower()
    if produced not in PRODUCED_BY:
        errors.append(f"receipt {rid!r}: invalid produced_by {produced!r}")

    sweep = receipt.get("sweep")
    if not isinstance(sweep, int) or sweep < 1:
        errors.append(f"receipt {rid!r}: sweep must be a positive int")

    frontier = receipt.get("frontier_kw")
    if not isinstance(frontier, int) or not (0 <= frontier <= 4):
        errors.append(f"receipt {rid!r}: frontier_kw must be int 0..4")

    if mode in {"shallow", "deep"} and not str(receipt.get("section", "")).strip():
        errors.append(f"receipt {rid!r}: section is required for mode {mode!r}")

    if mode == "deep":
        ep = str(receipt.get("ep_id", "") or receipt.get("open_id", "")).strip()
        if not ep:
            errors.append(
                f"receipt {rid!r}: ep_id (or open_id) is required for mode 'deep'"
            )

    code_refs = receipt.get("code_refs")
    if not isinstance(code_refs, list):
        errors.append(f"receipt {rid!r}: code_refs must be a list")
    elif len(code_refs) > MAX_CODE_REFS:
        errors.append(
            f"receipt {rid!r}: code_refs exceeds max {MAX_CODE_REFS}"
        )

    facts = receipt.get("facts")
    if not isinstance(facts, list):
        errors.append(f"receipt {rid!r}: facts must be a list")
    elif len(facts) > MAX_FACTS:
        errors.append(f"receipt {rid!r}: facts exceeds max {MAX_FACTS}")
    elif isinstance(facts, list):
        for i, fact in enumerate(facts):
            if not isinstance(fact, str):
                errors.append(f"receipt {rid!r}: facts[{i}] must be a string")
            elif len(fact) > MAX_FACT_CHARS:
                errors.append(
                    f"receipt {rid!r}: facts[{i}] exceeds {MAX_FACT_CHARS} chars"
                )

    clar = receipt.get("need_clarification")
    if clar is not None and not isinstance(clar, str):
        errors.append(f"receipt {rid!r}: need_clarification must be a string")

    if isinstance(facts, list):
        has_clar = bool(str(clar or "").strip()) if clar is not None else False
        has_facts = any(str(f).strip() for f in facts)
        if not has_facts and not has_clar:
            errors.append(
                f"receipt {rid!r}: facts must be non-empty unless need_clarification is set"
            )

    return errors


def normalize_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    ep = str(receipt.get("ep_id", "") or receipt.get("open_id", "") or "")
    return {
        "id": str(receipt.get("id", "")),
        "sweep": int(receipt.get("sweep", 0)),
        "mode": str(receipt.get("mode", "")).lower(),
        "section": str(receipt.get("section", "")),
        "ep_id": ep,
        "frontier_kw": int(receipt.get("frontier_kw", 0)),
        "code_refs": list(receipt.get("code_refs") or []),
        "facts": [str(f) for f in (receipt.get("facts") or [])],
        "produced_by": str(receipt.get("produced_by", "subagent")).lower(),
        "need_clarification": receipt.get("need_clarification"),
        "created_at": receipt.get("created_at") or _now_iso(),
    }


def validate_ledger(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("version") != "1":
        errors.append(f"invalid version: {data.get('version')!r}")

    receipts = data.get("receipts")
    if not isinstance(receipts, list):
        errors.append("receipts must be a list")
        return errors

    seen: set[str] = set()
    for receipt in receipts:
        if not isinstance(receipt, dict):
            errors.append("each receipt must be an object")
            continue
        rid = str(receipt.get("id", ""))
        if rid in seen:
            errors.append(f"duplicate receipt id: {rid!r}")
        seen.add(rid)
        errors.extend(validate_receipt(receipt))

    return errors


def load_ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        return init_ledger()
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_ledger(data)
    if errors:
        raise ValueError("; ".join(errors))
    return data


def save_ledger(path: Path, data: dict[str, Any]) -> None:
    errors = validate_ledger(data)
    if errors:
        raise ValueError("; ".join(errors))
    data["updated_at"] = _now_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def next_receipt_id(ledger: dict[str, Any]) -> str:
    n = len(ledger.get("receipts") or []) + 1
    return f"GN-{n:03d}"


def _receipt_key(receipt: dict[str, Any]) -> tuple[int, str, str, str]:
    return (
        int(receipt.get("sweep", 0)),
        str(receipt.get("mode", "")).lower(),
        str(receipt.get("section", "")),
        str(receipt.get("ep_id", "") or ""),
    )


def append_receipts(
    ledger: dict[str, Any], receipts: list[dict[str, Any]]
) -> dict[str, Any]:
    updated = dict(ledger)
    existing = list(updated.get("receipts") or [])
    seen_keys = {_receipt_key(r) for r in existing}
    for raw in receipts:
        normalized = normalize_receipt(raw)
        key = _receipt_key(normalized)
        if key in seen_keys:
            raise ValueError(
                f"duplicate grounding receipt for sweep={key[0]!r} "
                f"mode={key[1]!r} section={key[2]!r}"
            )
        if not normalized["id"]:
            normalized["id"] = next_receipt_id({"receipts": existing})
        errors = validate_receipt(normalized, for_write=True)
        if errors:
            raise ValueError("; ".join(errors))
        existing.append(normalized)
        seen_keys.add(key)
    updated["receipts"] = existing
    return updated


def receipts_for_sweep(
    ledger: dict[str, Any],
    sweep: int,
    *,
    mode: str = "shallow",
    ep_id: str | None = None,
) -> list[dict[str, Any]]:
    receipts = [
        r
        for r in (ledger.get("receipts") or [])
        if r.get("sweep") == sweep and str(r.get("mode", "")).lower() == mode
    ]
    if ep_id:
        receipts = [r for r in receipts if str(r.get("ep_id", "")) == ep_id]
    return receipts


def check_sweep_coverage(
    ledger: dict[str, Any],
    sweep: int,
    unsettled: list[dict[str, Any]],
    *,
    mode: str = "shallow",
) -> dict[str, Any]:
    """Verify every unsettled section has exactly one valid receipt for this sweep."""
    if not unsettled:
        return {"ok": True, "missing": [], "errors": [], "unsettled_count": 0}

    sweep_receipts = receipts_for_sweep(ledger, sweep, mode=mode)
    by_section: dict[str, list[dict[str, Any]]] = {}
    for receipt in sweep_receipts:
        section = str(receipt.get("section", ""))
        by_section.setdefault(section, []).append(receipt)

    missing: list[str] = []
    errors: list[str] = []
    for entry in unsettled:
        section = entry["section"]
        expected_kw = entry.get("frontier_kw", 0)
        matches = by_section.get(section) or []
        if not matches:
            missing.append(section)
            errors.append(
                f"sweep {sweep}: no {mode!r} grounding receipt for unsettled section {section!r}"
            )
            continue
        if len(matches) > 1:
            errors.append(
                f"sweep {sweep}: duplicate {mode!r} grounding receipts for section {section!r}"
            )
            continue
        receipt = matches[0]
        if receipt.get("frontier_kw") != expected_kw:
            errors.append(
                f"sweep {sweep}: section {section!r} receipt frontier_kw="
                f"{receipt.get('frontier_kw')!r} != current {expected_kw!r}"
            )

    return {
        "ok": len(missing) == 0 and len(errors) == 0,
        "missing": missing,
        "errors": errors,
        "unsettled_count": len(unsettled),
        "receipt_count": len(sweep_receipts),
    }
