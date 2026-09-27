# Method — Work-order structural gate

Probe the EvalTarget once. Use `<!-- chapter:task-list -->` and each `<!-- chapter:task-tN -->`. Ignore `<!-- chapter:tech-doc -->`.

Emit one issue per blocker. `root_cause` is `WO-ERROR`. Quote the task-list or task passage as evidence. Do not edit the EvalTarget.

A finding here stops later dimensions. The caller returns the session to Drafting.

## Check 1 — Cross-phase dependencies

Every dependency that crosses a phase boundary in the task-list is declared on the dependent task. A task in a later phase that uses an earlier phase's output without a declared dependency is a blocker.

## Check 2 — SKILL file granularity

Count distinct SKILL files named in each task chapter. More than 3 in one task is a blocker.
