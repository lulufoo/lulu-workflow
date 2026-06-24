#!/usr/bin/env python3
"""Validate Initializing derive artifacts and compose document seed.

Subcommands:
    validate    Check revision-dir derive/body/title artifacts and compose doc

CLI details: ``python3 init_compose_validation.py --help``
"""

from __future__ import annotations

import argparse
import json
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

_MIN_BODY_LINES_WITH_I_STAR = 3
_PROHIBITED_BODY_PATTERNS = ("[Source:", "decision-doc-mapping")
_KW_INIT_KEYS = ("what", "why", "alternatives", "failure")
_C_MIN = 2
_C_MAX = 5


def section_order_for_profile(project_root: Path, profile_id: str) -> list[str]:
    raw = fetch_compose_framework(
        "section-registry",
        project_root,
        profile_id=profile_id,
    )
    data = json.loads(raw)
    return [str(key).upper() for key in data.get("section_order") or []]


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
        "kw_init": {
            "what": bool(i_star.strip()),
            "why": False,
            "alternatives": False,
            "failure": False,
        },
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
        path = revision_dir / f"_derive-{payload['section_key']}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
        (revision_dir / f"_body-{section}.txt").write_text(body, encoding="utf-8")
        (revision_dir / f"_title-{section}.txt").write_text(
            f"Topic {section}\n",
            encoding="utf-8",
        )


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
    if kind != "scope_absent":
        errors.append(f"{prefix}.kind must be 'scope_absent'")
    note = entry.get("note")
    if not isinstance(note, str) or not note.strip():
        errors.append(f"{prefix}.note must be a non-empty string")
    dimension = entry.get("dimension")
    if dimension is not None and dimension not in _KW_INIT_KEYS:
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

    kw_init = data.get("kw_init")
    if not isinstance(kw_init, dict):
        errors.append(f"{key}: kw_init must be an object")
    else:
        for sub in _KW_INIT_KEYS:
            if not isinstance(kw_init.get(sub), bool):
                errors.append(f"{key}: kw_init.{sub} must be a boolean")

    i_star = str(data.get("i_star", "")).strip()
    if not i_star and isinstance(gaps, list) and not gaps:
        errors.append(f"{key}: empty i_star requires at least one gaps entry")

    return errors


def _validate_body_file(
    body_path: Path,
    *,
    section_key: str,
    i_star: str,
) -> list[str]:
    errors: list[str] = []
    if not body_path.is_file():
        return [f"{section_key}: missing body file {body_path.name}"]

    body = body_path.read_text(encoding="utf-8")
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


def _validate_title_file(title_path: Path, *, section_key: str) -> list[str]:
    if not title_path.is_file():
        return [f"{section_key}: missing title file {title_path.name}"]
    if not title_path.read_text(encoding="utf-8").splitlines():
        return [f"{section_key}: empty title file"]
    return []


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

    raw_doc = compose_doc.read_text(encoding="utf-8")
    for key in keys:
        derive_path = revision_dir / f"_derive-{key}.json"
        if not derive_path.is_file():
            errors.append(f"missing derive: {key}")
            continue
        try:
            derive = _load_derive(derive_path)
        except ValueError as exc:
            errors.append(f"invalid derive {key}: {exc}")
            continue

        errors.extend(_validate_derive_document(derive, expected_key=key))

        i_star = str(derive.get("i_star", ""))
        body_path = revision_dir / f"_body-{key}.txt"
        title_path = revision_dir / f"_title-{key}.txt"
        errors.extend(_validate_body_file(body_path, section_key=key, i_star=i_star))
        errors.extend(_validate_title_file(title_path, section_key=key))

        body = section_body_by_key(raw_doc, key, project_root=project_root).strip()
        if not body:
            errors.append(f"compose document empty body: {key}")
        elif not section_display_heading(raw_doc, key, project_root=project_root).strip():
            errors.append(f"compose document missing display title: {key}")

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
