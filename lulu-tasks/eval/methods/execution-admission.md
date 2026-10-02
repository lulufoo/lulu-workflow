# Method — Task execution admission

Probe each `<!-- chapter:task-tN -->` once. `root_cause` is `WO-ERROR`. Quote the task passage. The probe does not edit the EvalTarget.

`kind` is `coding` or `action`. Checks 1, 2, 3, and 5 apply only to `coding`. Checks 7 and 8 apply only to `action`. Checks 4 and 6 apply to both. When `kind` is `coding` and `tdd_exempt: true`, skip checks 2 and 5 for that task.

## Checks

1. **Granularity.** `coding` only. If the task changes functions, it changes 1–3, or it is one bounded `tdd_exempt` unit. Deleting one module file is one change. Unchanged functions do not count. A split of the task-list is a finding. Do not split an `action` task by function count. No code change on an `action` task is not a finding.
2. **TDD order.** `coding` only. Acceptance criteria are observable conditions and appear before function specs.
3. **Spec completeness.** `coding` only: each function the task changes includes name, parameters, and return type. An `action` task needs no function spec. Both kinds: acceptance criteria are non-empty. No `TODO`, `TBD`, or placeholder body.
4. **Constraints.** Hard rules stated in `<!-- chapter:tech-doc -->` for this task's behavior appear in the task, with a section citation.
5. **Tests.** `coding` only. Acceptance criteria include a normal case, a boundary case, and an edge case.
6. **Dependencies.** The task-list graph is a DAG. Each prerequisite is declared. A cycle or a missing edge is a finding.
7. **Effects.** `action` only. `effects` matches what the goal needs. A goal that writes to a system declares `mutates` and names that system. A goal that only reads declares `read_only`. A mismatch in either direction is a finding.
8. **Idempotency.** `action` only. The goal is reachable by inspecting the current state and acting on what is missing. A goal whose effect repeats on re-run, such as sending a message, is a finding. The fix is to reword the goal or split the task.

## action

The title states the goal. Each acceptance criterion is an observable condition that evidence such as an id, link, command output, or count can answer.

## Remediation

Edit `<!-- chapter:task-tN -->` bodies only. The tech-doc and task-list chapters stay byte-identical; task chapters are neither added nor removed. A split (check 1), a missing edge (check 6), or any fix that needs the task-list cannot be resolved in this round: include that task-list edit in the diff so the work-order owner rejects the round and returns the order to Drafting with the findings.
