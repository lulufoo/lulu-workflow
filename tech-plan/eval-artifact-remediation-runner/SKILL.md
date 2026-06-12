---
rule-guard:
  globs:
    - "**/*.md"
description: >
  Artifact remediation runner for tech-plan eval. Fixes WO-MISS / WO-ERROR
  issues in tech-doc.md. Invoked by eval-rules Step 3.
---

# eval-artifact-remediation-runner/SKILL.md

Terminal runner subagent. Resolves **Artifact Remediation** (`WO-MISS`, `WO-ERROR`) for one eval round.

---

## Bootstrap

1. Read `{$SKILL_ROOT}/eval/SKILL.md`
2. Read `{$SKILL_ROOT}/eval/issue-taxonomy.json`
3. Read `{$SKILL_ROOT}/eval/review.template.md`
4. Follow steps below

---

## Required Inputs

```
CYCLE_ID              cycle identifier
CYCLE_TYPE            feature | topic
TECH_DOC_PATH         absolute path to revision tech-doc.md
EVALUATE_DIR          absolute path to revision{N}/evaluate{M}/
EVALUATE_STATE_PATH   absolute path to evaluate-state.md (read-only)
EXECUTION_MODE        guided | autonomous
EVALUATE_ROUND        round number M
PROJECT_ROOT          project root
PRODUCT_REF           (optional, for e1 context)
```

---

## Step 1 — Load pending WO-* rows

For each `tech-review-e{M}*.md` in `EVALUATE_DIR`, parse rows where `root_cause ∈ {WO-MISS, WO-ERROR}` and `status: pending`.

If none → STOP (parent should have skipped dispatch).

---

## Step 2 — Fix loop

For each pending row in order:

### guided mode

`AskQuestion`:

```
Issue {id} [{root_cause}]: {description}
Location: {location} | Severity: {severity}

Option A — Fix: apply fix to tech-doc.md
Option B — Ignore: skip this issue
```

- Fix → edit `TECH_DOC_PATH` using `location` + `description` + `evidence`; update row: `status: fixed`, `decision: fix`
- Ignore → update row: `status: ignored`, `decision: ignore`

### autonomous mode

Auto-fix all WO-* rows unless severity is `minor` and fix requires structural changes. Log reasoning in review file if needed.

---

## Constraints

- Write fixes to `tech-doc.md` only
- Update review row `status` and `decision` only
- Do **not** Write/Edit `evaluate-state.md` or `workflow-state.md`
- Do **not** dispatch subagents
