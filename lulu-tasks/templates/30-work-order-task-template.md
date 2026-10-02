# Task Template — work-order

> **Usage**: Every `tasks/t{N}/task.md` follows this template. `kind` is `coding` or `action`. Section 2 is `coding` only.

---

## File header frontmatter

```yaml
---
version: 1
task_id: t1
title: <one-sentence description of the task goal>
kind: coding               # coding | action
target_files:
  - <relative/path/filename.ext>
dependencies: []          # list of prerequisite task_ids, e.g. [t1, t2]; use [] if none
tdd_exempt: false         # coding only: true for pure UI / pure structural changes with no logic branches
target_repo: <git repo name, no path>          # coding: required. action: only with execution_worktree
execution_worktree: feature_worktree   # feature_worktree | extra_repo_worktree | custom_path. coding: required. action: omit to run in the project root
execution_worktree_path: <path>         # required when execution_worktree is custom_path
effects: read_only        # action only: read_only | mutates
mutates: [<system>]       # action only: required when effects is mutates, e.g. [linear]; omit for read_only
exit_contract:
  commit: required          # coding: required. action: omit; use receipt
  commit_ref_md: required   # coding only
  code_log: required        # coding only
  # receipt: required       # action only
---
```

---

## Section 1: Acceptance Criteria

> **Writing constraints**: `coding` lists at least one item under each of the three headings below. `N/A` is allowed only when `tdd_exempt: true`. `action` states its goal in `title` and lists one checklist item per acceptance criterion. Each item is an observable condition that a reader can check against evidence such as an id, link, command output, or count. An `action` has no function spec. Write the goal so re-running it is safe: inspect the current state, act only on what is missing.

**Normal scenarios**

- [ ] Scenario description: input `X`, expected output `Y`

**Boundary scenarios**

- [ ] Scenario description: when `X` is at a boundary value, expected output `Y`

**Exception scenarios**

- [ ] Scenario description: when `X` is invalid, expect to throw `ErrorType` or return `Y`

---

## Section 2: Function Specs

> **coding only.** Omit this section for `action`. Acceptance criteria come first. Read code only for the signature being specified.
>
> **Writing constraints**: One block per changed function. `Signature` lists every parameter with its type, then the return type.

```
Function name: <function_name>
Signature:     (<param>: <type>, <param>: <type>) → <return type>
Responsibility: one sentence describing what the function does
Side effects:  <none / describe side effects>
```

---

## Section 3: Constraints (hard implementation rules, copied from tech-doc)

> **Nature**: Must be followed. A `coding` task that breaks one does not meet the cited rule. An `action` task that breaks one does not meet the cited rule.
>
> **Writing constraints**: Each constraint cites its `tech-doc §N`; a rule with nothing to cite goes to Section 4 or is dropped.

- Constraint 1: <rule text> (tech-doc §N)  
- Constraint 2: <rule text> (tech-doc §N)  

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
