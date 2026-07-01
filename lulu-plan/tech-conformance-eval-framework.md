# Tech Conformance Evaluation Framework

> **Dimension:** `tech-conformance` (e4)
> **SoT:** upstream tech intent document — either `design-doc` (from lulu-design) or `decision-doc` (from lulu-approach)
> **EvalTarget:** `tech-doc`

---

## Purpose

Verify that `tech-doc` faithfully operationalizes the upstream tech intent document.
The probe checks that design decisions, constraints, and direction choices expressed in the SoT
are traceable to concrete implementation plans in `tech-doc`.

---

## Probe Procedure

### P1 — Decision / Direction Coverage

For each design decision (design-doc) or key direction choice (decision-doc) in the SoT:

1. Locate the corresponding section(s) in `tech-doc`.
2. Verify the decision or direction is explicitly addressed — not omitted, not deferred without reason.

**Issue:** decision or direction present in SoT but absent or unaddressed in `tech-doc`.

### P2 — Constraint Operationalization

For each constraint stated in the SoT (technical, architectural, or scoping constraint):

1. Identify where in `tech-doc` the constraint is reflected.
2. Verify the implementation plan does not violate the constraint.

**Issue:** constraint stated in SoT but contradicted or silently ignored in `tech-doc`.

### P3 — AC / Objective Traceability (design-doc SoT only)

When SoT is a `design-doc`:

1. For each Acceptance Criterion (AC) in the SoT, locate its corresponding task row or verification criterion in `tech-doc`.
2. Verify coverage is explicit, not assumed.

**Issue:** AC in SoT with no traceable task or verification entry in `tech-doc`.

### P4 — No Scope Inflation

Identify implementation decisions in `tech-doc` that have no basis in the SoT and expand scope
beyond the stated direction.

**Issue:** `tech-doc` introduces significant design choices or scope that contradict or materially extend beyond SoT boundaries without justification.

---

## Severity

| Condition | Severity |
|---|---|
| P1 — major decision or direction absent | `high` |
| P2 — constraint violated | `high` |
| P3 — AC with no trace | `high` |
| P4 — unexplained scope inflation | `medium` |
| P1/P2/P3 — minor or peripheral item | `medium` |

---

## SoT Interpretation Notes

- **design-doc SoT:** apply P1 + P2 + P3 + P4.
- **decision-doc SoT:** apply P1 + P2 + P4 only (no ACs to trace).
- When SoT section is marked as exploratory or TBD, skip P3 for that item.
