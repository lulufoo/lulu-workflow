# Method — Task execution admission

Probe each `<!-- chapter:task-tN -->` once. `root_cause` is `WO-ERROR`. Quote the task passage. The probe does not edit the EvalTarget.

`kind` is `coding` or `action`. Checks 1, 2, and 3 apply only to `coding`. Checks 5 and 6 apply only to `action`. Check 4 applies to both. When `kind` is `coding` and `tdd_exempt: true`, skip checks 1 and 3 for that task.

## Checks

1. **TDD order.** `coding` only. Acceptance criteria are observable conditions and appear before function specs.
2. **Spec completeness.** `coding` only: each function the task changes includes name, parameters, and return type. An `action` task needs no function spec. Both kinds: acceptance criteria are non-empty. No `TODO`, `TBD`, or placeholder body.
3. **Tests.** `coding` only. Acceptance criteria include a normal case, a boundary case, and an edge case.
4. **Dependencies.** The task-list graph is a DAG. Each prerequisite is declared. A cycle or a missing edge is a finding.
5. **Effects.** `action` only. `effects` matches what the goal needs. A goal that writes to a system declares `mutates` and names that system. A goal that only reads declares `read_only`. A mismatch in either direction is a finding.
6. **Idempotency.** `action` only. The goal is reachable by inspecting the current state and acting on what is missing. A goal whose effect repeats on re-run, such as sending a message, is a finding. The fix is to reword the goal or split the task.

## action

The title states the goal. Each acceptance criterion is an observable condition that evidence such as an id, link, command output, or count can answer.

## Remediation

Edit existing `<!-- chapter:task-tN -->` bodies only. A missing edge (check 4) or any other fix that needs the task-list is out of this round's scope: write that task-list edit into the diff anyway; the work-order owner rejects the round and returns the order to Drafting with the findings.
