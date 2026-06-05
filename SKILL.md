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

## Stages

| Stage | Module | Status |
|-------|--------|--------|
| Product diagnostic | `product-diagnostic/` | Active |
| Tech diagnostic | `tech-diagnostic/` | Active |
| Generic diagnostic | `diagnostic/` | Active |
| Product plan | `product-plan/` | Active |
| Tech plan | `tech-plan/` | Active |
| Tech work order | `tech-work-order/` | Active |
| Tech code | `tech-code/` | Active |

> **product-diagnostic** is the recommended entry point for full-feature work (produces product-scoped decision-doc).
> **tech-diagnostic** is the entry point for pure tech work (produces tech-scoped decision-doc).
> **diagnostic** runs without domain constraints (standalone use).

## Utilities

Cross-cutting tools that may be invoked from any stage. Not part of the Stage Transitions pipeline.

| Utility | Module | When to use |
|---------|--------|-------------|
| Research synthesis | `research-synthesis/` | External evidence synthesis; before `diagnostic` for landscape research, or during `diagnostic` R/V gates to assess assumptions that require external evidence |

## Stage Transitions

When a stage delivers:
1. Read `$SKILL_ROOT/config/transition-table.json`
2. Look up the entry where `from == <current_stage>` under the `cycle_type` key (`topic` or `feature`)
3. List allowed next stages from the `to` array, recommend one, wait for explicit user selection (see § Autonomous Tech Line Auto-Chain for the exception)
4. If `to` is empty: announce completion; display the `note` field if present

> `tech-plan` → `tech-code` is **prohibited** — bypasses task breakdown and TDD-first discipline in `tech-work-order`.

**Starting rules:**
- `product-diagnostic` is the recommended entry for full-feature work (product decision → product-plan → tech line).
- `tech-diagnostic` is the direct entry for pure tech work (no product phase needed).

### § Autonomous Tech Line Auto-Chain

**Trigger conditions:** `$EXECUTION_MODE == "autonomous"` AND `cycle_type == "feature"`

Does **not** trigger for:
- Copilot mode (any container type)
- Topic containers (`cycle_type == "topic"`) — topic containers have no tech-work-order or tech-code stages

When triggered, stage handoff in the Tech Line is automatic — no user selection required:

| Delivered Stage | Next Auto Action |
|---|---|
| `tech-plan` | Auto start `tech-work-order` |
| `tech-work-order` | Auto start `tech-code` |
| `tech-code` | Done — no further auto action |

Each stage's autonomous overrides govern how delivery and handoff are executed. See `Autonomous Overrides` sections in `tech-plan/SKILL.md`, `tech-work-order/SKILL.md`, and `tech-code/SKILL.md`.

---

### Stage Rollback

Any participant may trigger a Stage Rollback when new information shows a prior stage's output is no longer valid:

- **Trigger:** state the target stage to roll back to (any prior stage, any number of levels back)
- **Effect on Product Line:** rolling back to `product-diagnostic` invalidates `product-plan` + entire tech line; rolling back to `product-plan` invalidates entire tech line.
- **Effect on Tech Line:** rolling back to `tech-diagnostic` invalidates `tech-plan`, `tech-work-order`, `tech-code`.
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

## Session Foundation

### Active Context

`active-context.json` is indexed by Cursor/Copilot `conversation_id`:

```json
{ "<conversation_id>": { "cycle_id": "...", "stage": "tech-plan", "cycle_type": "feature" } }
```

- `cycle_type`: `"topic"` | `"feature"` — backward compat: absent field is treated as `"feature"`
- Re-starting a different feature in the **same** conversation overwrites that conv entry (one active workflow per conversation)

**Output variables:** `$CYCLE_ID` · `$EXECUTION_MODE` (`"copilot"` | `"autonomous"`)

### Execution Mode

Defines how AI and user share control throughout the workflow.

| Mode | Value | AI Behavior | User Role |
|------|-------|-------------|-----------|
| Copilot | `"copilot"` | AI leads: proactively advances, asks, recommends; waits at key gates | Approver |
| Autonomous | `"autonomous"` | AI executes on instruction only; does not advance or suggest unprompted; includes Tech Line auto-chain for feature containers | Commander |

`$EXECUTION_MODE` is set during Feature Resolution and applies to all subsequent stages.

#### Initial Mode Resolution

1. `cycle_id` not in `cycles.json` → `"copilot"`
   - both topic-id and cycle-id are resolved from `cycles.json`
2. Value is a string (legacy) → `"copilot"` (backward-compat: `"assisted"` → `"copilot"`; `"self-service"` → `"autonomous"`)
3. Value is an object → use `object.execution_mode`

#### Runtime Switch

The user may switch mode at any point by entering:

```
SET_EXECUTION_MODE: <mode>
```

On detection: `$EXECUTION_MODE ← <mode>`, effective immediately for all remaining stages.
Announce: `Execution mode → <mode>`

Sub-SKILLs do not emit this command directly. They may prompt the user that switching is available.

### Feature Resolution

Run at session start for every sub-workflow.

#### Fast Path

1. Find the latest `LULU-DEV-WORKFLOW: <id>` line in this conversation *(skip conversation-summary blocks)*
2. If found **and** no ambiguity signal → run Initial Mode Resolution for `cycle_id` → **DONE**

> **Ambiguity signals:** no footer · user mentions a different feature · user says "switch" / "new" / "choose"

#### Slow Path

1. Read `$CACHE_DIR/cycles.json` → display list. If the triggering message contains a description, derive a suggested name `<name>`.

   ```
   Containers:
   [topic]   1. <name> [copilot]
   [feature] 2. <name> [autonomous]
   …
   N. New topic — type a description to create
   M. New feature — type a description to create
   ```

   Ask both in one message:
   > `Container: enter number to select, or type a description to create [default: "<name>"]`  
   > `Execution mode: (1) copilot [default]  (2) autonomous`

   *(Show `[default: "<name>"]` only when a name was derived from the triggering message.)*

