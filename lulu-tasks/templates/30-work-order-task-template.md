# Task Template — work-order

> **Usage**: Every `tasks/t{N}/task.md` follows this template. Section order is fixed and reflects the Test-First cognitive constraint: define acceptance criteria first (what proves correctness), then derive function specs (what must be implemented).

---

## File header frontmatter

```yaml
---
version: 1
task_id: t1
title: <one-sentence description of the task goal>
target_files:
  - <relative/path/filename.ext>
dependencies: []          # list of prerequisite task_ids, e.g. [t1, t2]; use [] if none
tdd_exempt: false         # set true for pure UI / pure structural changes with no logic branches
target_repo: <git repo name, no path>
execution_worktree: feature_worktree   # feature_worktree | extra_repo_worktree | custom_path
execution_worktree_path: <path>         # required when execution_worktree is custom_path
exit_contract:
  commit: required
  commit_ref_md: required
  code_log: required
---
```

---

## Section 1: Acceptance Criteria (Test-First — write first)

> **Writing constraints**: Describe test cases in natural language; do not write code. Cover normal / boundary / exception scenarios.
> When `tdd_exempt: true`, this section may be left empty (fill `N/A`).

**Normal scenarios**

- [ ] Scenario description: input `X`, expected output `Y`

**Boundary scenarios**

- [ ] Scenario description: when `X` is at a boundary value, expected output `Y`

**Exception scenarios**

- [ ] Scenario description: when `X` is invalid, expect to throw `ErrorType` or return `Y`

---

## Section 2: Function Specs (derived from acceptance criteria)

> **Writing constraints**: Acceptance criteria come first; then derive function signatures. Do not think through the implementation first and backfill tests.

```
Function name: <function_name>
Signature:     <parameter list> → <return type>
Responsibility: one sentence describing what the function does
Side effects:  <none / describe side effects>
```

If there are multiple functions, list each separately.

---

## Section 3: Constraints (hard implementation rules, copied from tech-doc)

> **Nature**: Must be followed in the TDD session; violation means the implementation does not meet architecture requirements.

- Constraint 1: <source tech-doc §N>  
- Constraint 2: <source tech-doc §N>  

---

## Section 4: Supplement (soft context, copied from tech-doc)

> **Nature**: The TDD session should be aware of these, but they are not individually mandatory. Used to prevent loss of tech-doc information.

- Background:  
- Migration window / cross-team dependencies:  
- Reference links:  

---

## Section 5: Dependencies

> List prerequisite tasks. The TDD session should not start this task while dependencies remain incomplete.

| Prerequisite task_id | Reason |
|---|---|
| — | — |
