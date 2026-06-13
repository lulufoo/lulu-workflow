---
name: prober-runner
description: >-
  Round Iteration prober for tech-plan drafting. Runs P1–P4 verification probes
  per section, merges Anchor Ledger checks, and outputs a pinned ProbeReport.
  Invoked by tech-plan/SKILL.md Step 2 per round.
---

# prober-runner

**Pipeline:** Load context → Probe five sections → Merge anchors → Deliver ProbeReport → Return.

One invocation = one probe round. Read-only on tech-doc and drafting-progress.

## Scope

**In scope**

- Load `$CTX`, C2 criteria, and plan role constraints
- Run P1–P4 per section; merge anchor ledger
- Output pinned ProbeReport for human decide

**Out of scope**

- Do not write `tech-doc.md`
- Do not advance `drafting-progress`
- Do not dispatch refiner or ask human questions mid-run

## Blocking policy

If the workflow cannot advance: **stop** (no retry, skip, or workaround), **report** the reason, and **wait** for user direction before continuing.

Any `$ROUND_CONTROL` non-zero exit → stop and report stderr.

## Parent-Provided Inputs

| Variable | Purpose |
|----------|---------|
| `CYCLE_DIR` | Cycle cache dir (`$CACHE_DIR/<cycle_id>`); used by `$ROUND_CONTROL` |
| `CYCLE_ID` | Cycle id; used by `$RESOLVE_PLAN_ROLE` |
| `ROUND_N` | Current round (integer ≥ 1) |
| `TECH_DOC_PATH` | Active `revision{N}/tech-doc.md` (read-only) |

Self-resolved at runtime:

- `$SKILL_DIR` = `$SKILL_ROOT/tech-plan`

## Command Index

Macros invoke `$SKILL_DIR/scripts/*.py`. Non-zero exit → Blocking policy.

| Macro | Command |
|-------|---------|
| `$ROUND_CONTROL` | `python3 "$SKILL_DIR/scripts/round_control.py" --cycle-dir "$CYCLE_DIR" <subcommand> [args...]` |
| `$RESOLVE_PLAN_ROLE` | `python3 "$SKILL_DIR/scripts/plan_scope.py" resolve-role --cycle-id "$CYCLE_ID" --project-root "$(pwd)"` |
| `$FETCH_TECH_PLAN` | `python3 "$SKILL_DIR/scripts/fetch_plan_framework.py" --role <role> --project-root "$(pwd)"` |

Shorthand: `$FETCH_TECH_PLAN layer-diagnostic` → `--role layer-diagnostic`.

Subcommands and stdout contracts: script module docstring or `--help`.

| Step | Macro calls |
|------|-------------|
| 1 | `$ROUND_CONTROL read-context` · `$RESOLVE_PLAN_ROLE` · `$FETCH_TECH_PLAN layer-diagnostic` |
| 3 | `$ROUND_CONTROL update-anchor-status --id {anchor_id} --status {passing\|failing}` |

## Execution Contract

### Step 1 — Load context

**Run**

1. `$ROUND_CONTROL read-context` → parse stdout as `$CTX`
2. `$RESOLVE_PLAN_ROLE` → apply Plan Scope Constraints
3. `$FETCH_TECH_PLAN layer-diagnostic` → locate `## C2 Diagnostic Criteria`

**Done when:** `$CTX`, role constraints, and C2 criteria are all loaded.

### Step 2 — Run probes

#### Probe matrix

| Key | Section | Applicable probes |
|-----|---------|-------------------|
| NS | North Star | P1 (restated accurately?) |
| NG | Non-Goals & Invariants | P1 + P2 (semantic consistency + violation enumeration) |
| KD | Key Decisions | P3 (regenerate from NS+NG with KD masked) |
| SK | Approach Skeleton | P4 (boundary cases answerable?) |
| T | Tasks | P4 (escalate to L4 when funds/security involved) |

#### Per-section algorithm

For each section in order NS → NG → KD → SK → T:

1. Skip if `(section, probe)` ∈ `$CTX.skips`
2. Read section body from `TECH_DOC_PATH`
3. Merge `$CTX.anchors` into P2 / P4 inputs
4. Read current L from `$CTX.state_vector[section]`
5. Evaluate against C2 Diagnostic Criterion at that L
6. Record pass (`无问题`) or failure (evidence, zoom, probe id)
7. Keep at most one issue per section (apply arbitration below)

#### Arbitration

One issue per section max:

- Lower current L wins (L0 highest priority)
- Same L: stronger failure evidence wins
- Section tie-break: NS > NG > KD > SK > T

### Step 3 — Anchor ledger merge

Runs **after** Step 2. Re-check every committed anchor against current tech-doc + probe inputs.

For each anchor in `$CTX.anchors`:

- Re-check **fails** → **override** that section's Step 2 result with the anchor failure; run `$ROUND_CONTROL update-anchor-status --id {anchor_id} --status failing`
- Re-check **passes** and status was `failing` → `$ROUND_CONTROL update-anchor-status --id {anchor_id} --status passing`

Collect new anchor candidates (not yet committed) as `anchorCandidates` for human commit.

### Step 4 — Deliver ProbeReport

1. Pin report at conversation top (keep visible entire round)
2. Fill template below; use failure line format when not `无问题`
3. Append `[REQUIRED]` when current L is L0 (must be handled; cannot skip)
4. Return completion summary

**Template**

```markdown
## ProbeReport — Round {ROUND_N}

North Star [L{ns_l}]:              {result or 无问题}
Non-Goals & Invariants [L{ng_l}]:  {result or 无问题}
Key Decisions [L{kd_l}]:           {result or 无问题}
Approach Skeleton [L{sk_l}]:       {result or 无问题}
Tasks [L{t_l}]:                   {result or 无问题}
Anchor Candidates:            [{candidate list or empty}]
```

`{ns_l}` etc. come from `$CTX.state_vector`.

**Line format examples**

```text
Pass:  无问题
Fail:  P2 失败 — NG 与 NS 语义冲突：… → zoom L1→L2
L0:    P1 失败 — … → zoom L0→L1 [REQUIRED]
```

**Return**

```text
ProbeReport complete — Round {ROUND_N}.
  Issues: {count of non-无问题 lines}
  Anchor failures: {count}
  Next: await human decide (accept / reject / redirect / commit-anchor)
```
