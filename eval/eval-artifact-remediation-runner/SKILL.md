---
rule-guard:
  globs:
    - "**/*.md"
description: >
  Per-dimension artifact remediation runner. Fixes WO-MISS / WO-ERROR for one
  ReviewFile; writes RemediationTarget from EvalCorpus. Invoked by eval-rules Step 3.
---

# eval-artifact-remediation-runner/SKILL.md

Terminal runner subagent. Resolves **Artifact Remediation** (`WO-MISS`, `WO-ERROR`) for **one dimension**.

---

## Bootstrap

1. Read `{$SKILL_ROOT}/eval/SKILL.md`
2. Read `{$SKILL_ROOT}/eval/issue-taxonomy.json`
3. Read `{$SKILL_ROOT}/eval/review.template.md`
4. Follow steps below

---

## Required Inputs

Plain-text block from `$EVAL_CONTROL begin-dimension-artifact-remediation`:

```
WORKFLOW_ID
DIMENSION_ID
DIMENSION
DIMENSION_LABEL
CYCLE_ID
CYCLE_TYPE
REMEDIATION_TARGET_PATH   absolute path (write target)
EVALUATE_DIR
EVALUATE_STATE_PATH       read-only
REVIEW_OUTPUT_PATH        filename relative to EVALUATE_DIR
EVALUATE_ROUND
PROJECT_ROOT
UPSTREAM_BASELINE_REF     optional
```

---

## Step 1 — Load pending WO-* rows

Parse `{EVALUATE_DIR}/{REVIEW_OUTPUT_PATH}` for rows where `root_cause ∈ {WO-MISS, WO-ERROR}` and `status: pending`.

If none → STOP (parent should not have dispatched).

---

## Step 2 — Fix loop

For each pending row in order, **AskQuestion**:

```
Issue {id} [{root_cause}]: {description}
Location: {location} | Severity: {severity}

Option A — Fix: apply fix to RemediationTarget
Option B — Ignore: skip this issue
```

- **Fix** → edit `REMEDIATION_TARGET_PATH` using `location` + `description` + `evidence`; update row: `status: fixed`, `decision: fix`
- **Ignore** → update row: `status: ignored`, `decision: ignore`

---

## Constraints

- Write fixes to `REMEDIATION_TARGET_PATH` only
- Update review row `status` and `decision` only in this dimension's ReviewFile
- Do **not** Write/Edit `evaluate-state.md` or `workflow-state.md`
- Do **not** dispatch subagents
