# Preparing

Bind each work-order `target_repo` to a listed checkout, persist the map, then prepare isolated worktrees.

## Script Macros

| Macro | Command |
|-------|---------|
| `$TC_LIST_REPOS` | `python3 "$SKILL_DIR/scripts/tc_repo_map_control.py" --cycle-dir "$CACHE_DIR/$CYCLE_ID" list-candidates` |
| `$TC_PUT_REPOS` | `python3 "$SKILL_DIR/scripts/tc_repo_map_control.py" --cycle-dir "$CACHE_DIR/$CYCLE_ID" put-map` |
| `$TC_PREPARE` | `python3 "$SKILL_DIR/scripts/tc_prepare.py" --cycle-dir "$CACHE_DIR/$CYCLE_ID"` |

Subcommand contracts: module docstring / `--help`.

## Steps

1. Run `$TC_LIST_REPOS`. Pin `candidates` from stdout.
2. Bind every task `target_repo` to one candidate `path`. If a name has no candidate, ask. Tasks without `target_repo` need no bind.
3. Run `$TC_PUT_REPOS` with binds on stdin (`{}` when no task has a `target_repo`).
4. Run `$TC_PREPARE`. Non-zero → Blocking policy.
5. Return to the entry router.

`$TC_PREPARE` owns worktree get-or-create and Preparing → Executing.
