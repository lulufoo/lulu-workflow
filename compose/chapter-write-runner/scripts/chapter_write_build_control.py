#!/usr/bin/env python3
"""Prepare session context for chapter-write-runner.

``context`` returns filtered Role/Domain instances and a mechanically
substituted ``document_preamble`` (cycle id, date, cycle display name). It
never returns facts or full registries.

This control does not claim chapters or persist documents.

Process how: docs/domain/archive/compose/archive-26.0/
chapter-write-runner-extract-design.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

_RUNNER_SCRIPTS = Path(__file__).resolve().parent
_COMPOSE = _RUNNER_SCRIPTS.parents[1]
_SCRIPTS = _COMPOSE / "scripts"
for _path in (_SCRIPTS, _RUNNER_SCRIPTS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from domain_instance_schema import (  # noqa: E402
    DOMAIN_SCHEME_KEY,
    load_and_validate_domain_instance,
)
from fetch_compose_framework import fetch_compose_framework  # noqa: E402
from role_instance_schema import (  # noqa: E402
    ROLE_SCHEME_KEY,
    load_and_validate_role_instance,
)
from schema_common import resolve_fetched_instance_path  # noqa: E402
from scope_resolver import resolve_cycle_type  # noqa: E402
from workflow_common import CACHE_DIR, load_container_meta  # noqa: E402
from workflow_paths import resolve_revision_runtime_profile  # noqa: E402

_ROLE_KEYS = ("role_id", "expressive_tendency")
_DOMAIN_KEYS = (
    "cognitive_frame",
    "expression_conventions",
    "vocabulary_domain",
)
_EXPRESSION_KEYS = ("register", "carriers", "scannability", "altitude")
_NAME_PLACEHOLDER_RE = re.compile(r"\{(?:Feature|Topic) Name\}")


def _cycle_display_name(*, project_root: Path, cycle_id: str) -> str:
    """Return cycles.json ``name`` for cycle_id, else cycle_id, else \"\"."""
    cid = str(cycle_id or "").strip()
    if not cid:
        return ""
    try:
        meta = load_container_meta(project_root.resolve() / CACHE_DIR, cid)
    except (OSError, ValueError, json.JSONDecodeError):
        return cid
    if isinstance(meta, dict):
        name = str(meta.get("name") or "").strip()
        if name:
            return name
    return cid


