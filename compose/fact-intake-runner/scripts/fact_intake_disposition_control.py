#!/usr/bin/env python3
"""Fact-intake disposition Confirm patch validate/apply."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_DEDUCTIVE = _SCRIPTS / "deductive"
for _path in (_SCRIPTS, _SCRIPTS / "_kernel", _SCRIPTS / "templates", _DEDUCTIVE):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from deductive_disposition_patch import (  # noqa: E402
    apply_disposition_patch,
    disposition_counts,
    validate_disposition_patch,
)
from l_ledger_schema import active_slice_dir  # noqa: E402
from facts_schema import facts_path, load_facts, save_facts  # noqa: E402
from compose_template_loader import (  # noqa: E402
    ComposeTemplateLoadError,
    load_compose_template,
)
from section_registry_schema import fetch_section_registry, lens_key_sequence  # noqa: E402
from workflow_paths import resolve_revision_runtime_profile  # noqa: E402

DISPOSITION_PATCH_BASENAME = "fact-intake-disposition-review.patch"


def disposition_patch_path(revision_dir: Path) -> Path:
    """Canonical Confirm patch: same directory as ``_facts.json`` (active slice)."""
    return active_slice_dir(revision_dir.resolve()) / DISPOSITION_PATCH_BASENAME


def _resolve_patch_file(args: argparse.Namespace) -> Path:
    if args.patch_file is not None:
        return args.patch_file.resolve()
    return disposition_patch_path(args.revision_dir)


def _ok(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _fail(message: str) -> int:
    print(f"错误：{message}", file=sys.stderr)
    return 1


def _runtime_profile(args: argparse.Namespace):
    return resolve_revision_runtime_profile(
        Path(args.revision_dir),
        Path(args.project_root).resolve(),
    )


def _section_order(
    project_root: Path,
    profile: str,
    *,
    profile_path: Path | None = None,
) -> list[str]:
    return lens_key_sequence(
        fetch_section_registry(
            project_root,
            profile_id=profile,
            profile_path=profile_path,
        )
    )


def _consume_rule_ids(
    project_root: Path,
    profile: str,
    *,
    profile_path: Path | None = None,
) -> list[str]:
    raw = load_compose_template(
        "role-instance",
        project_root,
        profile_id=profile,
        profile_path=profile_path,
    )
    role = json.loads(raw)
    if not isinstance(role, dict):
        raise ValueError("role-instance must be a JSON object")
    policy = role.get("consume_policy")
    if not isinstance(policy, dict):
        return []
    rules = policy.get("rules") or []
    if not isinstance(rules, list) or not rules:
        return []
    return [
        str(r.get("id", "")).strip()
        for r in rules
        if isinstance(r, dict) and str(r.get("id", "")).strip()
    ]


def _load_patch_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read patch: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("patch root must be an object")
    return data


def cmd_disposition_patch_path(args: argparse.Namespace) -> int:
    path = disposition_patch_path(args.revision_dir)
    return _ok(
        {
            "ok": True,
            "command": "disposition-patch-path",
            "path": path.as_posix(),
            "facts_path": facts_path(active_slice_dir(args.revision_dir.resolve())).as_posix(),
        }
    )


def cmd_disposition_patch_validate(args: argparse.Namespace) -> int:
    revision_dir = active_slice_dir(args.revision_dir.resolve())
    try:
        runtime = _runtime_profile(args)
        facts = load_facts(facts_path(revision_dir))
        patch = _load_patch_file(_resolve_patch_file(args))
        allowed_lenses = _section_order(
            args.project_root.resolve(),
            runtime.profile_id,
            profile_path=runtime.profile_path,
        )
        allowed_rule_ids = _consume_rule_ids(
            args.project_root.resolve(),
            runtime.profile_id,
            profile_path=runtime.profile_path,
        )
    except (ValueError, ComposeTemplateLoadError, json.JSONDecodeError, FileNotFoundError, OSError) as exc:
        return _fail(str(exc))
    errors = validate_disposition_patch(
        patch,
        facts,
        allowed_lenses=allowed_lenses,
        allowed_rule_ids=allowed_rule_ids,
    )
    if errors:
        return _fail("; ".join(errors))
    return _ok(
        {
            "ok": True,
            "command": "disposition-patch-validate",
            "ops_total": len(patch.get("ops") or []),
            "counts": disposition_counts(facts),
        }
    )


def cmd_disposition_patch_apply(args: argparse.Namespace) -> int:
    revision_dir = active_slice_dir(args.revision_dir.resolve())
    path = facts_path(revision_dir)
    try:
        runtime = _runtime_profile(args)
        facts = load_facts(path)
        patch = _load_patch_file(_resolve_patch_file(args))
        allowed_lenses = _section_order(
            args.project_root.resolve(),
            runtime.profile_id,
            profile_path=runtime.profile_path,
        )
        allowed_rule_ids = _consume_rule_ids(
            args.project_root.resolve(),
            runtime.profile_id,
            profile_path=runtime.profile_path,
        )
    except (ValueError, ComposeTemplateLoadError, json.JSONDecodeError, FileNotFoundError, OSError) as exc:
        return _fail(str(exc))
    errors = validate_disposition_patch(
        patch,
        facts,
        allowed_lenses=allowed_lenses,
        allowed_rule_ids=allowed_rule_ids,
    )
    if errors:
        return _fail("; ".join(errors))
    try:
        updated = apply_disposition_patch(facts, patch, mutate=False)
        save_facts(
            path,
            updated,
            allowed_lenses=allowed_lenses,
            allowed_rule_ids=allowed_rule_ids,
        )
    except ValueError as exc:
        return _fail(str(exc))
    loaded = load_facts(path)
    return _ok(
        {
            "ok": True,
            "command": "disposition-patch-apply",
            "path": path.as_posix(),
            "ops_total": len(patch.get("ops") or []),
            "counts": disposition_counts(loaded),
        }
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    path_p = sub.add_parser(
        "disposition-patch-path",
        help="Print canonical Confirm patch path (next to _facts.json)",
    )
    path_p.add_argument("--revision-dir", type=Path, required=True)
    path_p.set_defaults(func=cmd_disposition_patch_path)
    for name, func, help_text in (
        (
            "disposition-patch-validate",
            cmd_disposition_patch_validate,
            "Validate fact-intake disposition-review.patch",
        ),
        (
            "disposition-patch-apply",
            cmd_disposition_patch_apply,
            "Apply fact-intake disposition-review.patch",
        ),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--revision-dir", type=Path, required=True)
        p.add_argument(
            "--patch-file",
            type=Path,
            default=None,
            help=(
                f"Patch JSON (default: {{active slice}}/{DISPOSITION_PATCH_BASENAME})"
            ),
        )
        p.add_argument("--project-root", type=Path, default=Path.cwd())
        p.set_defaults(func=func)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
