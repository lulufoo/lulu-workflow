#!/usr/bin/env python3
"""Schema and I/O for slice ``lens-frontier.json``.

Caches per-lens ``frontier_kw`` (0..4), skip flags, and an optional ``clean``
fingerprint. ``frontier_kw`` is the last found gap KW for that lens (resume
start; default 0). ``clean`` is the Detect payload digest recorded when the
lens was last judged gap-free; a stale digest means the lens is due again.
The script does not judge KW truth; it only stores values written through
commands.

Design rationale:
docs/domain/archive/compose/archive-42.0/compose-g3-coarsest-gap-ruler-design.md
docs/domain/archive/compose/archive-68.0/compose-g3-detect-clean-skip-design.md
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

_SECTION = Path(__file__).resolve().parents[3] / "_kernel"
if str(_SECTION) not in sys.path:
    sys.path.insert(0, str(_SECTION))

from compose_state_lock import durable_write_json  # noqa: E402

FRONTIER_BASENAME = "lens-frontier.json"
FRONTIER_VERSION = 1
_ENVELOPE_KEYS = frozenset({"version", "lenses"})
_LENS_KEYS = frozenset({"frontier_kw", "skipped", "clean"})
_H2_RE = re.compile(r"(?m)^##[ \t]+(\S+)[ \t]*$")


def lens_frontier_path(slice_dir: Path) -> Path:
    return Path(slice_dir) / FRONTIER_BASENAME


def empty_lens_frontier() -> dict[str, Any]:
    return {"version": FRONTIER_VERSION, "lenses": {}}


def default_lens_entry() -> dict[str, Any]:
    return {"frontier_kw": 0, "skipped": False}


def slice_kw_criteria(kw_raw: str, lens: str) -> str | None:
    """Return body under ``## <LENS>`` until the next ATX h2, or None."""
    key = lens.strip().upper()
    matches = list(_H2_RE.finditer(kw_raw))
    for index, match in enumerate(matches):
        if match.group(1).strip().upper() != key:
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(kw_raw)
        return kw_raw[start:end].strip("\n")
    return None


def _validate_lens_entry(prefix: str, entry: Any) -> list[str]:
    if not isinstance(entry, dict):
        return [f"{prefix} must be an object"]
    errors: list[str] = []
    extra = set(entry) - _LENS_KEYS
    if extra:
        errors.append(f"{prefix} unexpected fields {sorted(extra)}")
    kw = entry.get("frontier_kw")
    if not isinstance(kw, int) or isinstance(kw, bool) or kw < 0 or kw > 4:
        errors.append(f"{prefix}.frontier_kw must be an int 0..4")
    if not isinstance(entry.get("skipped"), bool):
        errors.append(f"{prefix}.skipped must be a bool")
    clean = entry.get("clean")
    if clean is not None and (not isinstance(clean, str) or not clean.strip()):
        errors.append(f"{prefix}.clean must be a non-empty string when present")
    return errors


def validate_lens_frontier(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return ["lens-frontier root must be an object"]
    errors: list[str] = []
    extra = set(data) - _ENVELOPE_KEYS
    if extra:
        errors.append(f"lens-frontier unexpected fields {sorted(extra)}")
    if data.get("version") != FRONTIER_VERSION:
        errors.append("lens-frontier.version must be 1")
    lenses = data.get("lenses")
    if not isinstance(lenses, dict):
        errors.append("lens-frontier.lenses must be an object")
        return errors
    for key, entry in lenses.items():
        lens = str(key).strip().upper()
        if not lens:
            errors.append("lens-frontier.lenses contains an empty key")
            continue
        errors.extend(_validate_lens_entry(f"lenses.{lens}", entry))
    return errors


def normalize_lens_frontier(data: dict[str, Any]) -> dict[str, Any]:
    lenses: dict[str, Any] = {}
    raw = data.get("lenses") or {}
    if isinstance(raw, dict):
        for key, entry in raw.items():
            lens = str(key).strip().upper()
            if not lens or not isinstance(entry, dict):
                continue
            normalized = {
                "frontier_kw": int(entry.get("frontier_kw", 0)),
                "skipped": bool(entry.get("skipped", False)),
            }
            clean = entry.get("clean")
            if isinstance(clean, str) and clean.strip():
                normalized["clean"] = clean.strip()
            lenses[lens] = normalized
    return {"version": FRONTIER_VERSION, "lenses": lenses}


def load_lens_frontier(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return empty_lens_frontier()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid lens-frontier JSON: {exc}") from exc
    errors = validate_lens_frontier(data)
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_lens_frontier(data)


def save_lens_frontier(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    errors = validate_lens_frontier(data)
    if errors:
        raise ValueError("; ".join(errors))
    normalized = normalize_lens_frontier(data)
    errors = validate_lens_frontier(normalized)
    if errors:
        raise ValueError("; ".join(errors))
    durable_write_json(path, normalized)
    return normalized


def init_frontier_from_keys(keys: list[str]) -> dict[str, Any]:
    lenses = {
        str(key).strip().upper(): default_lens_entry()
        for key in keys
        if str(key).strip()
    }
    return {"version": FRONTIER_VERSION, "lenses": lenses}


def merge_missing_keys(data: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    normalized = normalize_lens_frontier(data)
    lenses = dict(normalized["lenses"])
    for key in keys:
        lens = str(key).strip().upper()
        if lens and lens not in lenses:
            lenses[lens] = default_lens_entry()
    return {"version": FRONTIER_VERSION, "lenses": lenses}
