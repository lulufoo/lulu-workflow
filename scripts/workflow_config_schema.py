#!/usr/bin/env python3
"""Authoritative I/O for workflow-config under $WORKFLOW_DIR.

Library module — CLI lives in workflow_config.py.

Layout:
  $WORKFLOW_DIR/
    manifest.json
    stages/{stage}.json
    workflow-guard-config.json

Same-dir leftover workflow-config.json is still readable. Leftover
config.json pointers and skill-config/lulu-workflow/ are ignored.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from platform_schema import PLATFORM_PATHS, detect_platform as _detect_platform
from platforms.registry import resolve_workflow_dir as _resolve_workflow_dir

_LEGACY_WORKFLOW_CONFIG_FILENAME = "workflow-config.json"
_STAGES_SUBDIR = "stages"
_MANIFEST_FILENAME = "manifest.json"
RESERVED_TOP_LEVEL_KEYS = frozenset({"version", "layout"})
_STAGE_CONFIG_BUCKETS = frozenset({"compose", "eval"})
_STAGE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_WORKFLOW_ROOT = Path(__file__).resolve().parents[1]
_COMPOSE_PROFILE_FILENAME = "compose-profile.json"
_DROP_ORPHAN_CONFIG_KEYS = frozenset(
    {
        "tdt_design_doc_template_url",
        "tpt_spec_template_url",
        "tdt_inductive_scan_criteria_url",
        "pst_inductive_scan_criteria_url",
    }
)
_LEGACY_COMPOSE_FRAMEWORK_KEYS = {
    "lulu-arch": frozenset(
        {
            "tat_section_registry_url",
            "tat_section_form_registry_url",
            "tat_section_kw_criteria_url",
            "tat_topic_role_instance_url",
            "tat_topic_domain_instance_url",
        }
    ),
    "lulu-blueprint": frozenset(
        {
            "pbt_section_registry_url",
            "pbt_section_form_registry_url",
            "pbt_section_kw_criteria_url",
            "pbt_topic_role_instance_url",
            "pbt_topic_domain_instance_url",
        }
    ),
    "lulu-design": frozenset(
        {
            "tdt_section_registry_url",
            "tdt_section_form_registry_url",
            "tdt_section_kw_criteria_url",
            "tdt_feature_role_instance_url",
            "tdt_feature_domain_instance_url",
        }
    ),
    "lulu-plan": frozenset(
        {
            "tpt_section_registry_url",
            "tpt_section_form_registry_url",
            "tpt_section_kw_criteria_url",
            "tpt_feature_role_instance_url",
            "tpt_feature_domain_instance_url",
        }
    ),
    "lulu-spec": frozenset(
        {
            "pst_section_registry_url",
            "pst_section_form_registry_url",
            "pst_section_kw_criteria_url",
            "pst_feature_role_instance_url",
            "pst_feature_domain_instance_url",
        }
    ),
}


def detect_platform(platform: Optional[str] = None) -> str:
    return _detect_platform(override=platform, strict=False)


def default_platform_config() -> dict:
    return {"version": 1}


def platform_config_path(project_root: Path, platform: Optional[str] = None) -> Path:
    plat = detect_platform(platform)
    return project_root / _resolve_workflow_dir(plat, project_root) / "config.json"


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
    """No-op. Pointer config.json is not part of the workflow-config contract."""
    del project_root, platform


def resolve_workflow_config_path(
    project_root: Path,
    platform: Optional[str] = None,
) -> Path:
    """Return the project workflow config root: $WORKFLOW_DIR."""
    plat = detect_platform(platform)
    return project_root / _resolve_workflow_dir(plat, project_root)


def resolve_workflow_config_root(
    project_root: Path,
    platform: Optional[str] = None,
) -> Path:
    """Return the directory that holds manifest.json and stages/."""
    return resolve_workflow_config_path(project_root, platform)


def _legacy_monolith_in_root(root: Path) -> Path:
    return root / _LEGACY_WORKFLOW_CONFIG_FILENAME


def _validate_stage_name(stage: str) -> None:
    if not stage or not _STAGE_NAME_RE.fullmatch(stage):
        raise ValueError(f"invalid workflow stage name: {stage!r}")


def _stage_file_in_root(root: Path, stage: str) -> Path:
    return root / _STAGES_SUBDIR / f"{stage}.json"


def _skill_stage_config_path(stage: str) -> Path:
    return _WORKFLOW_ROOT / stage / "config.json"


def _load_stage_from_stages_dir(root: Path, stage: str) -> dict:
    stage_path = _stage_file_in_root(root, stage)
    if not stage_path.exists():
        return {}
    return _read_json_object(stage_path, label=f"stage config [{stage}]")


def _load_stage_from_skill_root(stage: str) -> dict:
    stage_path = _skill_stage_config_path(stage)
    if not stage_path.exists():
        return {}
    return _read_json_object(stage_path, label=f"built-in stage config [{stage}]")


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
    """Return the project stage config or a built-in stage config fallback."""
    _validate_stage_name(stage)
    root = resolve_workflow_config_root(project_root, platform)
    project_path = _stage_file_in_root(root, stage)
    if project_path.exists():
        return project_path
    built_in_path = _skill_stage_config_path(stage)
    if built_in_path.exists():
        return built_in_path
    return project_path


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
    root = resolve_workflow_config_root(project_root, platform)
    monolith = _legacy_monolith_in_root(root)

    stage_cfg = _load_stage_from_stages_dir(root, stage)
    if stage_cfg:
        return stage_cfg
    stage_cfg = _load_stage_from_legacy_monolith(monolith, stage)
    if stage_cfg:
        return stage_cfg
    return _load_stage_from_skill_root(stage)


def workflow_config_is_present(project_root: Path, platform: Optional[str] = None) -> bool:
    root = resolve_workflow_config_root(project_root, platform)
    if _stages_layout_present(root):
        return True
    return _legacy_monolith_in_root(root).exists()


def load_workflow_config(project_root: Path, platform: Optional[str] = None) -> dict:
    """Load merged workflow config (manifest + all stages). Raises ValueError if absent."""
    root = resolve_workflow_config_root(project_root, platform)
    if not workflow_config_is_present(project_root, platform):
        raise ValueError(f"workflow-config not found: {root}")

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
        raise ValueError(f"workflow-config not found: {root}")
    return merged


def get_stage_config(project_root: Path, stage: str, platform: Optional[str] = None) -> dict:
    return load_stage_config(project_root, stage, platform)


def compose_framework_config_keys(stage: str) -> frozenset[str]:
    """Return legacy Compose config keys for flat-config compatibility."""
    profile_path = _WORKFLOW_ROOT / stage / _COMPOSE_PROFILE_FILENAME
    keys = set(_LEGACY_COMPOSE_FRAMEWORK_KEYS.get(stage, ()))
    if not profile_path.is_file():
        return frozenset(keys)
    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return frozenset(keys)
    templates = profile.get("framework_templates") or {}
    if not isinstance(templates, dict):
        return frozenset(keys)
    for value in templates.values():
        ref = str(value).strip() if isinstance(value, str) else ""
        if ref and not ref.startswith("lulu-workflow/"):
            keys.add(ref)
    return frozenset(keys)


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


def iter_builtin_stage_configs() -> list[tuple[str, dict]]:
    """Return (stage, payload) for each skill-root ``{stage}/config.json``."""
    found: list[tuple[str, dict]] = []
    for child in sorted(_WORKFLOW_ROOT.iterdir()):
        if not child.is_dir() or not _STAGE_NAME_RE.fullmatch(child.name):
            continue
        stage_path = child / "config.json"
        if not stage_path.is_file():
            continue
        found.append(
            (
                child.name,
                _read_json_object(stage_path, label=f"built-in stage config [{child.name}]"),
            )
        )
    return found


# Skill-root `{stage}/config.json` is the default. Init copies only project-local
# seeds into $WORKFLOW_DIR/stages/. Skill-owned defaults (e.g. lulu-tasks) stay
# in the skill package and are read via `_load_stage_from_skill_root`.
_INIT_SEEDED_STAGES = frozenset({"lulu-exec"})


def ensure_builtin_stage_configs(
    project_root: Path,
    platform: Optional[str] = None,
) -> list[Path]:
    """Write missing project-seeded $WORKFLOW_DIR/stages/{stage}.json.

    Copies only `_INIT_SEEDED_STAGES`. Does not overwrite existing stage files.
    Creates manifest.json when missing.
    """
    from fetch_template import atomic_write  # noqa: WPS433

    stages = [
        (name, payload)
        for name, payload in iter_builtin_stage_configs()
        if name in _INIT_SEEDED_STAGES
    ]
    if not stages:
        return []

    root = resolve_workflow_config_root(project_root, platform)
    root.mkdir(parents=True, exist_ok=True)
    stages_dir = root / _STAGES_SUBDIR
    stages_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = root / _MANIFEST_FILENAME
    if not manifest_path.exists():
        manifest_text = json.dumps({"version": 1, "layout": "stages"}, indent=2) + "\n"
        atomic_write(manifest_path, manifest_text)

    created: list[Path] = []
    for stage, payload in stages:
        dest = _stage_file_in_root(root, stage)
        if dest.exists():
            continue
        stage_text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        atomic_write(dest, stage_text)
        created.append(dest)
    return created


def apply_workflow_config_from_url(
    project_root: Path,
    url: str,
    *,
    platform: Optional[str] = None,
) -> Path:
    """Load a local or explicit GitHub source and write the stages layout."""
    source = url.strip()
    local_source = Path(source[7:]) if source.startswith("file://") else Path(source)
    if local_source.is_file():
        content = local_source.read_text(encoding="utf-8")
    else:
        from fetch_template import gh_api_fetch, parse_blob_url  # noqa: WPS433

        parsed = parse_blob_url(source)
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

    return root


def lookup_subagent(stage_cfg: dict) -> str:
    """Return the stage's subagent model string, or '' when unset."""
    raw = stage_cfg.get("subagent", "")
    if not isinstance(raw, str):
        return ""
    return raw.strip()
