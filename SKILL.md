---
name: lulu-workflow
description: >-
  Top-level development workflow framework. Use when mentioning lulu-workflow,
  开发工作流, dev workflow, product doc workflow, 产品文档流程, lulu-brainstorm, or any sub-stage
  (lulu-bet, lulu-approach, lulu-spec, lulu-blueprint, lulu-arch, lulu-design, lulu-plan, lulu-tasks, lulu-exec).
disable-model-invocation: true
argument-hint: "[lulu-brainstorm | pd=lulu-bet | td=lulu-approach | ps=lulu-spec | pa=lulu-blueprint | ta=lulu-arch | ds=lulu-design | t=lulu-plan | w=lulu-tasks | c=lulu-exec]"
---

# lulu-workflow

Routes project-level work into a stage skill. Done when `init` has reported, or the matching sub-SKILL is loaded.

> **Runtime modules** (loaded by sub-skills, not this file):
> - `_runtime.md` — Script Macros + Platform / Session / Execution Mode (all sub-skills)
> - `_slowpath.md` — Feature Resolution Slow Path (loaded on demand)
> - `_transitions.md` — Stage Transitions + Rollback (loaded at delivery)
> - `_subagent.md` — Sub-agent Context (lulu-exec, lulu-tasks, decision)

## Stage lines

Both lines start at `lulu-brainstorm`. The product track and the architecture track sit side by side. `$CYCLE_TYPE` is `topic` or `feature`.

| Line | Purpose | Shape |
|------|---------|-------|
| **topic** | Shape product and architecture | `lulu-brainstorm` forks to `lulu-bet` → `lulu-blueprint` and `lulu-approach` → `lulu-arch` |
| **feature** | Carry a feature through to code | `lulu-brainstorm` forks to `lulu-bet` → `lulu-spec` and `lulu-approach` → `lulu-design`; both join `lulu-plan` → `lulu-tasks` → `lulu-exec` |

1. `lulu-bet` and `lulu-approach` appear on both lines.
2. On `feature`, the two tracks join at `lulu-plan`.
3. On `feature`, `lulu-approach` may also go straight to `lulu-tasks` when no plan is needed.

## Routing

Load one sub-SKILL after `$CYCLE_ID` is confirmed.

| Key | Sub-SKILL | Action |
|---|---|---|
| `lulu-brainstorm` | Divergence before a problem is defined | Read [lulu-brainstorm/SKILL.md](./lulu-brainstorm/SKILL.md) |
| `lulu-bet` / `pd` | Product decision | Read [lulu-bet/SKILL.md](./lulu-bet/SKILL.md) |
| `lulu-blueprint` / `pa` | Product arch (topic) | Read [lulu-blueprint/SKILL.md](./lulu-blueprint/SKILL.md) |
| `lulu-spec` / `ps` | Product spec (feature) | Read [lulu-spec/SKILL.md](./lulu-spec/SKILL.md) |
| `lulu-approach` / `td` | Tech decision | Read [lulu-approach/SKILL.md](./lulu-approach/SKILL.md) |
| `lulu-arch` / `ta` | Tech arch (topic) | Read [lulu-arch/SKILL.md](./lulu-arch/SKILL.md) |
| `lulu-design` / `ds` | Tech design | Read [lulu-design/SKILL.md](./lulu-design/SKILL.md) |
| `lulu-plan` / `t` | Tech plan | Read [lulu-plan/SKILL.md](./lulu-plan/SKILL.md) |
| `lulu-tasks` / `w` | Tech work order | Read [lulu-tasks/SKILL.md](./lulu-tasks/SKILL.md) |
| `lulu-exec` / `c` | Task exec | Read [lulu-exec/SKILL.md](./lulu-exec/SKILL.md) |

1. The sub-SKILL owns drafting, evaluation, and delivery.

## Bootstrap

First use in a repo. Read `_runtime.md` § Script Macros and § Platform Context before the command.

1. **When** — the repo has no platform hooks, or this is the first run.
2. **Run** — `$CYCLE_CONTROL init-project`
3. **Done** — report success or stderr. Re-run is safe.
4. **Next** — enter a sub-SKILL. Cycle binding is `_runtime.md` § Session Foundation.

## Script Macros

`$CYCLE_CONTROL` is defined in `_runtime.md` § Script Macros. This file invokes `init-project` only.

1. `start`, `menu`, and `resolve-token` run from `_slowpath.md`.
2. `bind-context` runs from `_runtime.md` § Session Foundation after `$CYCLE_ID` is confirmed.
3. Subcommands and stdout: `cycle_control.py` module docstring or `--help`.
4. Non-zero exit → stop and report stderr.
5. Call `$CYCLE_CONTROL` only. A bare `python3` path or `cycle_schema.py` is outside this file.
