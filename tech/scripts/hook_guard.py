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

# Matches: .cache/<platform>/lulu-dev-workflow/tech-doc/<conv_id>/revision{N}/workflow-state.md
_PLATFORM = CACHE_DIR.parts[1]
_CACHE_PARTS = (".cache", _PLATFORM, "lulu-dev-workflow", "tech")


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
    """Return (conv_id, doc_round_str) if path is revision{N}/workflow-state.md under tech-doc cache."""
    parts = Path(path).parts
    if (
        len(parts) == 7
        and parts[:4] == _CACHE_PARTS
        and re.match(r"^revision\d+$", parts[5])
        and parts[6] == "workflow-state.md"
    ):
        return parts[4], parts[5]  # conv_id, revision{N}
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
                f"planning workflow 进行中：只允许写入 .cache/{_PLATFORM}/lulu-dev-workflow/ 目录，不允许修改项目源码或其他文件。",
                f"Path guard active: writes outside .cache/{_PLATFORM}/lulu-dev-workflow/ are blocked during planning workflow.",
            )))
            return 0

    match = match_workflow_state_path(path)

    if match is None:
        print(json.dumps(allow()))
        return 0

    conv_id, doc_round_str = match
    doc_path = project_root / CACHE_DIR / "tech" / conv_id / doc_round_str

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


    if to_state == "Drafting" and current_state == "Evaluating":
        eval_state_file = doc_path / "evaluate-state.md"
        if not eval_state_file.exists():
            print(json.dumps(deny(
                "evaluate-state.md 不存在，请先将评估标记为 abandoned 后再回退 Drafting。",
                "Write evaluate-state.md with current_dimension: abandoned before transitioning to Drafting.",
            )))
            return 0
        eval_fields = parse_frontmatter_fields(eval_state_file.read_text(encoding="utf-8"))
        if eval_fields.get("current_dimension") != "abandoned":
            print(json.dumps(deny(
                "Evaluating → Drafting 需先将 evaluate-state.md 的 current_dimension 设为 abandoned。",
                "Write evaluate-state.md with current_dimension: abandoned before transitioning to Drafting.",
            )))
            return 0

    if to_state == "ReadyForDelivery":
        fields = parse_frontmatter_fields(contents)

        # Drafting → ReadyForDelivery: skip E1/E2/E3 when user explicitly requested
        if current_state == "Drafting":
            skip_flag = str(fields.get("skip_evaluate_requested", "")).lower()
            if skip_flag != "true":
                print(json.dumps(deny(
                    "从 Drafting 进入 ReadyForDelivery 须用户显式要求跳过评估，"
                    "并在 workflow-state 中设置 skip_evaluate_requested: true。",
                    "Set skip_evaluate_requested: true only after the user explicitly "
                    "requests to skip evaluation.",
                )))
                return 0

            tech_doc_file = doc_path / "tech-doc.md"
            if not tech_doc_file.is_file():
                print(json.dumps(deny(
                    f"{doc_round_str}/tech-doc.md 不存在，请先完成技术方案起草。",
                    f"{doc_round_str}/tech-doc.md must exist before ReadyForDelivery.",
                )))
                return 0

            if tech_doc_file.stat().st_size == 0:
                print(json.dumps(deny(
                    f"{doc_round_str}/tech-doc.md 为空，请写入技术方案内容后再推进。",
                    f"{doc_round_str}/tech-doc.md must be non-empty before ReadyForDelivery.",
                )))
                return 0

        elif current_state == "Evaluating":
            pass  # fall through to evaluate pre-conditions below
        else:
            print(json.dumps(deny(
                f"无法从 '{current_state}' 进入 ReadyForDelivery。",
                "ReadyForDelivery is only reachable from Drafting (skip evaluate) "
                "or Evaluating (evaluate complete).",
            )))
            return 0

        if current_state != "Evaluating":
            # Drafting skip-eval path: no evaluate files required
            print(json.dumps(allow()))
            return 0

        # Evaluating → ReadyForDelivery: full evaluate pre-conditions
        try:
            evaluate_round = int(fields.get("evaluate_round", "0"))
        except ValueError:
            evaluate_round = 0
        eval_dir = doc_path / f"evaluate{evaluate_round}"

        run_mode = read_md_field(state_file, "mode", default="product")
        is_tech_mode = run_mode == "tech"

        eval_state_file = doc_path / "evaluate-state.md"
        if not eval_state_file.exists():
            print(json.dumps(deny(
                "evaluate-state.md 不存在，评估尚未初始化。请先进入 Evaluating 并完成评估。",
                "evaluate-state.md must exist before ReadyForDelivery.",
            )))
            return 0

        eval_state_content = eval_state_file.read_text(encoding="utf-8")
        eval_fields = parse_frontmatter_fields(eval_state_content)

        # 2. current_dimension must be "done"
        if eval_fields.get("current_dimension") != "done":
            dim = eval_fields.get("current_dimension", "unknown")
            expected = "E2→E3" if is_tech_mode else "E1→E2→E3"
            print(json.dumps(deny(
                f"评估未完成（current_dimension: {dim}）。请完成 {expected} 全部评估后再推进。",
                "evaluate-state.md current_dimension must be 'done' before ReadyForDelivery.",
            )))
            return 0

        # 3. required dimensions must be complete
        # tech mode skips E1; product mode requires all three
        required_dims = ("e2", "e3") if is_tech_mode else ("e1", "e2", "e3")
        for dim in required_dims:
            status = eval_fields.get(f"{dim}_status", "")
            if status != "complete":
                print(json.dumps(deny(
                    f"{dim} 评估未完成（{dim}_status: {status}）。请处理所有问题后再推进。",
                    f"evaluate-state.md {dim}_status must be 'complete' before ReadyForDelivery.",
                )))
                return 0

        # 4. review files must exist (e2→seq 2, e3→seq 3; tech mode skips e1→seq 1)
        dim_seq = {"e2": 2, "e3": 3} if is_tech_mode else {"e1": 1, "e2": 2, "e3": 3}
        for dim, seq in dim_seq.items():
            review_file = eval_dir / f"tech-review-e{evaluate_round}{seq}.md"
            if not review_file.exists():
                print(json.dumps(deny(
                    f"evaluate{evaluate_round}/tech-review-e{evaluate_round}{seq}.md 不存在，请先完成 {dim.upper()} 评审。",
                    f"evaluate{evaluate_round}/tech-review-e{evaluate_round}{seq}.md must exist before ReadyForDelivery.",
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