def _ok(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _fail(message: str) -> int:
    print(f"错误：{message}", file=sys.stderr)
    return 1


def _cycle_type(args: argparse.Namespace) -> str:
    return resolve_cycle_type(
        cycle_id=str(args.cycle_id or "").strip() or None,
        cycle_type=str(args.cycle_type or "").strip() or None,
    )


def _scope_instances(
    *,
    cycle_type: str,
    project_root: Path,
    profile: str,
    cycle_id: str,
    profile_path: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    role_path = resolve_fetched_instance_path(
        ROLE_SCHEME_KEY,
        project_root,
        profile_id=profile,
        cycle_id=cycle_id or None,
        profile_path=profile_path,
    )
    domain_path = resolve_fetched_instance_path(
        DOMAIN_SCHEME_KEY,
        project_root,
        profile_id=profile,
        cycle_id=cycle_id or None,
        profile_path=profile_path,
    )
    return (
        load_and_validate_role_instance(
            cycle_type,
            path=role_path,
            project_root=project_root,
            profile_id=profile,
        ),
        load_and_validate_domain_instance(
            cycle_type,
            path=domain_path,
            project_root=project_root,
            profile_id=profile,
        ),
    )


def _filter_role(role: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in _ROLE_KEYS:
        if key not in role:
            raise ValueError(f"role missing required field: {key}")
        out[key] = role[key]
    return out


def _expression_conventions_object(value: Any) -> dict[str, str]:
    """Return four-key object; accept dict or normalized multiline string."""
    if isinstance(value, dict):
        missing = [k for k in _EXPRESSION_KEYS if k not in value]
        if missing:
            raise ValueError(
                "domain.expression_conventions missing keys: " + ", ".join(missing)
            )
        out = {k: str(value[k]).strip() for k in _EXPRESSION_KEYS}
        if any(not v for v in out.values()):
            raise ValueError("domain.expression_conventions values must be non-empty")
        return out
    if isinstance(value, str) and value.strip():
        parsed: dict[str, str] = {}
        for line in value.splitlines():
            if ":" not in line:
                continue
            key, _, rest = line.partition(":")
            key = key.strip()
            if key in _EXPRESSION_KEYS:
                parsed[key] = rest.strip()
        missing = [k for k in _EXPRESSION_KEYS if not parsed.get(k)]
        if missing:
            raise ValueError(
                "domain.expression_conventions string missing keys: "
                + ", ".join(missing)
            )
        return {k: parsed[k] for k in _EXPRESSION_KEYS}
    raise ValueError("domain.expression_conventions must be an object or labeled string")


def _filter_domain(domain: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in _DOMAIN_KEYS:
        if key not in domain:
            raise ValueError(f"domain missing required field: {key}")
        out[key] = domain[key]
    out["expression_conventions"] = _expression_conventions_object(
        out["expression_conventions"]
    )
    return out


def _registry_preamble(
    *,
    project_root: Path,
    profile: str,
    cycle_id: str,
    profile_path: Path | None = None,
) -> str:
    raw = fetch_compose_framework(
        "section-registry",
        project_root,
        profile_id=profile,
        cycle_id=cycle_id or None,
        profile_path=profile_path,
    )
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("section-registry must be a JSON object")
    preamble = data.get("document_preamble")
    if not isinstance(preamble, str) or not preamble.strip():
        raise ValueError("section-registry.document_preamble must be a non-empty string")
    return preamble


def substitute_document_preamble(
    raw: str,
    *,
    cycle_id: str,
    display_name: str = "",
) -> str:
    """Apply mechanical preamble substitutions (cycle id, date, display name).

    ``{Feature Name}`` / ``{Topic Name}`` use ``display_name``, else ``cycle_id``.
    Residuals remain only when neither is available (e.g. ``--cycle-type`` only).
    """
    cid = str(cycle_id or "").strip()
    name = str(display_name or "").strip() or cid
    text = raw
    if cid:
        text = text.replace("<cycle_id>", cid)
    text = text.replace("YYYY-MM-DD", date.today().isoformat())
    if name:
        text = text.replace("{Feature Name}", name)
        text = text.replace("{Topic Name}", name)
    return text


def cmd_context(args: argparse.Namespace) -> int:
    try:
        root = Path(args.project_root).resolve()
        cycle_type = _cycle_type(args)
        cycle_id = str(args.cycle_id or "").strip()
        runtime = resolve_revision_runtime_profile(
            Path(args.revision_dir),
            root,
            cycle_id=cycle_id or None,
        )
        role, domain = _scope_instances(
            cycle_type=cycle_type,
            project_root=root,
            profile=runtime.profile_id,
            cycle_id=cycle_id,
            profile_path=runtime.profile_path,
        )
        display_name = _cycle_display_name(project_root=root, cycle_id=cycle_id)
        preamble = substitute_document_preamble(
            _registry_preamble(
                project_root=root,
                profile=runtime.profile_id,
                cycle_id=cycle_id,
                profile_path=runtime.profile_path,
            ),
            cycle_id=cycle_id,
            display_name=display_name,
        )
        payload: dict[str, Any] = {
            "ok": True,
            "command": "context",
            "phase": "session",
            "role": _filter_role(role),
            "domain": _filter_domain(domain),
            "document_preamble": preamble,
        }
        if _NAME_PLACEHOLDER_RE.search(preamble):
            payload["preamble_name_placeholders"] = True
    except (OSError, ValueError, json.JSONDecodeError, TypeError) as exc:
        return _fail(str(exc))
    return _ok(payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    context = sub.add_parser("context", help="Print filtered session write context")
    context.add_argument("--revision-dir", required=True)
    context.add_argument("--project-root", required=True)
    cycle = context.add_mutually_exclusive_group(required=True)
    cycle.add_argument("--cycle-id", default="")
    cycle.add_argument("--cycle-type", default="")
    context.set_defaults(func=cmd_context)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
