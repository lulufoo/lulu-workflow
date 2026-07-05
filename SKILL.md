---
name: lulu-dev-workflow
description: >-
  Top-level development workflow framework. Use when mentioning lulu-dev-workflow,
  开发工作流, dev workflow, product doc workflow, 产品文档流程, or any sub-stage
  (lulu-bet, lulu-approach, lulu-spec, lulu-blueprint, lulu-arch, lulu-design, lulu-plan, lulu-tasks, lulu-code).
disable-model-invocation: true
argument-hint: "[pd=lulu-bet | td=lulu-approach | ps=lulu-spec | pa=lulu-blueprint | ta=lulu-arch | ds=lulu-design | t=lulu-plan | w=lulu-tasks | c=lulu-code]"
---

# lulu-dev-workflow

A staged development workflow framework. Each stage is an independent sub-module
under this directory.

> **Runtime modules** (loaded by sub-skills, not this file):
> - `_runtime.md` — Script Macros + Platform / Session / Execution Mode (all sub-skills)
> - `_slowpath.md` — Feature Resolution Slow Path (loaded on demand)
> - `_transitions.md` — Stage Transitions + Rollback (loaded at delivery)
> - `_subagent.md` — Sub-agent Context (lulu-code, lulu-tasks only)

## Scope

This SKILL orchestrates **project-level lifecycle** only:

