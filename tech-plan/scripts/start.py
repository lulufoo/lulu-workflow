#!/usr/bin/env python3

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from hook_guard import (  # noqa: E402
    check_gate,
    current_effective_delivered,
    get_sessions,
    get_topic_doc,
    load_stage_order,
)
from invalidation_hook import invalidate_downstream  # noqa: E402

from archive import run as run_archive
from workflow_common import (
    CACHE_DIR,
    detect_container_type,
    load_container_meta,
    read_md_field,
    session_state_path,
    state_path,
    write_active_context,
    write_md_state,
    write_session_state,
)


_TO_STAGE = "tech-plan"
_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def _find_latest_delivered_stage(container_id: str, cycle_type: str,
                                  cache_dir: Path) -> "str | None":
    """Return the last stage in cycle order where current_effective_delivered is True."""
    try:
        stages = load_stage_order(cycle_type, _CONFIG_DIR)
    except Exception:
        return None
    latest = None
    for s in stages:
        if current_effective_delivered(container_id, s, cache_dir):
            latest = s
    return latest


def _mark_historical(container_id: str, stage: str, cache_dir: Path) -> None:
    """Add historical: true to frontmatter of the current effective delivered session."""
    sessions = [s for s in get_sessions(container_id, stage, cache_dir)
                if s.state != "Invalidated"]
    if not sessions:
        return
    latest = max(sessions, key=lambda s: (s.created_at, s.revision))
    ws_path = cache_dir / container_id / stage / latest.revision / "workflow-state.md"
    if not ws_path.exists():
        return
    text = ws_path.read_text(encoding="utf-8")
    if "historical:" not in text:
        updated = re.sub(r"(---\s*\n)", r"\1historical: true\n", text, count=1)
        ws_path.write_text(updated, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start a new tech-doc workflow session.")
    parser.add_argument("--project-root", default=".", help="Project root directory.")
    parser.add_argument("--feature-id", required=True, help="Feature ID (from feature_init.py).")
    parser.add_argument(
        "--run-mode",
        required=True,
        choices=["product", "tech"],
        help="Workflow mode: 'product' (requires --product-ref) or 'tech' (no product-ref).",
    )
    parser.add_argument("--product-ref", default="", help="Absolute path to product-doc.md (required for product mode).")
    parser.add_argument("--carry-forward-ref", default="", help="Absolute path to previous tech-doc.md (optional).")
    parser.add_argument(
        "--conversation-id",
        default="",
        help="Cursor/Copilot conversation ID for active-context indexing.",
    )
    return parser.parse_known_args()[0]


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    feature_id = args.feature_id.strip()

    container_type = detect_container_type(feature_id)

    run_mode = args.run_mode
    product_ref = args.product_ref.strip()
    carry_forward_ref = args.carry_forward_ref.strip()

    # Validate mode / product-ref consistency
    if run_mode == "product" and not product_ref:
        print("错误：--run-mode product 需要同时提供 --product-ref。")
        return 1
    if run_mode == "tech" and product_ref:
        print("错误：--run-mode tech 不能同时提供 --product-ref（两者互斥）。")
        return 1

    # Validate product_ref exists (product mode only)
    if product_ref and not Path(product_ref).exists():
        print(f"错误：product-ref 文件不存在：{product_ref}")
        return 1

    # Validate carry_forward_ref if provided
    if carry_forward_ref and not Path(carry_forward_ref).exists():
        print(f"错误：carry-forward-ref 文件不存在：{carry_forward_ref}")
        return 1

    cache_dir = project_root / CACHE_DIR
    try:
        load_container_meta(cache_dir, feature_id, container_type)
    except ValueError as e:
        print(f"错误：{e}")
        return 1

    # Step 2: re-open detection
    if current_effective_delivered(feature_id, _TO_STAGE, cache_dir):
        _mark_historical(feature_id, _TO_STAGE, cache_dir)
        invalidate_downstream(feature_id, _TO_STAGE, container_type, cache_dir)

    # Step 3: back-fill detection
    latest_stage = _find_latest_delivered_stage(feature_id, container_type, cache_dir)
    if latest_stage:
        try:
            _stages = load_stage_order(container_type, _CONFIG_DIR)
        except Exception:
            _stages = []
        if _TO_STAGE in _stages and latest_stage in _stages:
            if _stages.index(_TO_STAGE) < _stages.index(latest_stage):
                invalidate_downstream(feature_id, _TO_STAGE, container_type, cache_dir)

    # Step 4: check_gate
    ok, reason = check_gate(feature_id, _TO_STAGE, container_type, cache_dir, _CONFIG_DIR)
    if not ok:
        print(f"Gate blocked: {reason}", file=sys.stderr)
        sys.exit(1)

    # Step 5: get_topic_doc (feature containers only, if topic_id exists)
    try:
        topic_doc = get_topic_doc(feature_id, _TO_STAGE, cache_dir, _CONFIG_DIR)
        if topic_doc:
            print(f"Topic doc: {topic_doc}")
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # archive: deferred  archive_rc = run_archive(project_root, exclude_conv_id=feature_id)
    # archive: deferred  if archive_rc != 0:
    # archive: deferred      return archive_rc

    ss_path = project_root / session_state_path(feature_id)
    if ss_path.exists():
        try:
            active_doc = int(read_md_field(ss_path, "active_doc", default="0")) + 1
        except ValueError:
            active_doc = 1
    else:
        active_doc = 1

    write_session_state(ss_path, active_doc)
    write_active_context(
        project_root,
        feature_id,
        conversation_id=args.conversation_id.strip() or None,
        container_type=container_type,
    )

    ws_path = project_root / state_path(feature_id, active_doc)
    write_md_state(
        ws_path,
        "Drafting",
        evaluate_round=0,
        product_ref=product_ref,
        carry_forward_ref=carry_forward_ref,
        mode=run_mode,
    )

    if run_mode == "product":
        if carry_forward_ref:
            calibration_note = "⚠️  carry_forward_ref 存在，进入 Drafting 后必须强制校准（对比新 product-doc 与旧 tech-doc）。"
        else:
            calibration_note = "首次起草（产品需求模式），进入 Drafting 后必须校准（读取模板 + 架构约束 + product-doc）。"
    else:
        calibration_note = "技改模式：E1 意图对齐评估将跳过，仅执行 E3（代码库一致性）+ E2（方案质量）。"

    print(f"""
会话已启动。

会话状态文件：{ss_path.as_posix()}
当前技术文档：revision{active_doc}
状态文件：    {ws_path.as_posix()}
当前状态：    Drafting
运行模式：    {run_mode}
评估轮次：    0
product_ref：  {product_ref or '（无，技改模式）'}
carry_forward：{carry_forward_ref or '（无）'}

{calibration_note}
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
