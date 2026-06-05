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

## Stage Transitions

When a stage delivers:
1. Read `$SKILL_ROOT/config/transition-table.json`
2. Collect all entries where `from == <current_stage>` (`null` if no active stage) under the `cycle_type` key (`topic` or `feature`); aggregate their `to` arrays
3. Present all allowed next stages from the `to` array; wait for explicit user selection (see § Autonomous Tech Line Auto-Chain for the exception)
4. If `to` is empty: announce completion; display the `note` field if present

> Any transition not listed in `transition-table.json` is **prohibited**.

### § Autonomous Tech Line Auto-Chain

**Trigger conditions:** `$EXECUTION_MODE == "autonomous"` AND `cycle_type == "feature"`

**Auto-chain whitelist** (on delivery, immediately start the next stage without user selection):
`tech-plan` → `tech-work-order` → `tech-code`

Does **not** trigger for **Guided mode**.

Each stage's autonomous overrides govern how delivery and handoff are executed. See `Autonomous Overrides` sections in `tech-plan/SKILL.md`, `tech-work-order/SKILL.md`, and `tech-code/SKILL.md`.

---

### Stage Rollback

Any participant may trigger a Stage Rollback when new information shows a prior stage's output is no longer valid:

- **Trigger:** state the target stage to roll back to (any prior stage, any number of levels back)
- **Effect on Product Line:** rolling back to `product-diagnostic` invalidates `product-plan` + entire tech line; rolling back to `product-plan` invalidates entire tech line.
- **Effect on Tech Line:** rolling back to `tech-diagnostic` invalidates `tech-plan`, `tech-work-order`, `tech-code`.
- **AI must announce:** "[target stage] and all downstream stages are invalidated. Restarting from [target stage]."

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

**Output variables:** `$CYCLE_ID` · `$EXECUTION_MODE` (`"guided"` | `"autonomous"`)

### Execution Mode

Defines how AI and user share control throughout the workflow.

| Mode | Value | AI Behavior | User Role |
|------|-------|-------------|-----------|
| Guided | `"guided"` | AI leads: proactively advances, asks, recommends; waits at key gates | Approver |
| Autonomous | `"autonomous"` | AI executes on instruction only; does not advance or suggest unprompted; includes Tech Line auto-chain for feature cycles | Commander |

`$EXECUTION_MODE` is set during Feature Resolution and applies to all subsequent stages.

#### Initial Mode Resolution

1. `cycle_id` not in `cycles.json` → `"guided"`
2. Value is an object → use `object.execution_mode`

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
   Cycles:
   [topic]   1. <name> [guided]
   [feature] 2. <name> [autonomous]
   …
   N. New topic — type a description to create
   M. New feature — type a description to create
   ```

   Ask both in one message:
   > `Cycle: enter number to select, or type a description to create [default: "<name>"]`  
   > `Execution mode: (1) guided [default]  (2) autonomous`

   *(Show `[default: "<name>"]` only when a name was derived from the triggering message.)*

2. Parse response — both questions answered in one reply; any unanswered → default:
   - **Feature:** integer → `cycle_id ← cycles.json[n]`; run Initial Mode Resolution → **DONE**; text → `name ← input`; no answer → use derived `<name>` if available
   - **Mode:** `2` → `autonomous`; anything else / no answer → `guided`

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
- Merge rule: `subagents.default` merged with `subagents.<stage>`; stage wins on conflict.
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

Run `lulu-dev-workflow configure <github-blob-url>` to apply workflow config. See `configure` below.

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
https://github.com/lulufoo/ai-software-dev/blob/main/lulu-dev-workflow-template/workflow-config.json
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


