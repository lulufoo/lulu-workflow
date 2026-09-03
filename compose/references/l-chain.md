# l-chain

Navigate the ordered L chain while the session is `Working`. Running one L
is `l-execution.md`; this reference owns focus, order, and freezing.

## Loop

Run `$L_SHELL status` and follow `next_actions`. Never derive legal actions
from the ledger. On inner failure → Blocking; do not move focus.

## Actions

| Action | Do | Rule |
|---|---|---|
| Execute | Load `l-execution.md`; follow it until the focus is `Completed` | One focus at a time |
| Reopen | `l-execution.md` § Reopen | — |
| Advance | `$L_SHELL advance`, no confirm. `alignment_required` → Align; `ready-for-delivery` → Exit | Only to the direct successor; never skip |
| Align and unfreeze | Read-only: does the frozen successor still hold given the completed prefix? If yes, `$L_SHELL unfreeze --expected-fingerprint <stdout fingerprint> --confirm` | Align before unfreezing |
| Backtrack | `$L_SHELL backtrack --target Lx --confirm`, then `l-execution.md` § FreeEdit | Reached suffix freezes; state and document preserved |
| View | `$L_SHELL view --target Lx`; any macrostate; zero writes | — |

## Exit

Leave Working only when every L is `Completed` and unfrozen. Confirm, then
`$SESSION_CONTROL ready-for-delivery`. On failure → Blocking.
