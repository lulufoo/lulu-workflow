---
rule-guard:
  globs:
    - "**/*.md"
description: >
  Per-dimension SoT remediation runner. Resolves SOT-DEFECT / UNRESOLVABLE for
  one ReviewFile. Invoked by eval-rules Step 4.
---

# eval-sot-remediation-runner/SKILL.md

Terminal runner subagent. Resolves **SoT Remediation** (`SOT-DEFECT`, `UNRESOLVABLE`) for **one dimension**.

---

## Bootstrap

1. Read `{$SKILL_ROOT}/eval/SKILL.md`
2. Read `{$SKILL_ROOT}/eval/issue-taxonomy.json`
3. Read `{$SKILL_ROOT}/eval/review.template.md`
4. Read `{$SKILL_ROOT}/tech-work-order/eval-runner/SKILL.md` — **Attribution Protocol** and **Evidence Format per Root Cause** sections only
5. Follow steps below

---

## Required Inputs

Same plain-text contract as `eval-artifact-remediation-runner` (from `begin-dimension-sot-remediation`).

---

## Step 1 — Load pending SOT rows

Parse `{EVALUATE_DIR}/{REVIEW_OUTPUT_PATH}` for rows where `root_cause ∈ {SOT-DEFECT, UNRESOLVABLE}` and `status: pending`.

If none → STOP.

---

## Step 2 — Interactive loop (always AskQuestion)

For each pending row:

```
Issue {id} [{root_cause}]: {description}
Evidence: {evidence}
SoT ref: {sot_ref}

Option A — Escalate: cannot resolve; mark escalated
Option B — Reclassify: change root_cause to WO-MISS or WO-ERROR
Option C — Ignore: skip this issue
```

- **Escalate** → update row: `status: escalated`, `decision: escalate`
- **Reclassify → WO-*** → update `root_cause`; apply Artifact fix **inline** to `REMEDIATION_TARGET_PATH`; update row: `status: fixed`, `decision: reclassify`
- **Ignore** → update row: `status: ignored`, `decision: ignore`

`UNRESOLVABLE → Reclassify → SOT-DEFECT` path: treat as Escalate.

---

## Constraints

- Update this dimension's ReviewFile and `REMEDIATION_TARGET_PATH` (reclassify inline fix only)
- Do **not** Write/Edit `evaluate-state.md` or `workflow-state.md`
- Do **not** dispatch subagents
