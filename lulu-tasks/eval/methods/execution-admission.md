# Method — Task execution admission

Probe each `<!-- chapter:task-tN -->` once. `root_cause` is `WO-ERROR`. Quote the task passage. Do not edit the EvalTarget.

`kind` is `coding` or `verify`. Checks 1, 2, 3, and 5 apply only to `coding`. Checks 4 and 6 apply to both. When `kind` is `coding` and `tdd_exempt: true`, skip checks 2 and 5 for that task.

## Checks

1. **Granularity.** `coding` only. If the task changes functions, it changes 1–3, or it is one bounded `tdd_exempt` unit. Deleting one module file is one change. Unchanged functions do not count. A split of the task-list is a finding. Do not split a `verify` task by function count. No code change on a `verify` task is not a finding.
2. **TDD order.** `coding` only. Acceptance criteria are observable conditions and appear before function specs.
3. **Spec completeness.** `coding` only: each function the task changes includes name, parameters, and return type. A `verify` task needs no function spec. Both kinds: acceptance criteria are non-empty. No `TODO`, `TBD`, or placeholder body.
4. **Constraints.** Hard rules stated in `<!-- chapter:tech-doc -->` for this task's behavior appear in the task, with a section citation.
5. **Tests.** `coding` only. Acceptance criteria include a normal case, a boundary case, and an edge case.
6. **Dependencies.** The task-list graph is a DAG. Each prerequisite is declared. A cycle or a missing edge is a finding.

## verify

The task names the command and the observable result.
