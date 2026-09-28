# Work Order Execution Admission

After `compliance-crosscheck` passes, check that every `tasks/t{N}/task.md` can be executed from its own text.

**When to run:** `execution-admission`. The probe method is `lulu-tasks/eval/methods/execution-admission.md`.

**Result:** A failed check is `WO-ERROR`. Record the task passage and return the session to Drafting. When frontmatter has `tdd_exempt: true`, skip checks 2 and 5 for that task.

---

## Checks

### 1 — Granularity

The task changes 1–3 functions, or it is one bounded `tdd_exempt` unit. Deleting one module file is one change. Unchanged functions do not count.

| Check | Pass |
|-------|------|
| Task scope | 1–3 function changes; one module-file deletion counts as one |
| `tdd_exempt` | One bounded unit; the flag states why |

A split of `task-list.md` is a finding.

### 2 — TDD order

Acceptance criteria appear before function specs and are observable conditions.

| Check | Pass |
|-------|------|
| Order | Acceptance criteria section, then function specs |
| Criteria | Observable conditions, not implementation steps |

### 3 — Spec completeness

Signatures and acceptance criteria are filled in.

| Check | Pass |
|-------|------|
| Function signatures | Name, parameters, and return type |
| Acceptance criteria | Non-empty; no `TODO`, `TBD`, or placeholder body |

### 4 — Constraints

Hard rules in the tech-doc for this task's behavior appear in the task.

| Check | Pass |
|-------|------|
| Hard rules | Performance thresholds, format requirements, and error contracts copied into the task |
| Citation | Each copied rule names its tech-doc section |

### 5 — Tests

Acceptance criteria include a normal case, a boundary case, and an edge case.

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

---

## Checklist

- [ ] Each task changes 1–3 functions, or one module-file deletion, or is one bounded `tdd_exempt` unit
- [ ] Acceptance criteria appear before function specs
- [ ] Signatures include name, parameters, and return type
- [ ] No `TODO`, `TBD`, or empty acceptance criteria
- [ ] Tech-doc hard rules for the task are copied, each with a section citation
- [ ] Acceptance criteria cover a normal case, a boundary case, and an edge case, unless `tdd_exempt`
- [ ] The task-list graph is a DAG, and each prerequisite is declared
