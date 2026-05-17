#!/usr/bin/env python3

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from workflow_common import (
    CACHE_DIR,
    WHITELIST_PATH,
    normalize_tool_path,
    parse_frontmatter_fields,
    parse_frontmatter_state,
    read_md_field,
    read_json,
    read_md_state,
)

# Matches: .cache/lulu-dev-workflow/work-order/<conv_id>/r{N}/workflow-state.md
_CACHE_PARTS = (".cache", "lulu-dev-workflow", "work-order")


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
    """Return (conv_id, doc_round_str) if path is r{N}/workflow-state.md under work-order cache."""
    parts = Path(path).parts
    if (
        len(parts) == 6
        and parts[:3] == _CACHE_PARTS
        and re.match(r"^r\d+$", parts[4])
        and parts[5] == "workflow-state.md"
    ):
        return parts[3], parts[4]  # conv_id, r{N}
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
    match = match_workflow_state_path(path)

    if match is None:
        print(json.dumps(allow()))
        return 0

    conv_id, doc_round_str = match
    doc_path = project_root / CACHE_DIR / "work-order" / conv_id / doc_round_str

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
            f"Illegal transition: '{current_state}' → '{to_state}'.",
            "Requested transition is not in the workflow whitelist.",
        )))
        return 0

    if to_state == "ReadyForDelivery":
        # evaluate_round is read from the incoming workflow-state.md contents
        fields = parse_frontmatter_fields(contents)
        try:
            evaluate_round = int(fields.get("evaluate_round", "0"))
        except ValueError:
            evaluate_round = 0
        eval_dir = doc_path / f"evaluate{evaluate_round}"

        # 1. evaluate-state.md must exist
        eval_state_file = doc_path / "evaluate-state.md"
        if not eval_state_file.exists():
            print(json.dumps(deny(
                "evaluate-state.md 不存在，评估尚未初始化。请先进入 Evaluating 并完成 W1/W2 评估。",
                "evaluate-state.md must exist before ReadyForDelivery.",
            )))
            return 0

        eval_state_content = eval_state_file.read_text(encoding="utf-8")
        eval_fields = parse_frontmatter_fields(eval_state_content)

        # 2. current_dimension must be "done"
        if eval_fields.get("current_dimension") != "done":
            dim = eval_fields.get("current_dimension", "unknown")
            print(json.dumps(deny(
                f"评估未完成（current_dimension: {dim}）。请完成 W1→W2 全部评估后再推进。",
                "evaluate-state.md current_dimension must be 'done' before ReadyForDelivery.",
            )))
            return 0

        # 3. w1_status must be complete
        w1_status = eval_fields.get("w1_status", "")
        if w1_status != "complete":
            print(json.dumps(deny(
                f"W1（TWCA）评估未完成（w1_status: {w1_status}）。请处理所有 W1 问题后再推进。",
                "evaluate-state.md w1_status must be 'complete' before ReadyForDelivery.",
            )))
            return 0

        # 4. w2_status must be complete
        w2_status = eval_fields.get("w2_status", "")
        if w2_status != "complete":
            print(json.dumps(deny(
                f"W2（WOQA）评估未完成（w2_status: {w2_status}）。请处理所有 W2 问题后再推进。",
                "evaluate-state.md w2_status must be 'complete' before ReadyForDelivery.",
            )))
            return 0

        # 5. wo-review-e{M}1.md (W1 report) must exist
        w1_review = eval_dir / f"wo-review-e{evaluate_round}1.md"
        if not w1_review.exists():
            print(json.dumps(deny(
                f"evaluate{evaluate_round}/wo-review-e{evaluate_round}1.md 不存在，请先完成 W1（TWCA）评审。",
                f"evaluate{evaluate_round}/wo-review-e{evaluate_round}1.md must exist before ReadyForDelivery.",
            )))
            return 0

        # 6. wo-review-e{M}2.md (W2 report) must exist
        w2_review = eval_dir / f"wo-review-e{evaluate_round}2.md"
        if not w2_review.exists():
            print(json.dumps(deny(
                f"evaluate{evaluate_round}/wo-review-e{evaluate_round}2.md 不存在，请先完成 W2（WOQA）评审。",
                f"evaluate{evaluate_round}/wo-review-e{evaluate_round}2.md must exist before ReadyForDelivery.",
            )))
            return 0

    if to_state == "Delivered":
        gate_file = doc_path / "human-delivery-gate.md"
        if not gate_file.exists():
            print(json.dumps(deny(
                "ReadyForDelivery → Delivered 需要先写入 human-delivery-gate.md（用户确认交付）。",
                "Write human-delivery-gate.md to confirm user approval before transitioning to Delivered.",
            )))
            return 0

    print(json.dumps(allow()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
