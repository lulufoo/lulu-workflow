---
rule-guard:
  globs:
    - "**/*.md"
description: >
  SoT remediation runner for tech-plan eval. Resolves SOT-DEFECT / UNRESOLVABLE
  via interactive escalation. Invoked by eval-rules Step 4.
---

# eval-sot-remediation-runner/SKILL.md

Terminal runner subagent. Resolves **SoT Remediation** (`SOT-DEFECT`, `UNRESOLVABLE`) for one eval round.

---

## Bootstrap

1. Read `{$SKILL_ROOT}/eval/SKILL.md`
2. Read `{$SKILL_ROOT}/eval/issue-taxonomy.json`
3. Read `{$SKILL_ROOT}/eval/review.template.md`
4. Read `{$SKILL_ROOT}/tech-work-order/eval-runner/SKILL.md` — **Attribution Protocol** and **Evidence Format per Root Cause** sections only (SOT-DEFECT / UNRESOLVABLE AskQuestion depth)
5. Follow steps below

---

## Required Inputs

Same contract as `eval-artifact-remediation-runner` (see that SKILL).

---

## Step 1 — Load pending SOT rows

For each `tech-review-e{M}*.md` in `EVALUATE_DIR`, parse rows where `root_cause ∈ {SOT-DEFECT, UNRESOLVABLE}` and `status: pending`.

If none → STOP (parent should have skipped dispatch).

---

## Step 2 — Interactive loop (always AskQuestion)

**Always AskQuestion** regardless of `EXECUTION_MODE` (P2).

For each pending row:

```
Issue {id} [{root_cause}]: {description}
Evidence: {evidence}
SoT ref: {sot_ref}

Option A — Escalate: cannot resolve; mark escalated
Option B — Reclassify: change root_cause to WO-MISS or WO-ERROR
Option C — Ignore: skip this issue
```

- **Escalate** → update row: `status: escalated`, `decision: escalate`. Parent `check-sot-remediation` sets `eval_status: abandoned`.
- **Reclassify → WO-MISS / WO-ERROR** → update row `root_cause`; apply Artifact remediation fix **inline** to `tech-doc.md` (same rules as artifact runner); update row: `status: fixed`, `decision: reclassify`. Do **not** re-enter Artifact Remediation step.
- **Ignore** → update row: `status: ignored`, `decision: ignore`

`UNRESOLVABLE → Reclassify → SOT-DEFECT` path: treat as Escalate.

---

## Constraints

- Update review rows and `tech-doc.md` (Reclassify inline fix only)
- Do **not** Write/Edit `evaluate-state.md` or `workflow-state.md`
- Do **not** dispatch subagents
