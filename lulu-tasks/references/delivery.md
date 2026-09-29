# Delivery

Hand off the admitted work order. `$TT_FLOW` is already defined.

## Script Macros

| Macro | Command |
|-------|---------|
| `$TT_DELIVER` | `$TT_FLOW deliver` |

## Rules

1. Read `../_transitions.md`.
2. Feature runs `$TT_DELIVER` and outputs `task_paths`. Start `lulu-exec` for the delivered work order. `coding` and `verify` tasks both enter that session.
3. Topic waits for an explicit delivery confirmation, then runs `$TT_DELIVER` and outputs `task_paths`.
