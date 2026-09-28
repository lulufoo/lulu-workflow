# Method — Task execution admission

Probe each `<!-- chapter:task-tN -->` once. `root_cause` is `WO-ERROR`. Quote the task passage. Do not edit the EvalTarget.

When the task frontmatter has `tdd_exempt: true`, skip checks 2 and 5 for that task.

## Checks

1. **Granularity.** The task changes 1–3 functions, or it is one bounded `tdd_exempt` unit. Deleting one module file is one change. Unchanged functions do not count. A split of the task-list is a finding.
2. **TDD order.** Acceptance criteria appear before function specs and are observable conditions.
3. **Spec completeness.** Signatures include name, parameters, and return type. Acceptance criteria are non-empty. No `TODO`, `TBD`, or placeholder body.
4. **Constraints.** Hard rules stated in `<!-- chapter:tech-doc -->` for this task's behavior appear in the task, with a section citation.
5. **Tests.** Acceptance criteria include a normal case, a boundary case, and an edge case.
6. **Dependencies.** The task-list graph is a DAG. Each prerequisite is declared. A cycle or a missing edge is a finding.
