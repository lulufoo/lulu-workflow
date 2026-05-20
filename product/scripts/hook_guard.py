#!/usr/bin/env python3

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from workflow_common import (
    CACHE_DIR,
    WHITELIST_PATH,
    is_current_session_active,
    normalize_tool_path,
    parse_frontmatter_fields,
    parse_frontmatter_state,
    read_md_field,
    read_json,
    read_md_state,
)

# Matches: .cache/lulu-dev-workflow/product/<conv_id>/revision{N}/workflow-state.md
_CACHE_PARTS = (".cache", "lulu-dev-workflow", "product")


def allow() -> Dict[str, str]:
    return {"permission": "allow"}


def deny(user_message: str, agent_message: str = "") -> Dict[str, str]:
    payload = {"permission": "deny", "user_message": user_message}
    if agent_message:
        payload["agent_message"] = agent_message
    return payload


def load_event() -> Dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    return json.loads(raw)


def extract_tool_name(event: Dict[str, Any]) -> str:
    return str(event.get("tool_name") or event.get("tool") or event.get("name") or "")


def extract_path_and_contents(event: Dict[str, Any], project_root: Path) -> Tuple[str, str]:
    tool_input = event.get("tool_input") or event.get("arguments") or {}
    raw_path = (
        tool_input.get("path")
        or tool_input.get("target_file")
        or tool_input.get("file_path")
        or ""
    )
    normalized = normalize_tool_path(str(raw_path), project_root) if raw_path else ""
    contents = tool_input.get("content") or tool_input.get("contents")
    return normalized, (contents if isinstance(contents, str) else "")


def match_workflow_state_path(path: str) -> Optional[Tuple[str, str]]:
    """Return (conv_id, doc_round_str) if path is revision{N}/workflow-state.md under product cache.

    Expected: .cache/lulu-dev-workflow/product/<conv_id>/revision{N}/workflow-state.md
    """
    parts = Path(path).parts
    if (
        len(parts) == 6
        and parts[:3] == _CACHE_PARTS
        and re.match(r"^revision\d+$", parts[4])
        and parts[5] == "workflow-state.md"
    ):
        return parts[3], parts[4]  # conv_id, revision{N}
    return None


def main() -> int:
    project_root = Path.cwd()

    try:
        event = load_event()
    except json.JSONDecodeError as exc:
        print(json.dumps(deny(f"Invalid hook input JSON: {exc}")))
        return 0

    tool_name = extract_tool_name(event)
    if tool_name not in {"Write", "Edit"}:
        print(json.dumps(allow()))
        return 0

    path, contents = extract_path_and_contents(event, project_root)

    conv_id = str(event.get("conversation_id") or "")
    if path and is_current_session_active(project_root, conv_id):
        allowed_root = (project_root / CACHE_DIR).resolve()
        abs_path = (project_root / Path(path)).resolve()
        try:
            abs_path.relative_to(allowed_root)
        except ValueError:
            print(json.dumps(deny(
                "planning workflow 进行中：只允许写入 .cache/lulu-dev-workflow/ 目录，不允许修改项目源码或其他文件。",
                "Path guard active: writes outside .cache/lulu-dev-workflow/ are blocked during planning workflow.",
            )))
            return 0

    match = match_workflow_state_path(path)

    if match is None:
        print(json.dumps(allow()))
        return 0

    conv_id, doc_round_str = match
    doc_path = project_root / CACHE_DIR / "product" / conv_id / doc_round_str

    if tool_name == "Edit" and not contents:
        print(json.dumps(deny(
            "Workflow state file must be written in full, not as a partial Edit.",
            "Use a full Write operation when updating workflow-state.md.",
        )))
        return 0

    to_state = parse_frontmatter_state(contents)
    if not to_state:
        print(json.dumps(deny(
            "workflow-state.md must contain a YAML frontmatter block with a 'current_state' field.",
            "Ensure the file starts with '---' and includes 'current_state: <State>'.",
        )))
        return 0

    state_file = doc_path / "workflow-state.md"
    current_state = read_md_state(state_file, default="Drafting")

    if to_state == current_state:
        print(json.dumps(allow()))
        return 0

    whitelist = read_json(WHITELIST_PATH, default={"allowed_transitions": []})
    allowed_edges = {
        (edge.get("from"), edge.get("to"))
        for edge in whitelist.get("allowed_transitions", [])
    }

    if (current_state, to_state) not in allowed_edges:
        print(json.dumps(deny(
            f"Illegal transition: '{current_state}' \u2192 '{to_state}'.",
            "Requested transition is not in the workflow whitelist.",
        )))
        return 0

    if to_state == "ReadyForDelivery":
        fields = parse_frontmatter_fields(contents)
        try:
            evaluate_round = int(fields.get("evaluate_round", "0"))
        except ValueError:
            evaluate_round = 0
        e_dir = doc_path / f"evaluate{evaluate_round}"

        eval_state_file = doc_path / "evaluate-state.md"
        if not eval_state_file.exists():
            print(json.dumps(deny(
                "evaluate-state.md 不存在，评估尚未初始化。请先进入 Evaluating 并完成 PDQA 评估。",
                "evaluate-state.md must exist with status: complete before ReadyForDelivery.",
            )))
            return 0

        eval_status = read_md_field(eval_state_file, "status")
        if eval_status != "complete":
            print(json.dumps(deny(
                f"评估未完成（evaluate-state.md status: {eval_status}）。请处理所有 PDQA 问题后再推进。",
                "evaluate-state.md status must be 'complete' before ReadyForDelivery.",
            )))
            return 0

        pdqa_file = e_dir / "pdqa-review.md"
        if not pdqa_file.exists():
            print(json.dumps(deny(
                f"evaluate{evaluate_round}/pdqa-review.md 不存在，请先写入 PDQA 评估记录。",
                f"evaluate{evaluate_round}/pdqa-review.md must exist before ReadyForDelivery.",
            )))
            return 0

        main_doc_file = doc_path / "product-doc.md"
        if not main_doc_file.is_file():
            print(json.dumps(deny(
                f"{doc_round_str}/product-doc.md 不存在，请先完成产品文档起草或评估修订。",
                f"{doc_round_str}/product-doc.md must exist before ReadyForDelivery.",
            )))
            return 0

        if main_doc_file.stat().st_size == 0:
            print(json.dumps(deny(
                f"{doc_round_str}/product-doc.md 为空，请写入产品文档内容后再推进。",
                f"{doc_round_str}/product-doc.md must be non-empty before ReadyForDelivery.",
            )))
            return 0

    if to_state == "Delivered":
        gate_file = doc_path / "human-delivery-gate.md"
        if not gate_file.exists():
            print(json.dumps(deny(
                "ReadyForDelivery \u2192 Delivered requires human-delivery-gate.md to exist first.",
                "Write human-delivery-gate.md to confirm user approval before transitioning to Delivered.",
            )))
            return 0

    print(json.dumps(allow()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
