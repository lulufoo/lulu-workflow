---
name: prober-runner
description: >-
  Round Iteration prober for tech-plan drafting. Runs P1–P4 verification probes
  per section, merges Anchor Ledger checks, and outputs a pinned ProbeReport.
  Invoked by tech-plan/SKILL.md Step 2 per round.
---

# prober-runner

Terminal runner subagent. Executes **one probe round** per invocation.

## Blocking policy

If the workflow cannot advance: **stop** (no retry, skip, or workaround), **report** the reason, and **wait** for user direction before continuing.

Any `$ROUND_CONTROL` non-zero exit → stop and report stderr.

## Parent-Provided Inputs

```
CYCLE_DIR           absolute path to $CACHE_DIR/<cycle_id>
CYCLE_ID            cycle identifier (for $RESOLVE_PLAN_ROLE)
CYCLE_TYPE          topic | feature
ROUND_N             current round number (integer ≥ 1)
TECH_DOC_PATH       absolute path to revision{N}/tech-doc.md
```

Self-resolved at runtime:
- `$SKILL_DIR` = `$SKILL_ROOT/tech-plan`

Script macros: see `../SKILL.md` → **Command Index**.
In this runner, `$ROUND_CONTROL` expands with `--cycle-dir "$CYCLE_DIR"` (equivalent to parent `--cycle-dir "$CACHE_DIR/$CYCLE_ID"`).

## Step 1 — Load context

Run `$ROUND_CONTROL read-context`.
Parse stdout as `$CTX` per `round_control.py` → `read-context` contract.

Load C2 Diagnostic Criteria (see `../SKILL.md` → Command Index):

1. Run `$RESOLVE_PLAN_ROLE` with `CYCLE_ID`; apply Plan Scope Constraints.
2. Use `$FETCH_TECH_PLAN $CYCLE_TYPE layer-diagnostic`; read stdout and locate `## C2 Diagnostic Criteria`.

## Step 2 — Run probes per section

For each of the 5 layers, run applicable probes per C3. **Exclude** any `(section, probe)` pair already present in `$CTX.skips`.

| Section | Key | Applicable probes |
|---|---|---|
| North Star | NS | P1 (restated accurately?) |
| Non-Goals & Invariants | NG | P1 + P2 (semantic consistency + violation enumeration) |
| Key Decisions | KD | P3 (regenerate from NS+NG with KD masked) |
| Approach Skeleton | SK | P4 (boundary cases answerable?) |
| Tasks | T | P4 (escalate to L4 when funds/security involved) |

**Probe execution rules:**

1. Read `TECH_DOC_PATH`; extract each section body.
2. Merge `$CTX.anchors` into P2 and P4 inputs.
3. Evaluate against the C2 Diagnostic Criterion for the section's **current L** from `$CTX.state_vector`.
4. On failure: record evidence text, suggested zoom `(currentL → targetL)`, and triggered probe id.
5. On pass: record "无问题".

**Priority within a round (one issue per layer max):**

- Lower current L wins (L0 highest priority).
- Same L: stronger failure evidence wins.
- Section tie-break order: NS > NG > KD > SK > T.

## Step 3 — Anchor Ledger merge

Re-check every committed anchor against current tech-doc + probe inputs.

For each anchor in `$CTX.anchors`:

- If re-check **fails** → force highest-priority issue for that section; update ledger:
  `$ROUND_CONTROL update-anchor-status --id {anchor_id} --status failing`

- If re-check **passes** → update ledger when status was `failing`:
  `$ROUND_CONTROL update-anchor-status --id {anchor_id} --status passing`

Collect new anchor candidates (not yet committed) as `anchorCandidates` for human commit.

## Step 4 — Output ProbeReport

Pin the report at the top of the conversation. Keep it visible for the entire round.

```
## ProbeReport — Round {ROUND_N}

North Star [L{n}]:              {P1 result or 无问题}
Non-Goals & Invariants [L{n}]:  {P1/P2 result or 无问题}
Key Decisions [L{n}]:           {P3 result or 无问题}
Approach Skeleton [L{n}]:       {P4 result or 无问题}
Tasks [L{n}]:                   {P4 result or 无问题}
Anchor Candidates:            [{candidate list or empty}]
```

Failure line format:

```
P{n} 失败 — {evidence summary} → zoom L{x}→L{y} [REQUIRED if L0]
```

Append `[REQUIRED]` when current L is L0 (must be handled; cannot skip).

## Return

After outputting ProbeReport, return:

```text
ProbeReport complete — Round {ROUND_N}.
  Issues: {count of non-无问题 lines}
  Anchor failures: {count}
  Next: await human decide (accept / reject / redirect / commit-anchor)
```

Do not write tech-doc.md. Do not advance drafting-progress.
