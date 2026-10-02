# Work Order Execution Admission

Check that every `tasks/t{N}/task.md` can be executed from its own text.

**When to run:** `execution-admission`, in the same Eval round as `compliance-crosscheck`. The probe method is `lulu-tasks/eval/methods/execution-admission.md`.

**Result:** A failed check is `WO-ERROR`. Record the task passage. Eval remediates it inside the task chapter; a fix that needs the task-list returns the session to Drafting. `kind` is `coding` or `action`. Checks 1, 2, and 3 apply only to `coding`. Checks 5 and 6 apply only to `action`. Check 4 applies to both. When `kind` is `coding` and `tdd_exempt: true`, skip checks 1 and 3 for that task.

---

## Checks

### 1 — TDD order

`coding` only. Acceptance criteria are observable conditions and appear before function specs.

| Check | Pass |
|-------|------|
| Order | Acceptance criteria section, then any function specs |
| Criteria | Observable conditions, not implementation steps |

### 2 — Spec completeness

Signatures and acceptance criteria are filled in.

| Check | Pass |
|-------|------|
| Function signatures | `coding`: name, parameters, and return type. `action`: no function spec |
| Acceptance criteria | Non-empty; no `TODO`, `TBD`, or placeholder body |

### 3 — Tests

`coding` only. Acceptance criteria include a normal case, a boundary case, and an edge case. An `action` task lists observable conditions that evidence can answer instead.

| Check | Pass |
|-------|------|
| Normal | One happy-path condition |
| Boundary | A limit, empty input, or single-element case |
| Edge | An error state, or null when the tech-doc names it |

### 4 — Dependencies

The task-list graph is a DAG. Each prerequisite is declared.

| Check | Pass |
|-------|------|
| Graph | No cycle |
| Edges | Every task whose output this task uses is listed in `dependencies` |

A cycle or a missing edge is a finding.

### 5 — Effects

`action` only. `effects` matches what the goal needs.

| Check | Pass |
|-------|------|
| Writes | A goal that writes to a system declares `mutates` and names that system |
| Reads | A goal that only reads declares `read_only` |

A mismatch in either direction is a finding.

### 6 — Idempotency

`action` only. The goal is reachable by inspecting the current state and acting on what is missing.

| Check | Pass |
|-------|------|
| Re-run | Running the task again adds nothing that already exists |

A goal whose effect repeats on re-run, such as sending a message, is a finding. Reword the goal or split the task.

---

## Checklist

- [ ] `coding` acceptance criteria appear before function specs
- [ ] `coding` signatures include name, parameters, and return type; `action` has no function spec
- [ ] `action` acceptance criteria are observable conditions that evidence can answer
- [ ] `action` `effects` matches what the goal reads or writes
- [ ] `action` goal is idempotent
- [ ] No `TODO`, `TBD`, or empty acceptance criteria
- [ ] `coding` acceptance criteria cover a normal case, a boundary case, and an edge case, unless `tdd_exempt`
- [ ] The task-list graph is a DAG, and each prerequisite is declared
