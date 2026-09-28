# Task Template — work-order

> **Usage**: Every `tasks/t{N}/task.md` follows this template. `kind` is `coding` or `verify`. Section 2 is `coding` only.

---

## File header frontmatter

```yaml
---
version: 1
task_id: t1
title: <one-sentence description of the task goal>
kind: coding               # coding | verify
target_files:
  - <relative/path/filename.ext>
dependencies: []          # list of prerequisite task_ids, e.g. [t1, t2]; use [] if none
tdd_exempt: false         # coding only: true for pure UI / pure structural changes with no logic branches
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

## Section 1: Acceptance Criteria

> **Writing constraints**: `coding` covers a normal case, a boundary case, and an exception. `tdd_exempt: true` may use `N/A`. `verify` names the command and the observable result, and has no function spec.

**Normal scenarios**

- [ ] Scenario description: input `X`, expected output `Y`

**Boundary scenarios**

- [ ] Scenario description: when `X` is at a boundary value, expected output `Y`

**Exception scenarios**

- [ ] Scenario description: when `X` is invalid, expect to throw `ErrorType` or return `Y`

---

## Section 2: Function Specs

> **coding only.** Omit this section for `verify`. Acceptance criteria come first. Read code only for the signature being specified.

```
Function name: <function_name>
Signature:     <parameter list> → <return type>
Responsibility: one sentence describing what the function does
Side effects:  <none / describe side effects>
```

If there are multiple functions, list each separately.

---

## Section 3: Constraints (hard implementation rules, copied from tech-doc)

> **Nature**: Must be followed. A `coding` task that breaks one does not meet the cited rule. A `verify` task that breaks one does not meet the cited check.

- Constraint 1: <source tech-doc §N>  
- Constraint 2: <source tech-doc §N>  

---

## Section 4: Supplement (soft context, copied from tech-doc)

> **Nature**: Context for the task. Not individually mandatory. Keeps tech-doc information from being dropped.

- Background:  
- Migration window / cross-team dependencies:  
- Reference links:  

---

## Section 5: Dependencies

> List prerequisite tasks. Do not start this task while dependencies remain incomplete.

| Prerequisite task_id | Reason |
|---|---|
| — | — |
