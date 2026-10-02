# Work Order Coverage

Check the work order against the tech-doc. The tech-doc is the reference.

**When to run:** `compliance-crosscheck`. The probe method is `lulu-tasks/eval/methods/compliance-crosscheck.md`.

**Result:** A coverage or citation gap is `WO-MISS`. A contradiction or an added behavior is `WO-ERROR`. Quote the passage. Eval remediates it inside the task chapter; a fix that needs a new task or a task-list change returns the session to Drafting. Silence in the tech-doc is not a finding.

---

## Checks

### 1 — Coverage (`WO-MISS`)

Each deliverable behavior in the tech-doc has at least one task that implements it.

Enumerate behaviors, functions, and integration points. A heading is not a unit.

| Check | Pass |
|-------|------|
| Deliverable behavior | At least one task implements it |
| Evidence | The tech-doc passage, and the task location that is missing |

### 2 — Traceability (`WO-MISS`)

An acceptance criterion that restates a tech-doc requirement cites that section.

| Check | Pass |
|-------|------|
| Citation | The criterion names the tech-doc section it restates |
| Presence | A requirement in the tech-doc appears in the task that cites it |
| Evidence | The tech-doc passage, and the task criterion that omits it |

### 3 — Deviations (`WO-ERROR`)

A task constraint matches the tech-doc hard rule it implements. The task adds no behavior the tech-doc does not contain.

| Check | Pass |
|-------|------|
| Hard rules | Performance thresholds, format requirements, and error contracts in the task match the tech-doc |
| Scope | Every behavior in the task is present in the tech-doc |
| Evidence | The tech-doc passage and the task passage that conflicts with it, or the task passage that adds the behavior |

---

## Checklist

- [ ] Deliverable behaviors are enumerated from the tech-doc, not from its headings
- [ ] Each behavior has a task that implements it
- [ ] Each acceptance criterion that restates a tech-doc requirement cites that section
- [ ] Each task constraint matches the tech-doc hard rule it implements
- [ ] No task adds behavior the tech-doc does not contain
