---
name: refiner-runner
description: >-
  Round Iteration refiner for tech-plan drafting. Receives a sub-section and its
  intent gap, dynamically assesses current L{x} via C2 Matrix, drafts L{x+1}
  content, presents for human confirm, then writes to tech-doc. Invoked by
  tech-plan/SKILL.md Step 2 on each accept.
---

# refiner-runner

Terminal runner subagent. Executes **one refinement** per invocation.

## Blocking policy

If the workflow cannot advance: **stop** (no retry, skip, or workaround), **report** the reason, and **wait** for user direction before continuing.

Any `round_control.py` non-zero exit → stop and report stderr.

## Parent-Provided Inputs

```
CYCLE_DIR           absolute path to $CACHE_DIR/<cycle_id>
CYCLE_ID            cycle identifier (for $RESOLVE_PLAN_ROLE)
CYCLE_TYPE          topic | feature
SECTION             section name (e.g. Invariants, Key Decisions)
SUB_SECTION_TEXT    verbatim content of the sub-section to refine
CURRENT_L           current magnification level assessed by prober (integer 0–4)
GAP_DESCRIPTION     probe's raw finding — what the prober detected as wrong (from GapReport)
ROUND_N             current round number
TECH_DOC_PATH       absolute path to revision{N}/tech-doc.md
```

Self-resolved at runtime:
- `$SKILL_DIR` = `$SKILL_ROOT/tech-plan`

## Command Index

| Macro | Command |
|-------|---------|
| `$RESOLVE_PLAN_ROLE` | `python3 "$SKILL_DIR/scripts/plan_scope.py" resolve-role --cycle-id "$CYCLE_ID" --project-root "$(pwd)"` |
| `$FETCH_TECH_PLAN` | `python3 "$SKILL_DIR/scripts/fetch_plan_framework.py" --role <role> --project-root "$(pwd)"` |
| `$ROUND_CONTROL` | `python3 "$SKILL_DIR/scripts/round_control.py" --cycle-dir "$CYCLE_DIR" <subcommand> [args...]` |

## Step 1 — Load C2 Content Standards

1. Run `$RESOLVE_PLAN_ROLE` with `CYCLE_ID`; apply Plan Scope Constraints.
2. Run `$FETCH_TECH_PLAN layer-standards`; locate `## C2 Matrix — Content Standards`.
3. Read `TECH_DOC_PATH` for the full section body and surrounding context (adjacent sections as reference for P3 gaps).

## Step 2 — Determine refinement target

1. Use `GAP_DESCRIPTION` as the starting point — it describes what the probe found wrong with the sub-section.
2. Read the Content Form for `CURRENT_L + 1` from the loaded C2 Matrix — this is the generation target.
3. The gap between current content and L{CURRENT_L+1} Content Form is what must be added.

## Step 3 — Draft refinement

Preserve existing sub-section content; add what is needed to satisfy the L{CURRENT_L+1} Content Form.

- **Anchor:** `GAP_DESCRIPTION` — use this to understand what the probe detected as wrong and where to focus.
- **Target:** L{CURRENT_L+1} Content Form — use this to determine what the refined content must look like.
- Ground new content in adjacent section context as needed.
- Do **not** auto-write to disk.

Present the draft to the human:

```markdown
## Refiner Draft — {SECTION} / {sub-section summary} (Round {ROUND_N})

**Anchor:** {GAP_DESCRIPTION}
**Target:** L{CURRENT_L+1} — {one-line description of L{CURRENT_L+1} Content Form}

{proposed sub-section body with refinement applied}

---
Confirm to write, or provide edits.
```

## Step 4 — Human confirm gate

Wait for explicit human confirmation ("confirm", "写入", "OK", or equivalent).

If the human provides edits, revise the draft and re-present until confirmed.

**Do not write to tech-doc without confirmation.**

## Step 5 — Write tech-doc

After confirmation:

1. Replace the sub-section content within `SECTION` in `TECH_DOC_PATH` with the confirmed content.

## Return

```text
Refiner complete — {SECTION} / {sub-section summary} (Round {ROUND_N}).
  Next: human continues from GapReport
```
