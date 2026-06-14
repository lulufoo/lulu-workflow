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
> - `_runtime.md` — Script Macros + Platform / Session / Execution Mode (all sub-skills)
> - `_slowpath.md` — Feature Resolution Slow Path (loaded on demand)
> - `_transitions.md` — Stage Transitions + Rollback (loaded at delivery)
> - `_subagent.md` — Sub-agent Context (tech-code, tech-work-order only)

## Scope

This SKILL orchestrates **project-level lifecycle** only:

- Bootstrap: install hooks, workflow-config
- Maintenance: list / validate / archive cycles
- Routing: dispatch to sub-SKILLs (see ## Sub-SKILL Routing)

Cycle creation and selection run in sub-SKILLs via `_runtime.md` § Session Foundation → `_slowpath.md`.

Do **not** drive drafting, evaluating, or delivery here — sub-SKILLs own those steps.
Do **not** call `cycle_schema.py` or bare `python3 .../cycle_control.py` paths — use `$CYCLE_CONTROL` only.

## Prerequisites

| Layer | Requirement |
|-------|-------------|
| Machine | [`lulu-meta-skill install`](../lulu-meta-skill/install/SKILL.md) (once per machine) |
| Runtime | Read `_runtime.md` § Script Macros + § Platform Context when platform vars are needed |
| Platform vars | `$PLATFORM`, `$SKILL_ROOT`, `$CACHE_DIR`, `$WORKFLOW_DIR` |
| Session | Read `_runtime.md` § Session Foundation when session variables are needed |
| Session vars | `$CYCLE_ID`, `$CYCLE_TYPE`, `$EXECUTION_MODE` |
| Project config | `workflow-config.json` at resolved `workflowConfig` path (see ## Command Semantics → configure) |

## Command Flow

### Bootstrap — first time in a repo

1. **Machine install** — `lulu-meta-skill install`
2. **Project init** — `$CYCLE_CONTROL init-project` (once per repo; safe to re-run)
3. **Workflow config** — skip if config file already exists at resolved path; else `$CYCLE_CONTROL configure`
4. **First work** — Enter any sub-SKILL (e.g. `/tech-diagnostic`). Cycle binding via `_runtime.md` § Session Foundation.

### Maintenance — optional, user-invoked

| Intent | Run |
|--------|-----|
| List cycles | `$CYCLE_CONTROL list` |
| Inspect one cycle | `$CYCLE_CONTROL info --cycle-id "<id>"` |
| Validate cycle on disk | `$CYCLE_CONTROL validate --cycle-id "<id>"` |
| Prune old cycles | `$CYCLE_CONTROL archive` [`--keep N`] |
| Show config path only | `$CYCLE_CONTROL resolve-config-path` |

## Commands

> Invoke via `$CYCLE_CONTROL` only. Subcommand contracts: `cycle_control.py` module docstring or `--help`.
> `start` is invoked from `_slowpath.md` only (not from this orchestrator).

### `init` — Once per project

**When:** Repo has no platform hooks / first lulu-dev-workflow use.

**Run:** `$CYCLE_CONTROL init-project`

**Done:** Report success or stderr; does not create `workflow-config.json`.

### `configure` — When workflow-config is missing

**When:** Resolved config path has no file (see ## Command Semantics → configure).

**Run:** `$CYCLE_CONTROL configure` [`--url "<blob-url>"`]

**Done:** stdout = absolute path written; announce path to user.

### `archive [N]` — Prune old cycles

**When:** User asks to clean up old features (default keep 5).

**Run:** `$CYCLE_CONTROL archive` [`--keep N`]

**Done:** Summarize deleted vs retained (stdout).

## Command Semantics

### configure

- **Target path:** `workflowConfig` in platform config (default `skill-config/lulu-dev-workflow/workflow-config.json`).
- **Success stdout:** absolute path of file written.
- **Anti-pattern:** Do not write to `$WORKFLOW_DIR/workflow-config.json` unless `workflowConfig` points there.
- **Inspect only:** `$CYCLE_CONTROL resolve-config-path` (no download).

### archive

- **Retention rule:** Keep N most recent by timestamp embedded in `cycle_id` (default N=5).
- **Side effects:** Deletes dirs under `$CACHE_DIR`; updates `cycles.json`.

### init

- **Does not:** create `workflow-config.json`.
- **Safe:** re-run allowed (idempotent hooks registration).

## Script Macros

Requires `$SKILL_ROOT` and `$PLATFORM` from `_runtime.md` § Platform Context.

Non-zero exit → stop and report stderr.

| Macro | Command |
|-------|---------|
| `$CYCLE_CONTROL` | `python3 "$SKILL_ROOT/scripts/cycle_control.py" --project-root "$(pwd)" --platform $PLATFORM <subcommand> [args...]` |

Subcommands and stdout: `cycle_control.py` module docstring or `--help`.

## Sub-SKILL Routing

After `$CYCLE_ID` is confirmed, route stage work via sub-SKILLs — do not re-run orchestrator commands unless bootstrap/maintenance.

| Key | Sub-SKILL | Action |
|---|---|---|
| `product-diagnostic` / `pd` | Product diagnostic | Read [product-diagnostic/SKILL.md](./product-diagnostic/SKILL.md) |
| `tech-diagnostic` / `td` | Tech diagnostic | Read [tech-diagnostic/SKILL.md](./tech-diagnostic/SKILL.md) |
| `diagnostic` / `d` | Generic diagnostic | Read [diagnostic/SKILL.md](./diagnostic/SKILL.md) |
| `product-plan` / `p` | Product plan | Read [product-plan/SKILL.md](./product-plan/SKILL.md) |
| `tech-plan` / `t` | Tech plan | Read [tech-plan/SKILL.md](./tech-plan/SKILL.md) |
| `tech-work-order` / `w` | Tech work order | Read [tech-work-order/SKILL.md](./tech-work-order/SKILL.md) |
| `tech-code` / `c` | Tech code | Read [tech-code/SKILL.md](./tech-code/SKILL.md) |
