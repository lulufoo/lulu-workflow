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
mkdir -p ~/.cursor/skills/lulu-dev-workflow/scripts
mkdir -p ~/.cursor/skills/lulu-dev-workflow/diagnostic
mkdir -p ~/.cursor/skills/lulu-dev-workflow/product/scripts
mkdir -p ~/.cursor/skills/lulu-dev-workflow/product/templates
mkdir -p ~/.cursor/skills/lulu-dev-workflow/tech/scripts
mkdir -p ~/.cursor/skills/lulu-dev-workflow/work-order/scripts
mkdir -p ~/.cursor/skills/lulu-dev-workflow/code/scripts

# top-level
for f in SKILL.md scripts/init.py; do
  gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/$f" \
    --jq '.content' | base64 -d \
    > ~/.cursor/skills/lulu-dev-workflow/$f
done

# diagnostic
for f in SKILL.md; do
  gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/diagnostic/$f" \
    --jq '.content' | base64 -d \
    > ~/.cursor/skills/lulu-dev-workflow/diagnostic/$f
done

# product
for f in SKILL.md transition-whitelist.json; do
  gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/product/$f" \
    --jq '.content' | base64 -d \
    > ~/.cursor/skills/lulu-dev-workflow/product/$f
done
for f in hook_guard.py init.py start.py workflow_common.py; do
  gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/product/scripts/$f" \
    --jq '.content' | base64 -d \
    > ~/.cursor/skills/lulu-dev-workflow/product/scripts/$f
done
gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/product/templates/workflow-config.template.json" \
  --jq '.content' | base64 -d \
  > ~/.cursor/skills/lulu-dev-workflow/product/templates/workflow-config.template.json

# tech
for f in SKILL.md transition-whitelist.json; do
  gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/tech/$f" \
    --jq '.content' | base64 -d \
    > ~/.cursor/skills/lulu-dev-workflow/tech/$f
done
for f in hook_guard.py init.py start.py workflow_common.py; do
  gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/tech/scripts/$f" \
    --jq '.content' | base64 -d \
    > ~/.cursor/skills/lulu-dev-workflow/tech/scripts/$f
done

# work-order
for f in SKILL.md transition-whitelist.json; do
  gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/work-order/$f" \
    --jq '.content' | base64 -d \
    > ~/.cursor/skills/lulu-dev-workflow/work-order/$f
done
for f in hook_guard.py init.py start.py workflow_common.py; do
  gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/work-order/scripts/$f" \
    --jq '.content' | base64 -d \
    > ~/.cursor/skills/lulu-dev-workflow/work-order/scripts/$f
done

# code
for f in SKILL.md transition-whitelist.json; do
  gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/code/$f" \
    --jq '.content' | base64 -d \
    > ~/.cursor/skills/lulu-dev-workflow/code/$f
done
for f in hook_guard.py init.py start.py workflow_common.py; do
  gh api "repos/lulufoo/lulu-dev-skills/contents/lulu-dev-workflow/code/scripts/$f" \
    --jq '.content' | base64 -d \
    > ~/.cursor/skills/lulu-dev-workflow/code/scripts/$f
done
```

After install, run `lulu-dev-workflow init` in the target project.

### `init` — Project-level, run once per project

> Prerequisite: `install` has been run.

```bash
python3 ~/.cursor/skills/lulu-dev-workflow/scripts/init.py --project-root "$(pwd)"
```

Creates `.cursor/lulu-dev-workflow/workflow-config.json` and registers all sub-workflow
hooks into `.cursor/hooks.json`.

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
gh api "repos/{owner}/{repo}/contents/{path}?ref={ref}" \
  --jq '.content' | base64 -d \
  > .cursor/lulu-dev-workflow/workflow-config.json
```

After download, read and display the new `.cursor/lulu-dev-workflow/workflow-config.json` to confirm.

**Default template URL** (lulufoo standard config):
```
https://github.com/lulufoo/ai-software-dev/blob/main/lulu-dev-workflow-template/workflow-config.json
```

## Usage

Each stage has its own `SKILL.md` with start commands.

- **Decision diagnostic:** read `~/.cursor/skills/lulu-dev-workflow/diagnostic/SKILL.md`
- **Product doc:** read `~/.cursor/skills/lulu-dev-workflow/product/SKILL.md`
- **Tech design:** read `~/.cursor/skills/lulu-dev-workflow/tech/SKILL.md`
- **Work order:** read `~/.cursor/skills/lulu-dev-workflow/work-order/SKILL.md`
- **Code:** read `~/.cursor/skills/lulu-dev-workflow/code/SKILL.md`
