---
name: lulu-dev-workflow
description: >-
  Top-level development workflow framework. Use when mentioning lulu-dev-workflow,
  开发工作流, dev workflow, product doc workflow, 产品文档流程, or any sub-stage
  (diagnostic, product, tech, work-order, code).
disable-model-invocation: true
---

# lulu-dev-workflow

A staged development workflow framework. Each stage is an independent sub-module
under this directory.

## Stages

| Stage | Module | Status |
|-------|--------|--------|
| Decision diagnostic | `diagnostic/` | Active |
| Product documentation | `product/` | Active |
| Tech design | `tech/` | Active |
| Work order | `work-order/` | Active |
| Code | `code/` | Active |

> **diagnostic is mandatory before /product or /tech.**
> Run diagnostic to produce a decision-doc before starting either workflow.

## Setup

### `install` — Machine-level, run once

```bash
REPO="lulufoo/lulu-dev-skills"; REF="main"; SRC="lulu-dev-workflow"
# Cursor:
DST="$HOME/.cursor/skills/lulu-dev-workflow"
# Copilot (uncomment, comment out Cursor line above):
# DST="$HOME/.copilot/skills/lulu-dev-workflow"

# pull_dir REMOTE_PATH LOCAL_PATH — downloads all files in a remote directory
pull_dir() {
  mkdir -p "$2"
  gh api "repos/$REPO/contents/$1?ref=$REF" --jq '.[] | select(.type=="file") | .name' \
    | while read f; do
        gh api "repos/$REPO/contents/$1/$f?ref=$REF" --jq '.content' | base64 -d > "$2/$f"
      done
}

mkdir -p "$DST"
gh api "repos/$REPO/contents/$SRC/SKILL.md?ref=$REF" --jq '.content' | base64 -d > "$DST/SKILL.md"
pull_dir "$SRC/scripts" "$DST/scripts"

for sub in diagnostic product tech work-order code; do
  mkdir -p "$DST/$sub"
  gh api "repos/$REPO/contents/$SRC/$sub/SKILL.md?ref=$REF" --jq '.content' | base64 -d > "$DST/$sub/SKILL.md"
  pull_dir "$SRC/$sub/scripts" "$DST/$sub/scripts" 2>/dev/null || true
  gh api "repos/$REPO/contents/$SRC/$sub/transition-whitelist.json?ref=$REF" \
    --jq '.content' 2>/dev/null | base64 -d > "$DST/$sub/transition-whitelist.json" 2>/dev/null || true
done

pull_dir "$SRC/product/templates" "$DST/product/templates"
```

After install, run `lulu-dev-workflow init` in the target project.

### `init` — Project-level, run once per project

> Prerequisite: `install` has been run.

```bash
# Cursor:
python3 ~/.cursor/skills/lulu-dev-workflow/scripts/init.py --project-root "$(pwd)"
# Copilot:
python3 ~/.copilot/skills/lulu-dev-workflow/scripts/init.py --project-root "$(pwd)" --platform copilot
```

Creates `<platform-dir>/lulu-dev-workflow/workflow-config.json` and registers all sub-workflow
hooks (`.cursor/hooks.json` for Cursor, `.github/hooks/hooks.json` for Copilot).

`workflow-config.json` contains the following fields:

| Field | Description |
|-------|-------------|
| `product.template_url` | 产品文档模板 |
| `product.review_checklist_url` | 进入评估前审查清单 |
| `product.pdqa_url` | PDQA 评估框架 |
| `tech.tpt_url` | 技术方案模板（Tech Plan Template） |
| `tech.tpef_url` | 技术方案评估框架（Tech Plan Evaluation Framework） |
| `tech.ptc_url` | 产品-技术交叉检查（Product-Tech Crosscheck） |
| `tech.ac_url` | 架构约束文档（如有） |
| `work_order.task_template_url` | 单个施工单模板 |
| `work_order.tasklist_template_url` | 施工单列表模板 |
| `work_order.twca_url` | TWCA 评审框架 |
| `work_order.woqa_url` | WOQA 质量评审框架 |
| `code.test_command` | 项目测试命令（默认: `npm test`） |
| `code.woqa_url` | TDD 质量审计框架 |

Run `lulu-dev-workflow configure <github-blob-url>` to apply a config. See `## Commands` below.

## Commands

### `configure` — Download and apply a workflow-config.json from GitHub

Usage: `lulu-dev-workflow configure <github-blob-url>`

`<github-blob-url>` is a GitHub `blob` URL pointing to a `workflow-config.json`, e.g.:

```
https://github.com/lulufoo/ai-software-dev/blob/main/lulu-dev-workflow-template/workflow-config.json
```

Parse the URL to extract `owner`, `repo`, `ref`, `path`, then run:

```bash
# Cursor:
gh api "repos/{owner}/{repo}/contents/{path}?ref={ref}" \
  --jq '.content' | base64 -d \
  > .cursor/lulu-dev-workflow/workflow-config.json
# Copilot:
gh api "repos/{owner}/{repo}/contents/{path}?ref={ref}" \
  --jq '.content' | base64 -d \
  > .github/lulu-dev-workflow/workflow-config.json
```

After download, read and display the new config file to confirm.

**Default template URL** (lulufoo standard config):
```
https://github.com/lulufoo/ai-software-dev/blob/main/lulu-dev-workflow-template/workflow-config.json
```

## Usage

Each stage has its own `SKILL.md` with start commands.

- **Decision diagnostic:** read `~/.cursor/skills/lulu-dev-workflow/diagnostic/SKILL.md` (Cursor) or `~/.copilot/skills/lulu-dev-workflow/diagnostic/SKILL.md` (Copilot)
- **Product doc:** read `~/.cursor/skills/lulu-dev-workflow/product/SKILL.md` (Cursor) or `~/.copilot/skills/lulu-dev-workflow/product/SKILL.md` (Copilot)
- **Tech design:** read `~/.cursor/skills/lulu-dev-workflow/tech/SKILL.md` (Cursor) or `~/.copilot/skills/lulu-dev-workflow/tech/SKILL.md` (Copilot)
- **Work order:** read `~/.cursor/skills/lulu-dev-workflow/work-order/SKILL.md` (Cursor) or `~/.copilot/skills/lulu-dev-workflow/work-order/SKILL.md` (Copilot)
- **Code:** read `~/.cursor/skills/lulu-dev-workflow/code/SKILL.md` (Cursor) or `~/.copilot/skills/lulu-dev-workflow/code/SKILL.md` (Copilot)
