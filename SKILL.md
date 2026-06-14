---
name: lulu-dev-workflow
description: >-
  Top-level development workflow framework. Use when mentioning lulu-dev-workflow,
  开发工作流, dev workflow, product doc workflow, 产品文档流程, or any sub-stage
  (product-diagnostic, tech-diagnostic, diagnostic, product-plan, tech-plan, tech-work-order, tech-code).
disable-model-invocation: true
argument-hint: "[d=diagnostic | pd=product-diagnostic | td=tech-diagnostic | p=product-plan | t=tech-plan | w=tech-work-order | c=tech-code]"
---

# lulu-dev-workflow

A staged development workflow framework. Each stage is an independent sub-module
under this directory.

> **Runtime modules** (loaded by sub-skills, not this file):
> - `_runtime.md` — Platform Context + Session Foundation (all sub-skills)
> - `_slowpath.md` — Feature Resolution Slow Path (loaded on demand)
> - `_transitions.md` — Stage Transitions + Rollback (loaded at delivery)
> - `_subagent.md` — Sub-agent Context (tech-code, tech-work-order only)

## Commands

> Commands use `$PLATFORM`, `$SKILL_ROOT`, `$CACHE_DIR`, and `$WORKFLOW_DIR`. Read `_runtime.md` § Platform Context before running any command.

### `init` — Project-level, run once per project

> Prerequisite: machine-level install via [`lulu-meta-skill install`](../lulu-meta-skill/install/SKILL.md).

```bash
python3 "$SKILL_ROOT/scripts/init.py" --project-root "$(pwd)" --platform $PLATFORM
```

Registers platform config and workflow hooks. Does **not** create `workflow-config.json` — use `configure` first (or ensure `skill-config/lulu-dev-workflow/workflow-config.json` exists). Safe to re-run.

Run `configure` before `start` if the project has no workflow-config yet.

### `configure` — Download and apply a workflow-config.json from GitHub

Usage: `lulu-dev-workflow configure <github-blob-url>`

Parse the GitHub blob URL to extract `owner`, `repo`, `ref`, `path`, then run:

```bash
gh api "repos/{owner}/{repo}/contents/{path}?ref={ref}" \
  --jq '.content' | base64 -d \
  > "$WORKFLOW_DIR/workflow-config.json"
```

After download, display the new config. Default (if no URL given):
```
https://github.com/lulufoo/lulu-workflow-framework/blob/main/template/workflow-config.json
```

### `start [name]` — Create a new feature

Creates a new feature and prints the `cycle_id`:

```bash
python3 $SKILL_ROOT/scripts/cycle_init.py \
  --project-root "$(pwd)" --name "[name]"
```

Prints the `cycle_id` (format: `{cycle_type}-YYYYMMDDHHMMSS-xxxxxxxx`). After running, append `LULU-DEV-WORKFLOW: <cycle_id>` to this response.

### `archive [N]` — Prune old features, keep N most recent

Usage: `lulu-dev-workflow archive [N]` (default N=5)

Keeps the N most recent features (by creation timestamp in `cycle_id`) in `$CACHE_DIR`. Deletes older feature directories and removes their entries from `cycles.json`.

```bash
python3 $SKILL_ROOT/scripts/prune_features.py \
  --project-root "$(pwd)" \
  --keep N
```

Prints a summary of deleted directories and retained features.

## Sub-SKILL Routing

| Key | Sub-SKILL | Action |
|---|---|---|
| `product-diagnostic` / `pd` | Product diagnostic | Read [product-diagnostic/SKILL.md](./product-diagnostic/SKILL.md) |
| `tech-diagnostic` / `td` | Tech diagnostic | Read [tech-diagnostic/SKILL.md](./tech-diagnostic/SKILL.md) |
| `diagnostic` / `d` | Generic diagnostic | Read [diagnostic/SKILL.md](./diagnostic/SKILL.md) |
| `product-plan` / `p` | Product plan | Read [product-plan/SKILL.md](./product-plan/SKILL.md) |
| `tech-plan` / `t` | Tech plan | Read [tech-plan/SKILL.md](./tech-plan/SKILL.md) |
| `tech-work-order` / `w` | Tech work order | Read [tech-work-order/SKILL.md](./tech-work-order/SKILL.md) |
| `tech-code` / `c` | Tech code | Read [tech-code/SKILL.md](./tech-code/SKILL.md) |
