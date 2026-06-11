---
name: prober-runner
description: >-
  Round Iteration prober for tech-plan drafting. Runs P1–P4 verification probes
  per section, merges Anchor Ledger checks, and outputs a pinned ProbeReport.
  Invoked by tech-plan/SKILL.md Step 3 per round.
---

# prober-runner

Terminal runner subagent. Executes **one probe round** per invocation.

## Blocking policy

If the workflow cannot advance: **stop** (no retry, skip, or workaround), **report** the reason, and **wait** for user direction before continuing.

Any `round_state.py` non-zero exit → stop and report stderr.

## Parent-Provided Inputs

```
CYCLE_DIR           absolute path to $CACHE_DIR/<cycle_id>
CYCLE_TYPE          feature | topic
ROUND_N             current round number (integer ≥ 1)
TECH_DOC_PATH       absolute path to revision{N}/tech-doc.md
```

Self-resolved at runtime:
- `$SKILL_DIR` = `$SKILL_ROOT/tech-plan`
- `$META_KEY` = `tpt_meta_v2_url` when `CYCLE_TYPE=feature`, else `tpt_meta_url`

## Step 1 — Load context

```bash
python3 "$SKILL_DIR/scripts/round_state.py" \
  --cycle-dir "$CYCLE_DIR" \
  read-context
```

Parse stdout JSON as `$CTX`. Required fields: `state_vector`, `anchors`, `skips`, `round`.

Load C2 Matrix for Diagnostic Criterion checks:

```text
Use $FETCH_TEMPLATE tech-plan $META_KEY
```

Read stdout as meta markdown; locate `## C2 Matrix`.

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

```bash
python3 "$SKILL_DIR/scripts/round_state.py" \
  --cycle-dir "$CYCLE_DIR" \
  update-anchor-status --id {anchor_id} --status failing
```

- If re-check **passes** → update ledger when status was `failing`:

```bash
python3 "$SKILL_DIR/scripts/round_state.py" \
  --cycle-dir "$CYCLE_DIR" \
  update-anchor-status --id {anchor_id} --status passing
```

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
