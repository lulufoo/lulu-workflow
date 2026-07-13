#!/usr/bin/env python3
"""Schema and I/O for revision ``_facts.json`` (compose fact-first SoT).

Design rationale (source repo, why-only): docs/biz/compose-fact-first-theory/compose-fact-first-display-layer-design.md §3.1;
K1 ``source`` field: docs/biz/compose-fact-first-theory/compose-fact-first-k1-pd-design.md §3.

Shape: JSON array of ``{id, text, lens_tags}`` plus optional ``source``
(non-empty string array; Step-3-derived facts only) — no envelope.

``_facts.json`` replaces the single-``home`` ``_partition.json`` atom for the
fact-first display layer (increment 1, M1). A fact's ``lens_tags`` is an N:M
membership set (zero, one, or many lens keys) — deliberately **not** a single
``home``. Empty ``lens_tags`` is schema-legal (Q1 quarantine candidate,
audited downstream by Step 6 gates, not blocked here). Display placement
(``display_home`` / ``form_lens`` / chapter membership) is **not** a fact
field — it lives in ``_chapters.json`` (chapters_schema.py) to avoid double
bookkeeping (Grok review Blocker#1).

``source`` is private provenance (lightweight strings / upstream ``F-id``
hints). Gates never read it. K1 does not enforce referential integrity on
``F-id`` strings inside ``source`` (typed ``derives-from`` edges = increment 2).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

FACTS_BASENAME = "_facts.json"
_FACT_ID_RE = re.compile(r"^F-(\d+)$")
_FACT_REQUIRED = ("id", "text", "lens_tags")
_FACT_OPTIONAL = frozenset({"source"})


def facts_path(revision_dir: Path) -> Path:
    return Path(revision_dir) / FACTS_BASENAME


def _validate_source(prefix: str, source: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(source, list):
        errors.append(f"{prefix}.source must be an array when present")
        return errors
    if not source:
        errors.append(f"{prefix}.source must be a non-empty array when present")
        return errors
    for s_index, item in enumerate(source):
        if not isinstance(item, str) or not item.strip():
            errors.append(
                f"{prefix}.source[{s_index}] must be a non-empty string",
            )
    return errors


def validate_facts(
    facts: Any,
    *,
    allowed_lenses: list[str] | None = None,
) -> list[str]:
    """Return validation errors for a facts array."""
    errors: list[str] = []
    if not isinstance(facts, list):
        return ["facts root must be a JSON array"]
    if not facts:
        return ["facts array must not be empty"]

    allowed = {l.strip().upper() for l in (allowed_lenses or []) if str(l).strip()}
    seen_ids: set[str] = set()
    expected_n = 1

    for index, entry in enumerate(facts):
        prefix = f"facts[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in _FACT_REQUIRED:
            if field not in entry:
                errors.append(f"{prefix}: missing {field}")

        fact_id = entry.get("id")
        if not isinstance(fact_id, str) or not fact_id.strip():
            errors.append(f"{prefix}.id must be a non-empty string")
        else:
            fid = fact_id.strip()
            match = _FACT_ID_RE.match(fid)
            if not match:
                errors.append(f"{prefix}.id must match F-<n> (got {fid!r})")
            else:
                n = int(match.group(1))
                if n != expected_n:
                    errors.append(
                        f"{prefix}.id must be F-{expected_n} (got {fid!r}; "
                        "ids must be contiguous from F-1)",
                    )
                expected_n += 1
            if fid in seen_ids:
                errors.append(f"{prefix}.id duplicate: {fid!r}")
            seen_ids.add(fid)

        text = entry.get("text")
        if not isinstance(text, str) or not text.strip():
            errors.append(f"{prefix}.text must be a non-empty string")

        tags = entry.get("lens_tags")
        if not isinstance(tags, list):
            errors.append(f"{prefix}.lens_tags must be an array")
        else:
            seen_tags: set[str] = set()
            for t_index, tag in enumerate(tags):
                if not isinstance(tag, str) or not tag.strip():
                    errors.append(
                        f"{prefix}.lens_tags[{t_index}] must be a non-empty string",
                    )
                    continue
                tag_key = tag.strip().upper()
                if tag_key != tag.strip():
                    errors.append(
                        f"{prefix}.lens_tags[{t_index}] must be uppercase lens key",
                    )
                if tag_key in seen_tags:
                    errors.append(f"{prefix}.lens_tags duplicate: {tag_key!r}")
                seen_tags.add(tag_key)
                if allowed and tag_key not in allowed:
                    errors.append(
                        f"{prefix}.lens_tags[{t_index}] {tag_key!r} not in section_order "
                        f"{sorted(allowed)}",
                    )
            # Empty lens_tags is legal here by design (Q1 quarantine candidate).

        if "source" in entry:
            if entry["source"] is None:
                errors.append(
                    f"{prefix}.source must be an array when present "
                    "(null is not allowed; omit the field instead)",
                )
            else:
                errors.extend(_validate_source(prefix, entry["source"]))

        extra = set(entry) - set(_FACT_REQUIRED) - _FACT_OPTIONAL
        if extra:
            errors.append(f"{prefix}: unexpected fields {sorted(extra)}")

    return errors


def normalize_fact(entry: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": str(entry["id"]).strip(),
        "text": str(entry["text"]).strip(),
        "lens_tags": [str(t).strip().upper() for t in entry.get("lens_tags", [])],
    }
    if "source" in entry and entry["source"] is not None:
        out["source"] = [str(s).strip() for s in entry["source"]]
    return out


def load_facts(path: Path) -> list[dict[str, Any]]:
    """Load and validate facts file; raise ValueError on failure."""
    if not path.is_file():
        raise ValueError(f"facts file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid facts JSON: {exc}") from exc
    errors = validate_facts(data)
    if errors:
        raise ValueError("; ".join(errors))
    return [normalize_fact(entry) for entry in data]


def save_facts(
    path: Path,
    facts: list[dict[str, Any]],
    *,
    allowed_lenses: list[str] | None = None,
) -> None:
    """Validate and write facts array (preserves optional ``source``)."""
    normalized = [normalize_fact(f) for f in facts]
    errors = validate_facts(normalized, allowed_lenses=allowed_lenses)
    if errors:
        raise ValueError("; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def filter_by_lens(facts: list[dict[str, Any]], lens: str) -> list[dict[str, str]]:
    """Return facts tagged with one lens — addressable ``{id,text}``, never
    dissolved into prose (unlike Partition's ``filter_i_star``): a fact keeps
    its identity because it may also be tagged to other lenses (N:M)."""
    key = lens.strip().upper()
    return [
        {"id": f["id"], "text": f["text"]}
        for f in facts
        if key in f.get("lens_tags", [])
    ]


def lenses_present(facts: list[dict[str, Any]]) -> dict[str, int]:
    """Count of facts per lens tag. Sum may exceed len(facts) (N:M)."""
    counts: dict[str, int] = {}
    for fact in facts:
        for tag in fact.get("lens_tags", []):
            counts[tag] = counts.get(tag, 0) + 1
    return counts


def unlensed_fact_ids(facts: list[dict[str, Any]]) -> list[str]:
    """Facts with empty lens_tags — Q1 quarantine audit candidates."""
    return [f["id"] for f in facts if not f.get("lens_tags")]
