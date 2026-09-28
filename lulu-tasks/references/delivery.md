# Delivery

Hand off the admitted work order. `$TT_FLOW` is already defined.

## Script Macros

| Macro | Command |
|-------|---------|
| `$TT_DELIVER` | `$TT_FLOW deliver` |

## Rules

1. Read `../_transitions.md`.
2. Feature runs `$TT_DELIVER` and outputs `task_paths`. Start `lulu-code` only for tasks whose `kind` is `coding`. `verify` tasks in the same work order do not enter `lulu-code`.
3. Topic waits for an explicit delivery confirmation, then runs `$TT_DELIVER` and outputs `task_paths`.
