#!/usr/bin/env python3
"""Schema and I/O for revision ``_facts.json`` (compose fact-first SoT).

Design rationale (source repo, why-only): docs/domain/compose/mechanism-ssot/compose-fact-architecture.md;
process how archive: docs/domain/compose/archive-2.0/compose-fact-first-display-layer-design.md §3.1;
K1 ``source``: living docs/domain/compose/mechanism-ssot/compose-fact-architecture.md;
process how: docs/domain/compose/archive-2.0/compose-fact-first-k1-pd-design.md §3.

Shape: JSON array of ``{id, text, lens_tags}`` plus optional ``source``
(non-empty string array; Step-3-derived facts only) and optional ``origin``
(``{type, ref}`` structured provenance; K4 Phase 1a) — no envelope.

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

``origin`` (K4) is structured provenance: ``type ∈ {seed, discovered, derived}``
and non-empty ``ref`` string array (scope anchors / open ids / upstream F-ids).
Optional and backward-compatible — existing facts without ``origin`` remain valid.

``anchors`` (P4 init-fidelity) is a fact's born-with machine-relevant evidence:
an array of ``{kind, value}`` where ``kind ∈ ANCHOR_KINDS``. Optional and
backward-compatible; empty normalizes to omission. Lens-invariant substance
(not presentation) — the L6 gate requires each anchor to survive into the body.
Inductive non-empty ``lens_tags`` is enforced on the inductive write path only
(not here) — see K4 design §4.3.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

FACTS_BASENAME = "_facts.json"
_FACT_ID_RE = re.compile(r"^F-(\d+)$")
_FACT_REQUIRED = ("id", "text", "lens_tags")
_FACT_OPTIONAL = frozenset({"source", "origin", "derivation", "anchors"})
ORIGIN_TYPES = frozenset({"seed", "discovered", "derived"})
DERIVATION_DISPOSITIONS = frozenset({"carried", "quarantined"})
# Anchor kinds — SSOT for the machine-relevant evidence tokens a fact carries
# (born-with identity; P4 init-fidelity). ``code_ref`` keeps whole
# ``path::symbol`` values; L6 splits on ``::`` at match time (OR coverage).
ANCHOR_KINDS = frozenset({"path", "artifact", "symbol", "api", "code_ref"})


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


def _validate_origin(prefix: str, origin: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(origin, dict):
        errors.append(f"{prefix}.origin must be an object {{type, ref}}")
        return errors
    otype = origin.get("type")
    if not isinstance(otype, str) or otype.strip().lower() not in ORIGIN_TYPES:
        errors.append(
            f"{prefix}.origin.type must be one of {sorted(ORIGIN_TYPES)}, "
            f"got {otype!r}"
        )
    ref = origin.get("ref")
    if not isinstance(ref, list):
        errors.append(f"{prefix}.origin.ref must be an array")
    elif not ref:
        errors.append(f"{prefix}.origin.ref must be a non-empty array when present")
    else:
        for r_index, item in enumerate(ref):
            if not isinstance(item, str) or not item.strip():
                errors.append(
                    f"{prefix}.origin.ref[{r_index}] must be a non-empty string",
                )
    extra = set(origin) - {"type", "ref"}
    if extra:
        errors.append(f"{prefix}.origin unexpected fields {sorted(extra)}")
    return errors


def _validate_derivation(prefix: str, derivation: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(derivation, dict):
        errors.append(
            f"{prefix}.derivation must be an object {{disposition, upstream_ref}}",
        )
        return errors
    disposition = derivation.get("disposition")
    if (
        not isinstance(disposition, str)
        or disposition.strip().lower() not in DERIVATION_DISPOSITIONS
    ):
        errors.append(
            f"{prefix}.derivation.disposition must be one of "
            f"{sorted(DERIVATION_DISPOSITIONS)}, got {disposition!r}"
        )
    upstream_ref = derivation.get("upstream_ref")
    if not isinstance(upstream_ref, list):
        errors.append(f"{prefix}.derivation.upstream_ref must be an array")
    elif not upstream_ref:
        errors.append(
            f"{prefix}.derivation.upstream_ref must be a non-empty array when present",
        )
    else:
        for r_index, item in enumerate(upstream_ref):
            if not isinstance(item, str) or not item.strip():
                errors.append(
                    f"{prefix}.derivation.upstream_ref[{r_index}] "
                    "must be a non-empty string",
                )
    extra = set(derivation) - {"disposition", "upstream_ref"}
    if extra:
        errors.append(f"{prefix}.derivation unexpected fields {sorted(extra)}")
    return errors


def _validate_anchors(prefix: str, anchors: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(anchors, list):
        errors.append(f"{prefix}.anchors must be an array when present")
        return errors
    for a_index, item in enumerate(anchors):
        aprefix = f"{prefix}.anchors[{a_index}]"
        if not isinstance(item, dict):
            errors.append(f"{aprefix} must be an object {{kind, value}}")
            continue
        kind = item.get("kind")
        if not isinstance(kind, str) or kind.strip().lower() not in ANCHOR_KINDS:
            errors.append(
                f"{aprefix}.kind must be one of {sorted(ANCHOR_KINDS)}, got {kind!r}",
            )
        value = item.get("value")
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{aprefix}.value must be a non-empty string")
        extra = set(item) - {"kind", "value"}
        if extra:
            errors.append(f"{aprefix} unexpected fields {sorted(extra)}")
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

        if "origin" in entry:
            if entry["origin"] is None:
                errors.append(
                    f"{prefix}.origin must be an object when present "
                    "(null is not allowed; omit the field instead)",
                )
            else:
                errors.extend(_validate_origin(prefix, entry["origin"]))

        if "derivation" in entry:
            if entry["derivation"] is None:
                errors.append(
                    f"{prefix}.derivation must be an object when present "
                    "(null is not allowed; omit the field instead)",
                )
            else:
                errors.extend(_validate_derivation(prefix, entry["derivation"]))
                derivation = entry["derivation"]
                if isinstance(derivation, dict) and isinstance(tags, list):
                    disposition = str(derivation.get("disposition", "")).strip().lower()
                    if disposition == "carried" and len(tags) == 0:
                        errors.append(
                            f"{prefix}: derivation.disposition=carried requires "
                            "non-empty lens_tags",
                        )
                    if disposition == "quarantined" and len(tags) > 0:
                        errors.append(
                            f"{prefix}: derivation.disposition=quarantined requires "
                            "empty lens_tags",
                        )

        if "anchors" in entry:
            if entry["anchors"] is None:
                errors.append(
                    f"{prefix}.anchors must be an array when present "
                    "(null is not allowed; omit the field instead)",
                )
            else:
                errors.extend(_validate_anchors(prefix, entry["anchors"]))

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
    if "origin" in entry and entry["origin"] is not None:
        origin = entry["origin"]
        out["origin"] = {
            "type": str(origin["type"]).strip().lower(),
            "ref": [str(r).strip() for r in origin["ref"]],
        }
    if "derivation" in entry and entry["derivation"] is not None:
        derivation = entry["derivation"]
        out["derivation"] = {
            "disposition": str(derivation["disposition"]).strip().lower(),
            "upstream_ref": [str(r).strip() for r in derivation["upstream_ref"]],
        }
    if "anchors" in entry and entry["anchors"] is not None:
        seen_anchors: set[tuple[str, str]] = set()
        normalized_anchors: list[dict[str, str]] = []
        for anchor in entry["anchors"]:
            key = (str(anchor["kind"]).strip().lower(), str(anchor["value"]).strip())
            if key in seen_anchors:
                continue
            seen_anchors.add(key)
            normalized_anchors.append({"kind": key[0], "value": key[1]})
        # Empty anchors normalize to omission (equivalent to absent; §3.1).
        if normalized_anchors:
            out["anchors"] = normalized_anchors
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
    """Validate and write facts array (preserves optional ``source`` / ``origin``).

    Validate raw input first so malformed optional fields raise ValueError
    instead of KeyError/TypeError inside normalize.
    """
    errors = validate_facts(facts, allowed_lenses=allowed_lenses)
    if errors:
        raise ValueError("; ".join(errors))
    normalized = [normalize_fact(f) for f in facts]
    # Re-validate after normalize (uppercase tags, stripped strings).
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
