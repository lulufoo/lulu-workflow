---
rule-guard:
  globs:
    - "**/*.md"
description: >
  Single-round evaluation probe executor for lulu-dev-workflow tech-plan sessions.
  Invoked by tech-plan/eval-rules.md per dimension. Writes review file only;
  state via finish-dimension-probe.
---

# eval-runner/SKILL.md

Terminal runner subagent. Probes **one dimension** (`e1`, `e2`, or `e3`) per invocation.

> **Note:** Drafting Round Iteration (`prober-runner`) complements drafting maturity checks; **e3** is the dedicated Evaluating-stage TPEF / Shaping TPEF solution-quality review.

---

## Bootstrap

1. Read `{$SKILL_ROOT}/eval/SKILL.md`
2. Read `{$SKILL_ROOT}/eval/issue-taxonomy.json`
3. Read `{$SKILL_ROOT}/eval/review.template.md`
4. Follow steps below

**WO = `tech-doc.md`** (tech-plan v1)

---

## Required Inputs

```
DIMENSION           e1 | e2 | e3
CYCLE_ID            cycle identifier
CYCLE_TYPE          feature | topic
TECH_DOC_PATH       absolute path to the revision tech-doc.md
EVALUATE_STATE_PATH absolute path to revision{N}/evaluate-state.md (read-only)
EVALUATE_DIR        absolute path to revision{N}/evaluate{M}/
EXECUTION_MODE      guided | autonomous
PROJECT_ROOT        project root
```

Dimension-specific:

| Dimension | Additional inputs | Primary SoT (A) | B |
|-----------|-------------------|-----------------|---|
| `e1` | `PRODUCT_REF` | `PRODUCT_REF` + PTC framework | tech-doc |
| `e2` | — | codebase (+ arch constraints if cited) | tech-doc |
| `e3` | — | TPEF / Shaping TPEF framework | tech-doc |

---

## Step 1 — Load context

- Read `TECH_DOC_PATH`
- For `e2`: locate relevant code entry points:
  - **v2 template** (`## Approach Skeleton` or `## Tasks`): parse those sections
  - **legacy template** (`§5` / `§6`): parse `§5 Data Flow` and `§6 API / Interfaces`
  - Read identified code files
- For `e1`: read `PRODUCT_REF`; use `$FETCH_TECH_PLAN $CYCLE_TYPE eval-ptc`; read stdout as PTC framework
- For `e3`: use `$FETCH_TECH_PLAN $CYCLE_TYPE eval-tpef`; read stdout as TPEF framework

---

## Step 2 — Generate issues list

Evaluate the dimension against `TECH_DOC_PATH` and loaded references.

| Dim | Focus |
|-----|-------|
| `e1` | Intent alignment — does the tech design faithfully implement product requirements? |
| `e2` | Codebase consistency — does the design align with existing code structure / conventions? |
| `e3` | Solution quality — does the design follow TPEF / Shaping TPEF standards? |

For each issue classify `root_cause` per `eval/SKILL.md` and fill all required columns.

Output fields per issue: `id`, `root_cause`, `sot_ref`, `location`, `severity`, `evidence`, `description`, `status: pending`, `decision: —`

---

## Step 3 — Write review file

Path: `{EVALUATE_DIR}/tech-review-e{M}{DIM_N}.md` where `DIM_N` = e1→1, e2→2, e3→3.

1. Read `{$SKILL_ROOT}/eval/review.template.md`
2. Substitute `{{DIM_LABEL}}`, `{{REV}}`, `{{M}}`, `{{DATE}}`, `{{REFS}}`
3. Append issue rows; never alter header/separator row order
4. Zero issues: write header + separator only (no data rows)

Do **not** write `tech-doc.md`. Do **not** Write/Edit `evaluate-state.md`.

---

## Step 4 — Finish probe

Run `$EVAL_CONTROL finish-dimension-probe --dim {DIMENSION}`:

```bash
python3 "$SKILL_DIR/scripts/eval_control.py" \
  --cycle-id "$CYCLE_ID" --project-root "$PROJECT_ROOT" \
  finish-dimension-probe --dim {DIMENSION}
```

Non-zero exit → STOP, report parent.

---

## Constraints

- Probe only — no per-issue fix loop
- State updates **only** via `$EVAL_CONTROL finish-dimension-probe`
- Do **not** dispatch subagents
