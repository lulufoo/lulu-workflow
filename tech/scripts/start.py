#!/usr/bin/env python3

import argparse
from pathlib import Path

from workflow_common import (
    read_md_field,
    session_state_path,
    state_path,
    write_md_state,
    write_session_state,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start a new tech-doc workflow session.")
    parser.add_argument("--project-root", default=".", help="Project root directory.")
    parser.add_argument("--conversation-id", required=True, help="Current Cursor conversation ID.")
    parser.add_argument("--product-ref", required=True, help="Absolute path to product-doc.md.")
    parser.add_argument("--carry-forward-ref", default="", help="Absolute path to previous tech-doc.md (optional).")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    conv_id = args.conversation_id.strip()
    product_ref = args.product_ref.strip()
    carry_forward_ref = args.carry_forward_ref.strip()

    # Validate product_ref exists
    if not Path(product_ref).exists():
        print(f"错误：product-ref 文件不存在：{product_ref}")
        return 1

    # Validate carry_forward_ref if provided
    if carry_forward_ref and not Path(carry_forward_ref).exists():
        print(f"错误：carry-forward-ref 文件不存在：{carry_forward_ref}")
        return 1

    ss_path = project_root / session_state_path(conv_id)
    if ss_path.exists():
        try:
            active_doc = int(read_md_field(ss_path, "active_doc", default="0")) + 1
        except ValueError:
            active_doc = 1
    else:
        active_doc = 1

    write_session_state(ss_path, active_doc)

    ws_path = project_root / state_path(conv_id, active_doc)
    write_md_state(
        ws_path,
        "Drafting",
        evaluate_round=0,
        product_ref=product_ref,
        carry_forward_ref=carry_forward_ref,
    )

    calibration_note = (
        "⚠️  carry_forward_ref 存在，进入 Drafting 后必须强制校准（对比新 product-doc 与旧 tech-doc）。"
        if carry_forward_ref
        else "首次起草，进入 Drafting 后必须校准（读取模板 + 架构约束 + product-doc）。"
    )

    print(f"""
会话已启动。

会话状态文件：{ss_path.as_posix()}
当前技术文档：r{active_doc}
状态文件：    {ws_path.as_posix()}
当前状态：    Drafting
评估轮次：    0
product_ref：  {product_ref}
carry_forward：{carry_forward_ref or '（无）'}

{calibration_note}
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
