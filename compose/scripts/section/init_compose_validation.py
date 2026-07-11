#!/usr/bin/env python3
"""Validate Initializing derive artifacts and compose document seed.

Subcommands:
    validate    Check revision-dir derive/body/title/block-title artifacts and compose doc

CLI details: ``python3 init_compose_validation.py --help``
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

_SECTION = Path(__file__).resolve().parent
_SCRIPTS = _SECTION.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from compose_doc_schema import section_body_by_key, section_display_heading  # noqa: E402
from fetch_compose_framework import fetch_compose_framework  # noqa: E402
from outline_registry_schema import normalize_outline_registry  # noqa: E402
from init_artifact_paths import (  # noqa: E402
    block_titles_path,
    body_path,
    derive_path,
    display_titles_path,
)
from partition_schema import partition_path, validate_partition_atoms  # noqa: E402
from workflow_paths import load_profile  # noqa: E402

from init_block_titles_schema import get_block_title, load_block_titles, validate_block_titles  # noqa: E402
from init_display_titles_schema import (  # noqa: E402
    get_display_title,
    load_display_titles,
    save_display_titles,
    validate_display_titles,
)

_MIN_BODY_LINES_WITH_I_STAR = 3
_PROHIBITED_BODY_PATTERNS = ("[Source:", "decision-doc-mapping")
_GAP_KINDS = frozenset({"scope_absent", "unfounded"})
_GAP_DIMENSIONS = frozenset({"what", "why", "alternatives", "failure"})
_C_MIN = 2
_C_MAX = 5
_SECTION_KEY_ANCHOR_RE = re.compile(
    r"<!--\s*section-key:\s*([A-Za-z0-9_]+)\s*-->",
    re.IGNORECASE,
)


def section_order_for_profile(project_root: Path, profile_id: str) -> list[str]:
    raw = fetch_compose_framework(
        "section-registry",
        project_root,
        profile_id=profile_id,
    )
    data = json.loads(raw)
    return [str(key).upper() for key in data.get("section_order") or []]


def outline_registry_for_profile(
    project_root: Path,
    profile_id: str,
) -> dict[str, Any] | None:
    try:
        raw = fetch_compose_framework(
            "outline-registry",
            project_root,
            profile_id=profile_id,
        )
    except Exception:
        return None
    return normalize_outline_registry(json.loads(raw))


def flatten_outline_intents(outline: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for block_key in outline.get("outline_order") or []:
        bk = str(block_key).upper()
        block = (outline.get("blocks") or {}).get(bk) or {}
        keys.extend(str(item).upper() for item in block.get("intents") or [])
    return keys


def block_h2_above_intent(raw_doc: str, first_intent_key: str) -> str:
    """Return the nearest H2 heading above the first anchor for an intent key."""
    key = first_intent_key.strip().upper()
    anchor_pos: int | None = None
    for match in _SECTION_KEY_ANCHOR_RE.finditer(raw_doc):
        if match.group(1).upper() == key:
            anchor_pos = match.start()
            break
    if anchor_pos is None:
        return ""

    h2_title = ""
    for line in raw_doc[:anchor_pos].splitlines():
        if line.startswith("## ") and not line.startswith("### "):
            h2_title = line[3:].strip()
    return h2_title


def minimal_derive_payload(
    section_key: str,
    *,
    i_star: str = "Sample substance for this section.",
) -> dict[str, Any]:
    """Return a minimal valid derive document (for tests and fixtures)."""
    key = section_key.strip().upper()
    gaps: list[dict[str, str]] = []
    if not i_star.strip():
        gaps = [
            {
                "kind": "scope_absent",
                "dimension": "what",
                "note": "No matching scope substance for this section.",
            },
        ]
    return {
        "section_key": key,
        "i_star": i_star,
        "scope_refs": ["Decision: sample reference"],
        "code_refs": [],
        "gaps": gaps,
        "f": {
            "carrier": "prose",
            "structure": "2 short paragraphs",
            "forbidden": "task breakdown",
        },
        "c": [
            {
                "d": "granularity",
                "c": "decision-level only",
                "source": "role_fields.completion_bar",
            },
            {
                "d": "vocabulary",
                "c": "tech-neutral operational prose",
                "source": "role_fields.vocabulary_domain",
            },
        ],
    }


def write_minimal_derive_artifacts(
    revision_dir: Path,
    section_keys: Iterable[str],
    *,
    i_star: str = "Sample substance for this section.",
) -> None:
    revision_dir.mkdir(parents=True, exist_ok=True)
    for key in section_keys:
        payload = minimal_derive_payload(key, i_star=i_star)
        path = derive_path(revision_dir, payload['section_key'])
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_minimal_partition(
    revision_dir: Path,
    section_keys: Iterable[str],
) -> Path:
    """Write a minimal valid ``_partition.json`` (one atom per key) for tests."""
    revision_dir.mkdir(parents=True, exist_ok=True)
    atoms: list[dict[str, str]] = []
    for index, key in enumerate(section_keys, start=1):
        atoms.append(
            {
                "id": f"A-{index}",
                "text": f"Minimal atom for {str(key).strip().upper()}.",
                "home": str(key).strip().upper(),
            }
        )
    path = partition_path(revision_dir)
    path.write_text(json.dumps(atoms, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_minimal_init_work_artifacts(
    revision_dir: Path,
    section_keys: Iterable[str],
    *,
    i_star: str = "Sample substance for this section.",
) -> None:
    """Write derive, body, and title files for Init validation tests and fixtures."""
    write_minimal_derive_artifacts(revision_dir, section_keys, i_star=i_star)

    for key in section_keys:
        section = key.strip().upper()
        body = (
            f"Operational summary for {section}.\n\n"
            f"Scope-aligned substance line two.\n\n"
            f"Scope-aligned substance line three.\n"
        )
        body_path(revision_dir, section).write_text(body, encoding="utf-8")

    display_map: dict[str, str] = {}
    for key in section_keys:
        section = key.strip().upper()
        display_map[section] = f"Topic {section}"
    save_display_titles(display_titles_path(revision_dir), display_map)


def _load_derive(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("derive root must be an object")
    return data


def _validate_gap(entry: Any, *, section_key: str, index: int) -> list[str]:
    errors: list[str] = []
    prefix = f"{section_key} gaps[{index}]"
    if not isinstance(entry, dict):
        return [f"{prefix} must be an object"]
    kind = entry.get("kind")
    if kind not in _GAP_KINDS:
        errors.append(
            f"{prefix}.kind must be one of {sorted(_GAP_KINDS)} (got {kind!r})",
        )
    note = entry.get("note")
    if not isinstance(note, str) or not note.strip():
        errors.append(f"{prefix}.note must be a non-empty string")
    dimension = entry.get("dimension")
    if dimension is not None and dimension not in _GAP_DIMENSIONS:
        errors.append(f"{prefix}.dimension invalid: {dimension!r}")
    return errors


def _validate_derive_document(data: dict[str, Any], *, expected_key: str) -> list[str]:
    errors: list[str] = []
    key = expected_key.upper()
    section_key = data.get("section_key")
    if section_key != key:
        errors.append(f"{key}: section_key mismatch ({section_key!r})")

    for field in ("i_star",):
        if field not in data:
            errors.append(f"{key}: missing {field}")
        elif not isinstance(data[field], str):
            errors.append(f"{key}: {field} must be a string")

    scope_refs = data.get("scope_refs")
    if not isinstance(scope_refs, list):
        errors.append(f"{key}: scope_refs must be an array")
    elif not scope_refs:
        errors.append(f"{key}: scope_refs must not be empty")
    else:
        for index, ref in enumerate(scope_refs):
            if not isinstance(ref, str) or not ref.strip():
                errors.append(f"{key}: scope_refs[{index}] must be a non-empty string")

    code_refs = data.get("code_refs")
    if code_refs is None:
        errors.append(f"{key}: missing code_refs (use [] when none)")
    elif not isinstance(code_refs, list):
        errors.append(f"{key}: code_refs must be an array")
    else:
        for index, ref in enumerate(code_refs):
            if not isinstance(ref, str) or not ref.strip():
                errors.append(f"{key}: code_refs[{index}] must be a non-empty string")

    gaps = data.get("gaps")
    if not isinstance(gaps, list):
        errors.append(f"{key}: gaps must be an array")
    else:
        for index, entry in enumerate(gaps):
            errors.extend(_validate_gap(entry, section_key=key, index=index))

    f_obj = data.get("f")
    if not isinstance(f_obj, dict):
        errors.append(f"{key}: f must be an object")
    else:
        carrier = f_obj.get("carrier")
        if not isinstance(carrier, str) or not carrier.strip():
            errors.append(f"{key}: f.carrier must be a non-empty string")
        for sub in ("structure", "forbidden"):
            if sub not in f_obj or not isinstance(f_obj[sub], str):
                errors.append(f"{key}: f.{sub} must be a string")

    c_list = data.get("c")
    if not isinstance(c_list, list):
        errors.append(f"{key}: c must be an array")
    elif not (_C_MIN <= len(c_list) <= _C_MAX):
        errors.append(f"{key}: c must have {_C_MIN}–{_C_MAX} entries")
    else:
        for index, entry in enumerate(c_list):
            if not isinstance(entry, dict):
                errors.append(f"{key}: c[{index}] must be an object")
                continue
            for sub in ("d", "c", "source"):
                val = entry.get(sub)
                if not isinstance(val, str) or not val.strip():
                    errors.append(f"{key}: c[{index}].{sub} must be a non-empty string")

    if "kw_init" in data:
        errors.append(f"{key}: kw_init is removed; omit the field")

    i_star = str(data.get("i_star", "")).strip()
    if not i_star and isinstance(gaps, list) and not gaps:
        errors.append(f"{key}: empty i_star requires at least one gaps entry")

    return errors


def _validate_body_file(
    body_file: Path,
    *,
    section_key: str,
    i_star: str,
) -> list[str]:
    errors: list[str] = []
    if not body_file.is_file():
        return [f"{section_key}: missing body file {body_file.name}"]

    body = body_file.read_text(encoding="utf-8")
    if not body.strip():
        return [f"{section_key}: empty body file"]

    for pattern in _PROHIBITED_BODY_PATTERNS:
        if pattern in body:
            errors.append(f"{section_key}: prohibited pattern in body: {pattern!r}")

    if i_star.strip():
        non_blank_lines = [line for line in body.splitlines() if line.strip()]
        if len(non_blank_lines) < _MIN_BODY_LINES_WITH_I_STAR:
            errors.append(
                f"{section_key}: thin body ({len(non_blank_lines)} non-blank lines; "
                f"need {_MIN_BODY_LINES_WITH_I_STAR} when i_star non-empty)",
            )
    return errors


def _validate_section_display_titles(
    revision_dir: Path,
    section_keys: Iterable[str],
) -> list[str]:
    errors: list[str] = []
    path = display_titles_path(revision_dir)
    if not path.is_file():
        return [f"missing display titles file {path.name}"]
    try:
        data = load_display_titles(path)
    except (json.JSONDecodeError, ValueError) as exc:
        return [f"invalid {path.name}: {exc}"]
    errors.extend(validate_display_titles(data))
    for key in section_keys:
        section = str(key).strip().upper()
        if not get_display_title(data, section):
            errors.append(f"{section}: missing display title in {path.name}")
    return errors


def _validate_block_titles(
    revision_dir: Path,
    raw_doc: str,
    outline: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    path = block_titles_path(revision_dir)
    block_map: dict[str, str] = {}
    if path.is_file():
        try:
            block_map = load_block_titles(path)
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(f"invalid {path.name}: {exc}")
            return errors
        errors.extend(validate_block_titles(block_map))

    blocks = outline.get("blocks") or {}
    for block_key in outline.get("outline_order") or []:
        bk = str(block_key).upper()
        block = blocks.get(bk) or {}
        heading = str(block.get("heading", "")).strip()
        intents = [str(item).upper() for item in block.get("intents") or []]
        if not intents:
            continue

        expected_title = get_block_title(block_map, bk)
        if not expected_title:
            errors.append(f"{bk}: missing block title in {path.name}")
            continue

        doc_h2 = block_h2_above_intent(raw_doc, intents[0])
        if not doc_h2:
            errors.append(f"{bk}: compose document missing block H2 above {intents[0]}")
            continue
        if doc_h2 != expected_title:
            errors.append(
                f"{bk}: block H2 {doc_h2!r} != _title-block.json entry {expected_title!r}",
            )
        if expected_title != "（待补）" and doc_h2 == heading:
            errors.append(
                f"{bk}: block H2 still English placeholder {heading!r}",
            )
    return errors


def validate_init_artifacts(
    revision_dir: Path,
    compose_doc: Path,
    project_root: Path,
    profile_id: str,
) -> str | None:
    """Return first error summary or None when all checks pass."""
    if not revision_dir.is_dir():
        return f"revision dir not found: {revision_dir}"

    if not compose_doc.is_file():
        return f"compose document not found: {compose_doc}"

    keys = section_order_for_profile(project_root, profile_id)
    errors: list[str] = []

    profile = load_profile(profile_id, project_root=project_root)
    inductive = (profile.get("drafting") or {}).get("inductive") is True
    if not inductive:
        part = partition_path(revision_dir)
        if not part.is_file():
            errors.append(
                "missing _partition.json (required when drafting.inductive is false)",
            )
        else:
            try:
                data = json.loads(part.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors.append(f"invalid _partition.json: {exc}")
            else:
                errors.extend(
                    validate_partition_atoms(data, allowed_homes=keys),
                )

    raw_doc = compose_doc.read_text(encoding="utf-8")

    for key in keys:
        derive_file = derive_path(revision_dir, key)
        if not derive_file.is_file():
            errors.append(f"missing derive: {key}")
            continue
        try:
            derive = _load_derive(derive_file)
        except ValueError as exc:
            errors.append(f"invalid derive {key}: {exc}")
            continue

        errors.extend(_validate_derive_document(derive, expected_key=key))

        i_star = str(derive.get("i_star", ""))
        section_body_path = body_path(revision_dir, key)
        errors.extend(_validate_body_file(section_body_path, section_key=key, i_star=i_star))

        body = section_body_by_key(raw_doc, key, project_root=project_root).strip()
        if not body:
            errors.append(f"compose document empty body: {key}")
        elif not section_display_heading(raw_doc, key, project_root=project_root).strip():
            errors.append(f"compose document missing display title: {key}")

    errors.extend(_validate_section_display_titles(revision_dir, keys))

    outline = outline_registry_for_profile(project_root, profile_id)
    if outline is not None:
        flat = flatten_outline_intents(outline)
        if flat and flat != keys:
            errors.append(
                f"section_order != flatten(outline.intents): {keys!r} vs {flat!r}",
            )
        errors.extend(_validate_block_titles(revision_dir, raw_doc, outline))

    if not errors:
        return None
    return "; ".join(errors)


def cmd_validate(args: argparse.Namespace) -> int:
    error = validate_init_artifacts(
        args.revision_dir.resolve(),
        args.compose_doc.resolve(),
        args.project_root.resolve(),
        args.profile.strip(),
    )
    if error:
        print(f"错误：Init 校验失败：{error}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    validate_parser = sub.add_parser("validate", help="Validate Init derive artifacts")
    validate_parser.add_argument("--revision-dir", type=Path, required=True)
    validate_parser.add_argument("--compose-doc", type=Path, required=True)
    validate_parser.add_argument("--profile", type=str, required=True)
    validate_parser.add_argument("--project-root", type=Path, default=Path.cwd())
    validate_parser.set_defaults(func=cmd_validate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