- Bootstrap: install hooks, workflow-config
- Maintenance: optional cycle ops via `$CYCLE_CONTROL` (`cycle_control.py --help`)
- Routing: dispatch to sub-SKILLs (see ## Sub-SKILL Routing)

Cycle creation and selection run in sub-SKILLs via `_runtime.md` § Session Foundation → `_slowpath.md`.

Do **not** drive drafting, evaluating, or delivery here — sub-SKILLs own those steps.
Do **not** call `cycle_schema.py` or bare `python3 .../cycle_control.py` paths — use `$CYCLE_CONTROL` only.

## Stage lines

Work is bound to a **cycle** with `$CYCLE_TYPE` = `topic` or `feature` (see `_runtime.md` § Session Foundation → `_slowpath.md`).

| Line | Purpose | Typical path |
|------|---------|--------------|
| **topic** | Shaping — product/tech architecture exploration before committing to a feature | `lulu-bet` → `lulu-blueprint` → `lulu-approach` → `lulu-arch` |
| **feature** | Delivery — spec through implementation for one feature | `lulu-bet` → `lulu-spec` → `lulu-approach` → `lulu-design` → `lulu-plan` → `lulu-tasks` → `lulu-code` |

**Shared decision stages:** `lulu-bet` (product) and `lulu-approach` (tech) appear on both lines. After each decision, `$CYCLE_TYPE` determines the next stage — e.g. `lulu-spec` (feature) vs `lulu-blueprint` (topic).

**Branching (feature only):** after `lulu-approach`, next stage may be `lulu-design` or `lulu-plan` directly.

**Topic completion:** when `lulu-arch` delivers, the shaping loop ends; create a **feature** cycle referencing this topic to continue into delivery.

**SSOT:** allowed transitions and completion notes — `config/transition-table.json`. Runtime presentation rules — `_transitions.md`.

## Prerequisites

| Layer | Requirement |
|-------|-------------|
| Machine | [`lulu-meta-skill install`](../lulu-meta-skill/install/SKILL.md) (once per machine) |
| Runtime | Read `_runtime.md` § Script Macros + § Platform Context when platform vars are needed |
| Platform vars | `$PLATFORM`, `$SKILL_ROOT`, `$CACHE_DIR`, `$WORKFLOW_DIR` |
| Session | Read `_runtime.md` § Session Foundation when session variables are needed |
| Session vars | `$CYCLE_ID`, `$CYCLE_TYPE`, `$EXECUTION_MODE` |
| Project config | Workflow config at resolved `workflowConfig` root (see ## Command Semantics → configure); `workflow-guard-config.json` at resolved `hookConfig` path (created by init if missing) |

## Command Flow

### Bootstrap — first time in a repo

1. **Machine install** — `lulu-meta-skill install`
2. **Project init** — `$CYCLE_CONTROL init-project` (once per repo; safe to re-run)
3. **Workflow config** — skip if workflow config is already present at resolved root; else `$CYCLE_CONTROL configure`
4. **First work** — Enter any sub-SKILL (e.g. `/lulu-approach`). Cycle binding via `_runtime.md` § Session Foundation.

## Commands

> Invoke via `$CYCLE_CONTROL` only. Subcommand contracts: `cycle_control.py` module docstring or `--help`.
> `start` is invoked from `_slowpath.md` only (not from this orchestrator).

### `init` — Once per project

**When:** Repo has no platform hooks / first lulu-dev-workflow use.

**Run:** `$CYCLE_CONTROL init-project`

**Done:** Report success or stderr; creates `workflow-guard-config.json` at resolved `hookConfig` path if missing; does **not** create workflow config (use `configure`).

### `configure` — When workflow-config is missing

**When:** Workflow config is not present at resolved root (see ## Command Semantics → configure).

**Run:** `$CYCLE_CONTROL configure` [`--url "<blob-url>"`]

**Done:** stdout = absolute path written; announce path to user.

### `archive [N]` — Prune old cycles

**When:** User asks to clean up old features (default keep 5).

**Run:** `$CYCLE_CONTROL archive` [`--keep N`]

**Done:** Summarize deleted vs retained (stdout).

## Command Semantics

### configure

- **Target:** `workflowConfig` in platform config (default `skill-config/lulu-dev-workflow/`).
- **Success stdout:** absolute path of config root written (`manifest.json` + `stages/`).
- **Anti-pattern:** Do not write workflow config under `$WORKFLOW_DIR/` unless `workflowConfig` points there.
- **Inspect only:** `$CYCLE_CONTROL resolve-config-path` (no download).

### archive

- **Retention rule:** Keep N most recent by timestamp embedded in `cycle_id` (default N=5).
- **Side effects:** Deletes dirs under `$CACHE_DIR`; updates `cycles.json`.

### init

- **Creates:** platform `config.json` pointer(s) if missing; **`workflow-guard-config.json`** at resolved `hookConfig` path if missing (from skill default template; does not overwrite existing file).
- **Does not:** create workflow config (use `configure`).
- **Safe:** re-run allowed (idempotent hooks registration and workflow-guard-config bootstrap).

## Script Macros

Macro expansion: `_runtime.md` § Script Macros → Macro expansion.

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
| `lulu-bet` / `pd` | Product decision | Read [lulu-bet/SKILL.md](./lulu-bet/SKILL.md) |
| `lulu-blueprint` / `pa` | Product arch (topic) | Read [lulu-blueprint/SKILL.md](./lulu-blueprint/SKILL.md) |
| `lulu-spec` / `ps` | Product spec (feature) | Read [lulu-spec/SKILL.md](./lulu-spec/SKILL.md) |
| `lulu-approach` / `td` | Tech decision | Read [lulu-approach/SKILL.md](./lulu-approach/SKILL.md) |
| `lulu-arch` / `ta` | Tech arch (topic) | Read [lulu-arch/SKILL.md](./lulu-arch/SKILL.md) |
| `lulu-design` / `ds` | Tech design | Read [lulu-design/SKILL.md](./lulu-design/SKILL.md) |
| `lulu-plan` / `t` | Tech plan | Read [lulu-plan/SKILL.md](./lulu-plan/SKILL.md) |
| `lulu-tasks` / `w` | Tech work order | Read [lulu-tasks/SKILL.md](./lulu-tasks/SKILL.md) |
| `lulu-code` / `c` | Tech code | Read [lulu-code/SKILL.md](./lulu-code/SKILL.md) |
