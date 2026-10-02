# Work Order Execution Admission

Check that every `tasks/t{N}/task.md` can be executed from its own text.

**When to run:** `execution-admission`, in the same Eval round as `compliance-crosscheck`. The probe method is `lulu-tasks/eval/methods/execution-admission.md`.

**Result:** A failed check is `WO-ERROR`. Record the task passage. Eval remediates it inside the task chapter; a fix that needs the task-list returns the session to Drafting. `kind` is `coding` or `action`. Checks 1, 2, 3, and 5 apply only to `coding`. Checks 7 and 8 apply only to `action`. When `kind` is `coding` and `tdd_exempt: true`, skip checks 2 and 5 for that task.

---

## Checks

### 1 — Granularity

`coding` only. If the task changes functions, it changes 1–3, or it is one bounded `tdd_exempt` unit. Deleting one module file is one change. Unchanged functions do not count. Do not split an `action` task by function count.

| Check | Pass |
|-------|------|
| Function changes | `coding`: 1–3, or one module-file deletion |
| `action` | Not split by function count |
| `tdd_exempt` | `coding` only: one bounded unit; the flag states why |

A split of `task-list.md` is a finding.

### 2 — TDD order

`coding` only. Acceptance criteria are observable conditions and appear before function specs.

| Check | Pass |
|-------|------|
| Order | Acceptance criteria section, then any function specs |
| Criteria | Observable conditions, not implementation steps |

### 3 — Spec completeness

Signatures and acceptance criteria are filled in.

| Check | Pass |
|-------|------|
| Function signatures | `coding`: name, parameters, and return type. `action`: no function spec |
| Acceptance criteria | Non-empty; no `TODO`, `TBD`, or placeholder body |

### 4 — Constraints

Hard rules in the tech-doc for this task's behavior appear in the task.

| Check | Pass |
|-------|------|
| Hard rules | Performance thresholds, format requirements, and error contracts copied into the task |
| Citation | Each copied rule names its tech-doc section |

### 5 — Tests

`coding` only. Acceptance criteria include a normal case, a boundary case, and an edge case. An `action` task lists observable conditions that evidence can answer instead.

| Check | Pass |
|-------|------|
| Normal | One happy-path condition |
| Boundary | A limit, empty input, or single-element case |
| Edge | An error state, or null when the tech-doc names it |

### 6 — Dependencies

The task-list graph is a DAG. Each prerequisite is declared.

| Check | Pass |
|-------|------|
| Graph | No cycle |
| Edges | Every task whose output this task uses is listed in `dependencies` |

A cycle or a missing edge is a finding.

### 7 — Effects

`action` only. `effects` matches what the goal needs.

| Check | Pass |
|-------|------|
| Writes | A goal that writes to a system declares `mutates` and names that system |
| Reads | A goal that only reads declares `read_only` |

A mismatch in either direction is a finding.

### 8 — Idempotency

`action` only. The goal is reachable by inspecting the current state and acting on what is missing.

| Check | Pass |
|-------|------|
| Re-run | Running the task again adds nothing that already exists |

A goal whose effect repeats on re-run, such as sending a message, is a finding. Reword the goal or split the task.

---

## Checklist

- [ ] `coding` function changes are 1–3, or one module-file deletion counts as one; `action` is not split by function count
- [ ] `coding` acceptance criteria appear before function specs
- [ ] `coding` signatures include name, parameters, and return type; `action` has no function spec
- [ ] `action` acceptance criteria are observable conditions that evidence can answer
- [ ] `action` `effects` matches what the goal reads or writes
- [ ] `action` goal is idempotent
- [ ] No `TODO`, `TBD`, or empty acceptance criteria
- [ ] Tech-doc hard rules for the task are copied, each with a section citation
- [ ] `coding` acceptance criteria cover a normal case, a boundary case, and an edge case, unless `tdd_exempt`
- [ ] The task-list graph is a DAG, and each prerequisite is declared
