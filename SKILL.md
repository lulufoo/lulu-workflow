---
name: lulu-dev-workflow
description: >-
  Top-level development workflow framework. Use when mentioning lulu-dev-workflow,
  开发工作流, dev workflow, product doc workflow, 产品文档流程, or any sub-stage
  (diagnostic, product, tech, work-order, code).
disable-model-invocation: true
argument-hint: "[d=diagnostic | p=product | t=tech | w=work-order | c=code]"
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

## Stage Transitions

When a stage delivers, AI must list the allowed next stages from the whitelist below, recommend one, and wait for explicit user selection. AI must not infer and execute the next stage autonomously.

**Whitelist:**

| Current Stage | Allowed Next → |
|---|---|
| `diagnostic` | `tech` / `product` |
| `product` | `tech` |
| `tech` | `work-order` |
| `work-order` | `code` |
| `code` | done |

> `tech` → `code` is **prohibited** — bypasses task breakdown and TDD-first discipline in `work-order`.

### Stage Rollback

Any participant may trigger a Stage Rollback when new information shows a prior stage's output is no longer valid:

- **Trigger:** state the target stage to roll back to (any prior stage, any number of levels back)
- **Effect:** target stage + all downstream stages are invalidated; they must be redone from scratch
- **AI must announce:** "[target stage] and all downstream stages are invalidated. Restarting from [target stage]."

Stage Rollback is distinct from the diagnostic `Re-open` mechanism (which operates within a single diagnostic session on gate-level inputs).

## Platform Context

**Detect once at session start, substitute `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, and `$CACHE_DIR` throughout:**

| | Cursor | Copilot |
|---|---|---|
| `$PLATFORM` | `cursor` | `copilot` |
| `$SKILL_ROOT` | `~/.cursor/skills/lulu-dev-workflow` | `~/.copilot/skills/lulu-dev-workflow` |
| `$WORKFLOW_DIR` | `.cursor/lulu-dev-workflow` | `.github/lulu-dev-workflow` |
| `$CACHE_DIR` | `.cache/cursor/lulu-dev-workflow` | `.cache/copilot/lulu-dev-workflow` |

> **Detect:** `COPILOT_AGENT=1` env var → Copilot; `VSCODE_TARGET_SESSION_LOG` template variable present → Copilot; otherwise → Cursor.

## Feature Context

**Run at session start for every sub-workflow. Substitute `$CACHE_DIR` from Platform Context.**

**Fast path:** Find the latest `LULU-DEV-WORKFLOW: <id>` line in this conversation's AI responses (skip conversation-summary blocks). If found and no ambiguity signal → use it as `feature_id`.

Read `$CACHE_DIR/features.json[feature_id]`:
- If value is a string (legacy format) → `execution_mode = "assisted"`
- If value is an object → `execution_mode = value["execution_mode"]`
- If feature_id not found in features.json → `execution_mode = "assisted"`

Set `$EXECUTION_MODE = execution_mode`.

**Slow path:**

If the triggering message already contains a clear feature description → derive name → `Feature name: "<derived name>". Correct?` → confirmed:
Ask: "Execution mode: (1) assisted (default) (2) self-service?" Wait for selection; Enter alone → default `assisted`.
Run `feature_init.py --project-root "$(pwd)" --name "<name>" --mode "<mode>"`, set `$EXECUTION_MODE = mode` (done). Otherwise:

1. Read `$CACHE_DIR/features.json` → display list as `{n}. {name} [{execution_mode}]` (if value is legacy string format, show `[assisted]`); last entry: "New — type a description to create"
2. Prompt once: `Enter number to select, or type a description to create a new feature:`
3. Wait for single response, then branch:

   | Input | Action |
   |---|---|
   | Pure integer | Select that existing feature; extract `execution_mode` using the same rules as Fast path, set `$EXECUTION_MODE` |
   | Any other text | Ask: "Execution mode: (1) assisted (default) (2) self-service?" Wait for selection; Enter alone → default `assisted`. Run `feature_init.py --project-root "$(pwd)" --name "<user_input>" --mode "<mode>"`, set `$EXECUTION_MODE = mode` |

   _(Name is a working title; update `features.json` directly if refinement needed.)_

Append `LULU-DEV-WORKFLOW: <feature_id>` to every workflow AI response.

After confirming `feature_id`, only read workflow documents from `$CACHE_DIR/<feature_id>/`.

> Ambiguity signals: no footer in conversation · user mentions a different feature · user says "switch" / "new" / "choose"

**Output variables:**
- `$FEATURE_ID` — unique feature identifier
- `$EXECUTION_MODE` — `"assisted"` | `"self-service"` (default: `"assisted"`)

## Setup

### `install` — Machine-level, run once

```bash
REPO="lulufoo/lulu-dev-skills"; REF="main"
gh api "repos/$REPO/contents/lulu-dev-workflow/scripts/install.py?ref=$REF" \
  --jq '.content' | base64 -d | python3 - --platform $PLATFORM
```

### `init` — Project-level, run once per project

> Prerequisite: `install` has been run.

```bash
python3 "$SKILL_ROOT/scripts/init.py" --project-root "$(pwd)" --platform $PLATFORM
```

Creates `$WORKFLOW_DIR/workflow-config.json` and registers all sub-workflow hooks.

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
  > "$WORKFLOW_DIR/workflow-config.json"
```

After download, read and display the new config file to confirm.

**Default template URL** (lulufoo standard config):
```
https://github.com/lulufoo/ai-software-dev/blob/main/lulu-dev-workflow-template/workflow-config.json
```

### `workflow start [name]` — Create a new feature

Creates a new feature and prints the `feature_id`:

```bash
python3 $SKILL_ROOT/scripts/feature_init.py \
  --project-root "$(pwd)" --name "[name]"
```

Prints the `feature_id` (format: `YYYYMMDDHHMMSS-xxxxxxxx`). After running, append `LULU-DEV-WORKFLOW: <feature_id>` to this response.

### `archive [N]` — Prune old features, keep N most recent

Usage: `lulu-dev-workflow archive [N]` (default N=5)

Keeps the N most recent features (by creation timestamp in `feature_id`) in `$CACHE_DIR`. Deletes older feature directories and removes their entries from `features.json`.

```bash
python3 $SKILL_ROOT/scripts/prune_features.py \
  --project-root "$(pwd)" \
  --keep N
```

Prints a summary of deleted directories and retained features.

## Feature Tracking Convention

Every workflow AI response must end with:

```
LULU-DEV-WORKFLOW: <feature_id>
```

This line tracks the active feature per conversation window. Stage workflows use the latest such line as the fast path to identify `feature_id`. When no such line exists in the conversation, the slow path (interactive selection) is triggered instead.

## Usage

Each stage has its own `SKILL.md` with start commands.

| Abbreviation | Stage |
|---|---|
| `d` | diagnostic |
| `p` | product |
| `t` | tech |
| `w` | work-order |
| `c` | code |

When user passes a single letter, map it to the full stage name before routing.

- **Decision diagnostic:** [diagnostic/SKILL.md](./diagnostic/SKILL.md)
- **Product doc:** [product/SKILL.md](./product/SKILL.md)
- **Tech design:** [tech/SKILL.md](./tech/SKILL.md)
- **Work order:** [work-order/SKILL.md](./work-order/SKILL.md)
- **Code:** [code/SKILL.md](./code/SKILL.md)
