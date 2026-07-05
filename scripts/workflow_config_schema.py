#!/usr/bin/env python3
"""Authoritative I/O for workflow-config and platform config pointer.

Library module — CLI lives in workflow_config.py.

Layout:
  skill-config/lulu-dev-workflow/
    manifest.json
    stages/{stage}.json

Legacy: workflowConfig may point at a monolith workflow-config.json file.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from platform_schema import PLATFORM_PATHS, detect_platform as _detect_platform

_WORKFLOW_DIR_MAP = {
    platform: paths["workflow_dir"] for platform, paths in PLATFORM_PATHS.items()
}

_DEFAULT_WORKFLOW_CONFIG_DIR = "skill-config/lulu-dev-workflow/"
_LEGACY_WORKFLOW_CONFIG_FILENAME = "workflow-config.json"
_STAGES_SUBDIR = "stages"
_MANIFEST_FILENAME = "manifest.json"
_DEFAULT_HOOK_CONFIG_PATH = "skill-config/lulu-dev-workflow/workflow-guard-config.json"
_DEFAULT_CONFIGURE_BLOB_URL = (
    "https://github.com/lulufoo/lulu-workflow-framework/blob/main/template/workflow-config.json"
)
RESERVED_TOP_LEVEL_KEYS = frozenset({"version", "layout"})
_STAGE_CONFIG_BUCKETS = frozenset({"compose", "eval"})
_STAGE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_WORKFLOW_ROOT = Path(__file__).resolve().parents[1]
_COMPOSE_PROFILE_FILENAME = "compose-profile.json"
_DROP_ORPHAN_CONFIG_KEYS = frozenset(
    {
        "tdt_design_doc_template_url",
        "tpt_spec_template_url",
    }
)


def detect_platform(platform: Optional[str] = None) -> str:
    return _detect_platform(override=platform, strict=False)


def default_platform_config() -> dict:
    return {
        "version": 1,
        "workflowConfig": _DEFAULT_WORKFLOW_CONFIG_DIR,
        "hookConfig": _DEFAULT_HOOK_CONFIG_PATH,
    }


def platform_config_path(project_root: Path, platform: Optional[str] = None) -> Path:
    plat = detect_platform(platform)
    workflow_dir = _WORKFLOW_DIR_MAP.get(plat, _WORKFLOW_DIR_MAP["cursor"])
    return project_root / workflow_dir / "config.json"


def read_platform_config(project_root: Path, platform: Optional[str] = None) -> dict:
    cfg_path = platform_config_path(project_root, platform)
    if not cfg_path.exists():
        return {}
    try:
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def write_platform_config(
    project_root: Path,
    cfg: dict,
    platform: Optional[str] = None,
) -> None:
    cfg_path = platform_config_path(project_root, platform)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def ensure_platform_config(project_root: Path, platform: Optional[str] = None) -> None:
    cfg_path = platform_config_path(project_root, platform)
    if not cfg_path.exists():
        write_platform_config(project_root, default_platform_config(), platform)


def _workflow_config_rel(project_root: Path, platform: Optional[str] = None) -> str:
    platform_cfg = read_platform_config(project_root, platform)
    rel = platform_cfg.get("workflowConfig", _DEFAULT_WORKFLOW_CONFIG_DIR)
    return str(rel).strip() or _DEFAULT_WORKFLOW_CONFIG_DIR


def is_legacy_monolith_path(path: Path) -> bool:
    """True when the configured pointer targets a single JSON file."""
    return path.suffix.lower() == ".json"


def resolve_workflow_config_path(
    project_root: Path,
    platform: Optional[str] = None,
) -> Path:
    """Return the configured workflowConfig pointer (directory or legacy monolith file)."""
    return project_root / _workflow_config_rel(project_root, platform)


def resolve_workflow_config_root(
    project_root: Path,
    platform: Optional[str] = None,
) -> Path:
    """Return the directory that holds manifest.json and stages/."""
    pointer = resolve_workflow_config_path(project_root, platform)
    if is_legacy_monolith_path(pointer):
        return pointer.parent
    return pointer


def _legacy_monolith_in_root(root: Path) -> Path:
    return root / _LEGACY_WORKFLOW_CONFIG_FILENAME


def _validate_stage_name(stage: str) -> None:
    if not stage or not _STAGE_NAME_RE.fullmatch(stage):
        raise ValueError(f"invalid workflow stage name: {stage!r}")


def _stage_file_in_root(root: Path, stage: str) -> Path:
    return root / _STAGES_SUBDIR / f"{stage}.json"


def _load_stage_from_stages_dir(root: Path, stage: str) -> dict:
    stage_path = _stage_file_in_root(root, stage)
    if not stage_path.exists():
        return {}
    return _read_json_object(stage_path, label=f"stage config [{stage}]")


def _config_root_from_pointer(pointer: Path) -> Path:
    if is_legacy_monolith_path(pointer):
        return pointer.parent
    return pointer


def _stages_layout_present(root: Path) -> bool:
    if (root / _MANIFEST_FILENAME).exists():
        return True
    stages_dir = root / _STAGES_SUBDIR
    return stages_dir.is_dir() and any(stages_dir.glob("*.json"))


def resolve_stage_config_path(
    project_root: Path,
    stage: str,
    platform: Optional[str] = None,
) -> Path:
    """Return stages/{stage}.json under the config root."""
    _validate_stage_name(stage)
    root = resolve_workflow_config_root(project_root, platform)
    return _stage_file_in_root(root, stage)


def _read_json_object(path: Path, *, label: str) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"{label} unreadable: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} root must be a JSON object: {path}")
    return payload


def _load_stage_from_legacy_monolith(monolith_path: Path, stage: str) -> dict:
    if not monolith_path.exists():
        return {}
    try:
        config = _read_json_object(monolith_path, label="workflow-config.json")
    except ValueError:
        return {}
    section = config.get(stage)
    return section if isinstance(section, dict) else {}


def load_stage_config(project_root: Path, stage: str, platform: Optional[str] = None) -> dict:
    """Load one stage config. Missing stage file → {}."""
    _validate_stage_name(stage)
    pointer = resolve_workflow_config_path(project_root, platform)
    root = _config_root_from_pointer(pointer)

    if is_legacy_monolith_path(pointer):
        stage_cfg = _load_stage_from_legacy_monolith(pointer, stage)
        if stage_cfg:
            return stage_cfg
        return _load_stage_from_stages_dir(root, stage)

    stage_cfg = _load_stage_from_stages_dir(root, stage)
    if stage_cfg:
        return stage_cfg

    return _load_stage_from_legacy_monolith(_legacy_monolith_in_root(root), stage)


def workflow_config_is_present(project_root: Path, platform: Optional[str] = None) -> bool:
    pointer = resolve_workflow_config_path(project_root, platform)
    root = _config_root_from_pointer(pointer)

    if is_legacy_monolith_path(pointer) and pointer.exists():
        return True
    if _stages_layout_present(root):
        return True
    return _legacy_monolith_in_root(root).exists()


def load_workflow_config(project_root: Path, platform: Optional[str] = None) -> dict:
    """Load merged workflow config (manifest + all stages). Raises ValueError if absent."""
    if not workflow_config_is_present(project_root, platform):
        pointer = resolve_workflow_config_path(project_root, platform)
        raise ValueError(f"workflow-config not found: {pointer}")

    pointer = resolve_workflow_config_path(project_root, platform)
    if is_legacy_monolith_path(pointer):
        return _read_json_object(pointer, label="workflow-config.json")

    root = pointer
    merged: dict = {}
    manifest_path = root / _MANIFEST_FILENAME
    if manifest_path.exists():
        merged.update(_read_json_object(manifest_path, label="workflow manifest"))

    stages_dir = root / _STAGES_SUBDIR
    if stages_dir.is_dir():
        for stage_path in sorted(stages_dir.glob("*.json")):
            merged[stage_path.stem] = _read_json_object(
                stage_path,
                label=f"stage config [{stage_path.stem}]",
            )

    legacy_path = _legacy_monolith_in_root(root)
    if legacy_path.exists():
        legacy = _read_json_object(legacy_path, label="legacy workflow-config.json")
        for key, value in legacy.items():
            if key in RESERVED_TOP_LEVEL_KEYS:
                if key not in merged:
                    merged[key] = value
            elif isinstance(value, dict) and key not in merged:
                merged[key] = value

    if not merged:
        raise ValueError(f"workflow-config not found: {pointer}")
    return merged


def get_stage_config(project_root: Path, stage: str, platform: Optional[str] = None) -> dict:
    return load_stage_config(project_root, stage, platform)


def compose_framework_config_keys(stage: str) -> frozenset[str]:
    """Compose URL field names from compose-profile.json → framework_templates values."""
    profile_path = _WORKFLOW_ROOT / stage / _COMPOSE_PROFILE_FILENAME
    if not profile_path.is_file():
        return frozenset()
    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return frozenset()
    templates = profile.get("framework_templates") or {}
    if not isinstance(templates, dict):
        return frozenset()
    return frozenset(str(value) for value in templates.values() if value)


def lookup_stage_config_value(cfg: dict, key: str) -> Optional[str]:
    """Resolve one URL/key from nested compose/eval or flat legacy stage config."""
    if not isinstance(cfg, dict):
        return None
    for bucket in ("compose", "eval"):
        section = cfg.get(bucket)
        if isinstance(section, dict) and key in section:
            value = str(section.get(key, "")).strip()
            return value or None
    if key in cfg and key not in _STAGE_CONFIG_BUCKETS:
        value = str(cfg.get(key, "")).strip()
        return value or None
    return None


def stage_config_has_key(cfg: dict, key: str) -> bool:
    if not isinstance(cfg, dict):
        return False
    for bucket in ("compose", "eval"):
        section = cfg.get(bucket)
        if isinstance(section, dict) and key in section:
            return True
    return key in cfg and key not in _STAGE_CONFIG_BUCKETS


def get_stage_config_value(
    project_root: Path,
    stage: str,
    key: str,
    platform: Optional[str] = None,
) -> str:
    cfg = load_stage_config(project_root, stage, platform)
    return lookup_stage_config_value(cfg, key) or ""


def get_stage_config_bucket(
    project_root: Path,
    stage: str,
    bucket: str,
    platform: Optional[str] = None,
) -> dict:
    if bucket not in _STAGE_CONFIG_BUCKETS:
        raise ValueError(f"invalid workflow config bucket: {bucket!r}")
    cfg = load_stage_config(project_root, stage, platform)
    section = cfg.get(bucket)
    if isinstance(section, dict):
        return dict(section)

    compose_keys = compose_framework_config_keys(stage)
    if not compose_keys:
        return {}
    if bucket == "compose":
        return {
            key: value
            for key, value in cfg.items()
            if key in compose_keys and key not in _STAGE_CONFIG_BUCKETS
        }
    return {
        key: value
        for key, value in cfg.items()
        if key not in compose_keys and key not in _STAGE_CONFIG_BUCKETS
    }


def nest_compose_stage_config(stage: str, flat_cfg: dict) -> dict:
    """Split a flat stage dict into compose/eval using compose-profile SSOT."""
    if not isinstance(flat_cfg, dict) or not flat_cfg:
        return flat_cfg if isinstance(flat_cfg, dict) else {}
    if "compose" in flat_cfg or "eval" in flat_cfg:
        return flat_cfg

    compose_keys = compose_framework_config_keys(stage)
    if not compose_keys:
        return flat_cfg

    compose: dict = {}
    eval_cfg: dict = {}
    for key, value in flat_cfg.items():
        if key in _DROP_ORPHAN_CONFIG_KEYS:
            continue
        if key in compose_keys:
            compose[key] = value
        else:
            eval_cfg[key] = value

    nested: dict = {}
    if compose:
        nested["compose"] = compose
    if eval_cfg:
        nested["eval"] = eval_cfg
    return nested or flat_cfg


def split_monolith_payload(payload: dict) -> tuple[dict, dict[str, dict]]:
    """Split a monolith workflow-config dict into manifest + per-stage configs."""
    if not isinstance(payload, dict):
        raise ValueError("workflow-config root must be a JSON object")

    manifest: dict = {}
    if "version" in payload:
        manifest["version"] = payload["version"]
    manifest["layout"] = "stages"

    stages: dict[str, dict] = {}
    for key, value in payload.items():
        if key in RESERVED_TOP_LEVEL_KEYS:
            continue
        if isinstance(value, dict):
            stages[key] = nest_compose_stage_config(key, value)
    return manifest, stages


def write_stage_configs(
    root: Path,
    manifest: dict,
    stages: dict[str, dict],
) -> None:
    """Write manifest.json and stages/*.json under root."""
    from fetch_template import atomic_write  # noqa: WPS433

    root.mkdir(parents=True, exist_ok=True)
    stages_dir = root / _STAGES_SUBDIR
    stages_dir.mkdir(parents=True, exist_ok=True)

    manifest_text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    atomic_write(root / _MANIFEST_FILENAME, manifest_text)

    for stage, stage_cfg in sorted(stages.items()):
        _validate_stage_name(stage)
        if not isinstance(stage_cfg, dict):
            raise ValueError(f"stage [{stage}] must be a JSON object")
        stage_text = json.dumps(stage_cfg, indent=2, ensure_ascii=False) + "\n"
        atomic_write(stages_dir / f"{stage}.json", stage_text)


def _migrate_platform_config_pointer_to_dir(
    project_root: Path,
    root: Path,
    platform: Optional[str] = None,
) -> None:
    rel_root = root.relative_to(project_root.resolve()).as_posix()
    if not rel_root.endswith("/"):
        rel_root = f"{rel_root}/"

    platform_cfg = read_platform_config(project_root, platform)
    current = str(platform_cfg.get("workflowConfig", "")).strip()
    if current.endswith(".json"):
        platform_cfg["workflowConfig"] = rel_root
        write_platform_config(project_root, platform_cfg, platform)


def apply_workflow_config_from_url(
    project_root: Path,
    url: str,
    *,
    platform: Optional[str] = None,
) -> Path:
    """Download monolith workflow-config JSON and write stages/ layout."""
    from fetch_template import gh_api_fetch, parse_blob_url  # noqa: WPS433

    parsed = parse_blob_url(url.strip())
    content = gh_api_fetch(
        parsed["owner"],
        parsed["repo"],
        parsed["ref"],
        parsed["path"],
    )
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"downloaded workflow-config is not valid JSON: {exc}") from exc

    manifest, stages = split_monolith_payload(payload)
    root = resolve_workflow_config_root(project_root, platform)
    write_stage_configs(root, manifest, stages)

    legacy_path = _legacy_monolith_in_root(root)
    if legacy_path.exists():
        legacy_path.unlink()

    _migrate_platform_config_pointer_to_dir(project_root, root, platform)
    return root


def extract_subagent_model(
    stage_cfg: dict,
    platform: Optional[str] = None,
) -> Optional[str]:
    """Extract optional subagent model slug from a pre-loaded stage config dict."""
    plat = detect_platform(platform)
    subagent = stage_cfg.get("subagent") or {}
    model = subagent.get(plat)
    if model is None:
        return None
    stripped = str(model).strip()
    return stripped if stripped else None


def resolve_subagent_model(
    project_root: Path,
    stage: str,
    platform: Optional[str] = None,
) -> Optional[str]:
    if not workflow_config_is_present(project_root, platform):
        return None
    try:
        stage_cfg = load_stage_config(project_root, stage, platform)
    except ValueError:
        return None
    return extract_subagent_model(stage_cfg, platform)


def default_configure_blob_url() -> str:
    return _DEFAULT_CONFIGURE_BLOB_URL
