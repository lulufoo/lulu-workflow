---
name: prober-runner
description: >-
  Round Iteration prober for tech-plan drafting. Dynamically splits each section
  into sub-sections, assesses current L{x} per sub-section using C2 Diagnostic
  Criteria, identifies the L{x+1} gap from C2 Matrix Content Form, merges
  Anchor Ledger checks, and outputs a GapReport. Invoked by tech-plan/SKILL.md
  Step 2 per round.
---

# prober-runner

**Pipeline:** Load context → Diagnose sections → Merge anchors → Deliver GapReport → Return.

One invocation = one probe round. Read-only on tech-doc.

## Scope

**In scope**

- Load `$CTX`, C2 Diagnostic Criteria, C2 Matrix Content Form, and plan role constraints
- Per section: split into sub-sections, assess L{x}, identify L{x+1} gap
- Merge Anchor Ledger; surface new anchor candidates
- Output pinned GapReport for human decide

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

Subcommands and stdout contracts: script module docstring or `--help`.

| Step | Macro calls |
|------|-------------|
| 1 | `$ROUND_CONTROL read-context` · `$RESOLVE_PLAN_ROLE` · `$FETCH_TECH_PLAN layer-diagnostic` · `$FETCH_TECH_PLAN layer-standards` |
| 3 | `$ROUND_CONTROL update-anchor-status --id {anchor_id} --status {passing\|failing}` |

## Execution Contract

### Step 1 — Load context

1. `$ROUND_CONTROL read-context` → parse stdout as `$CTX` (contains anchors and skips)
2. `$RESOLVE_PLAN_ROLE` → apply Plan Scope Constraints
3. `$FETCH_TECH_PLAN layer-diagnostic` → load `## C2 Diagnostic Criteria` (used to assess current L{x})
4. `$FETCH_TECH_PLAN layer-standards` → load `## C2 Matrix — Content Standards` (used to identify L{x+1} gap)

**Done when:** `$CTX`, role constraints, Diagnostic Criteria, and Content Standards are all loaded.

### Step 2 — Diagnose sections

Read `TECH_DOC_PATH`. For each section in document order:

#### Per-section algorithm

1. Read the full section body.
2. Split the section into sub-sections — semantic units of intent (e.g. individual bullet items, decision entries, phase descriptions). Each sub-section is one coherent statement of intent.
3. For each sub-section:
   - Skip if `(section, sub-section)` ∈ `$CTX.skips`
   - Assess current L{x}: apply C2 Diagnostic Criteria for this section type; find the highest L whose criteria are fully met by this sub-section's content
   - Identify L{x+1} gap: read the Content Form for L{x+1} in C2 Matrix; the gap is the constraint dimension present in L{x+1} Content Form that is absent from the current sub-section
   - If the sub-section already satisfies the maximum defined L, record no gap
4. Collect all gaps for this section. Sort by L{x} ascending (lowest L first — weakest constraint is highest priority).

### Step 3 — Anchor Ledger merge

Runs **after** Step 2. Re-check every committed anchor against current tech-doc content.

For each anchor in `$CTX.anchors`:

- Re-check **fails** → override the relevant section's result with the anchor failure; run `$ROUND_CONTROL update-anchor-status --id {anchor_id} --status failing`
- Re-check **passes** and status was `failing` → `$ROUND_CONTROL update-anchor-status --id {anchor_id} --status passing`

Collect new anchor candidates (not yet committed) as `anchorCandidates` for human commit.

### Step 4 — Deliver GapReport

1. Pin report at conversation top (keep visible entire round)
2. Fill template below; omit gap-free sections entirely
3. Return completion summary

**Template**

```markdown
## GapReport — Round {ROUND_N}

### {Section Name}
- [L{x}→L{x+1}] {brief description of sub-section intent}
  Gap: {what L{x+1} requires that is currently absent}
- [L{x}→L{x+1}] {brief description of sub-section intent}
  Gap: {what L{x+1} requires that is currently absent}

### {Section Name}
- [L{x}→L{x+1}] {brief description of sub-section intent}
  Gap: {what L{x+1} requires that is currently absent}

Anchor failures: [{anchor id: description, ...}]
Anchor candidates: [{scenario, ...}]

Summary: {X} gaps across {Y} sections.
```

**Return**

```text
GapReport complete — Round {ROUND_N}.
  Gaps: {total count across all sections}
  Anchor failures: {count}
  Next: await human decide (accept / reject / redirect / commit-anchor / stop)
```
