# Method — Work-order coverage

Probe the EvalTarget once. `<!-- chapter:tech-doc -->` is the reference. Task-list and `<!-- chapter:task-tN -->` are the work order.

The reference is treated as sound. Emit `WO-MISS` or `WO-ERROR` only. Do not emit `SOT-DEFECT`, `UNRESOLVABLE`, or `DECISION-REQUIRED`. Do not edit the EvalTarget.

## Check 1 — Coverage (`WO-MISS`)

Each deliverable behavior in the tech-doc chapter has at least one task that carries it. A behavior with no task is `WO-MISS`. Quote the tech-doc passage and name the missing task location. An `action` task carries a behavior whose deliverable is a confirmed state of a system or a checked condition. That behavior does not also need a `coding` task.

## Check 2 — Traceability (`WO-MISS`)

Each task acceptance criterion that restates a tech-doc requirement cites that section. A requirement present in the tech-doc chapter and absent from the citing task is `WO-MISS`.

## Check 3 — Work-order deviations (`WO-ERROR`)

A task constraint that contradicts a tech-doc hard rule is `WO-ERROR`. A task that adds behavior the tech-doc chapter does not contain is `WO-ERROR`.

Silence in the tech-doc chapter is not a finding.
