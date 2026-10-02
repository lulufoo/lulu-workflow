# Method — Work-order coverage

Probe the EvalTarget once. `<!-- chapter:tech-doc -->` is the reference. Task-list and `<!-- chapter:task-tN -->` are the work order.

The reference is treated as sound. Emit `WO-MISS` or `WO-ERROR` only. Do not emit `SOT-DEFECT`, `UNRESOLVABLE`, or `DECISION-REQUIRED`. The probe does not edit the EvalTarget.

## Check 1 — Coverage (`WO-MISS`)

Each deliverable behavior in the tech-doc chapter has at least one task that carries it. A behavior with no task is `WO-MISS`. Quote the tech-doc passage and name the missing task location. An `action` task carries a behavior whose deliverable is a confirmed state of a system or a checked condition. That behavior does not also need a `coding` task.

## Check 2 — Traceability (`WO-MISS`)

Each task acceptance criterion or constraint that restates a tech-doc requirement or hard rule cites that section. A requirement or hard rule present in the tech-doc chapter for a task's behavior and absent from that task is `WO-MISS`.

## Check 3 — Work-order deviations (`WO-ERROR`)

A task constraint that contradicts a tech-doc hard rule is `WO-ERROR`. A task that adds behavior the tech-doc chapter does not contain is `WO-ERROR`.

Silence in the tech-doc chapter is not a finding.

## Remediation

Edit existing `<!-- chapter:task-tN -->` bodies only. A finding that needs a new task or a task-list change is out of this round's scope: write that task-list edit into the diff anyway; the work-order owner rejects the round and returns the order to Drafting with the findings.
