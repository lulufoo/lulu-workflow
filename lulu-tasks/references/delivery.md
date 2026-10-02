# Delivery

Hand off the admitted work order. `$TT_FLOW` is already defined.

## Script Macros

| Macro | Command |
|-------|---------|
| `$TT_DELIVER` | `$TT_FLOW deliver` |

## Rules

1. Read `../_transitions.md`.
2. Run `$TT_DELIVER` and output `task_paths`. Start `lulu-exec` for the delivered work order. `coding` and `action` tasks both enter that session.