2. Parse response — both questions answered in one reply; any unanswered → default:
   - **Feature:** integer → `cycle_id ← cycles.json[n]`; run Initial Mode Resolution → **DONE**; text → `name ← input`; no answer → use derived `<name>` if available
   - **Mode:** `2` → `autonomous`; anything else / no answer → `copilot`

3. If a new name is resolved, run:
   ```bash
   python3 cycle_init.py --project-root "$(pwd)" --name "<name>" --mode "<mode>"
   ```
   `$EXECUTION_MODE ← mode`

#### Done

- `$CYCLE_ID` confirmed
- Append `LULU-DEV-WORKFLOW: <cycle_id>` to every workflow response
- Read workflow docs only from `$CACHE_DIR/$CYCLE_ID/`

### Feature Tracking Convention

Every workflow AI response must end with:

```
LULU-DEV-WORKFLOW: <cycle_id>
```


This line tracks the active cycle per conversation window. Stage workflows use the latest such line as the fast path to identify `cycle_id`. When no such line exists in the conversation, the slow path (interactive selection) is triggered instead.

## Sub-agent Context

| Variable | copilot | cursor | claude | codex |
|----------|---------|--------|--------|-------|
| `$SUBAGENT_TOOL` | TBD | `Task` tool | TBD | TBD |
| `$SUBAGENT_AWAIT_SYNC` | TBD | `run_in_background: false`; block until return | TBD | TBD |
| `$SUBAGENT_AWAIT_ASYNC` | TBD | `run_in_background: true`; await completion notification | TBD | TBD |

### Usage

- **Dispatch** — Invoke `$SUBAGENT_TOOL` with a prompt that loads the target sub-SKILL and the input contract for that agent.
- **Serial** — Single agent: dispatch with `$SUBAGENT_AWAIT_SYNC`; block until return.
- **Parallel** — N agents in one message: each with `$SUBAGENT_AWAIT_ASYNC`; wait for all completion notifications before proceeding.

### Config Resolution

Before dispatching a sub-agent for a workflow stage, resolve the optional model slug from platform config:

```bash
python3 "$SKILL_ROOT/scripts/resolve_subagent.py" --project-root "$(pwd)" --stage <stage>
```

- stdout is JSON: `{"model": "<slug>"}` when configured, or `{}` when absent or empty.
- **Output variable `$RESOLVED_MODEL`:** non-empty `"model"` → `$RESOLVED_MODEL = <slug>`; absent or empty → `$RESOLVED_MODEL` = (omit — platform default applies).
- Pass `$RESOLVED_MODEL` as the `model` parameter to `$SUBAGENT_TOOL` when set; omit the parameter otherwise.
- Merge rule (implementation SSOT: `scripts/subagent_config.py`): `subagents.default` merged with `subagents.<stage>`; stage wins on conflict.
- Invalid model slugs are the user's responsibility; the Task tool may error at runtime.
- Resolve once per stage entry (not once per sub-agent dispatch); `$RESOLVED_MODEL` is stage-scoped, not session-scoped.

## Commands

### `init` — Project-level, run once per project

> Prerequisite: machine-level install via `lulu-meta-skill install`.

```bash
python3 "$SKILL_ROOT/scripts/init.py" --project-root "$(pwd)" --platform $PLATFORM
```

Creates `$WORKFLOW_DIR/workflow-config.json` and registers all sub-workflow hooks.

`$WORKFLOW_DIR/config.json` (platform config) fields:

| Field | Description |
|-------|-------------|
| `workflowConfig` | Path to shared `workflow-config.json` (relative to project root) |
| `subagents.<stage>.model` | Optional model slug for sub-agent dispatch (e.g. `subagents.tech-code.model`) |
| `subagents.default.model` | Optional fallback model; overridden by stage-specific `model` (user-added; init does not prefill) |

`workflow-config.json` contains the following fields:

| Field | Description |
|-------|-------------|
| `product-plan.template_url` | 产品文档模板 |
| `product-plan.review_checklist_url` | 进入评估前审查清单 |
| `product-plan.pdqa_url` | PDQA 评估框架 |
| `tech-plan.tpt_url` | 技术方案模板（Tech Plan Template） |
| `tech-plan.tpef_url` | 技术方案评估框架（Tech Plan Evaluation Framework） |
| `tech-plan.ptc_url` | 产品-技术交叉检查（Product-Tech Crosscheck） |
| `tech-plan.ac_url` | 架构约束文档（如有） |
| `tech-work-order.task_template_url` | 单个施工单模板 |
| `tech-work-order.tasklist_template_url` | 施工单列表模板 |
| `tech-work-order.twca_url` | TWCA 评审框架 |
| `tech-work-order.woqa_url` | WOQA 质量评审框架 |
| `tech-code.test_command` | 项目测试命令（默认: `npm test`） |
| `tech-code.woqa_url` | TDD 质量审计框架 |

Run `lulu-dev-workflow configure <github-blob-url>` to apply a config. See `configure` below.

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

### `start [name]` — Create a new feature

Creates a new feature and prints the `cycle_id`:

```bash
python3 $SKILL_ROOT/scripts/cycle_init.py \
  --project-root "$(pwd)" --name "[name]"
```

Prints the `cycle_id` (format: `YYYYMMDDHHMMSS-xxxxxxxx`). After running, append `LULU-DEV-WORKFLOW: <cycle_id>` to this response.

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

After routing to a sub-SKILL, follow the workflow defined in that sub-SKILL's SKILL.md.
