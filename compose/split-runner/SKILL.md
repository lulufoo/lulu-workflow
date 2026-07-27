---
name: split-runner
description: >-
  Pre-inductive multi-subdesign split for compose (lulu-design Lx packages).
  Intake → split-or-not → propose tree+rulers → human lock. Invoked from compose
  Step 0.1; does not own runtime $L_SLICE scheduling.
---

# split-runner

Run only when compose Drafting Step 0.1 dispatches multi-subdesign split for an Lx package layout. Observable done: `$MULTI_SLICE check-split-ready` exits 0.

**Must:** fill intake slots (or `N/A`); recommend split with reasons; enforce plan-self-sufficiency veto; lock tree + rulers (multi-L) via `$MULTI_SLICE` only.  
**Must not:** begin inductive; switch focus; hand-edit locked JSON; invent package-bucket facts; implement tree unlock/re-split (immutable this iteration); present the full eight-slot projection table to the user for review.

## Parent-Provided Inputs

| Variable | Purpose |
|---|---|
| `$REVISION_DIR` | Absolute path to `revision{N}/` |
| `$CYCLE_ID` | Active cycle id |
| `$COMPOSE_PROFILE` | Compose profile id |

Self-resolved: `$PROJECT_ROOT` = `$(pwd)`.

## Script Macros

| Macro | Command |
|-------|---------|
| `$MULTI_SLICE` | `python3 "$SKILL_ROOT/compose/scripts/core/multi_slice_control.py" --revision-dir "$REVISION_DIR" <subcommand>` |

Subcommands: `--help`. Contracts live in the control module / `--help` only.

## Intake purposes (fixed)

1. Split subdesigns accurately (whether to split, cut axis, nodes/edges).  
2. Build each subdesign boundary ruler.

## Intake slots (v1 minimum)

`package_boundary` · `cut_axis_preference` · `modules` · `deps_order` · `plan_autonomy` · `seam_ownership` · `non_goals` · `split_risks`  
Empty without explicit `N/A` → do not advance past Step 0 / do not lock.

## Split standards (summary)

- **Soft recommend:** emit `recommend_split` + reasons; human may override with a recorded reason.  
- **Hard veto:** any proposed L that cannot stand alone as an implementation plan → reject that cut.  
- **Cut axis:** declare exactly one primary `cut_axis` for the tree.  
- **Rulers (multi-L):** each L needs `job`, `in[]`, `out[]`, `seam[]` (`owns`: `full_plan`|`depend_only`), `plan_checklist[]`. Dual `full_plan` on a seam → reject.

## Execution Contract

### Step 0 — Intake

1. `$MULTI_SLICE check-root-facts` — on failure: `$MULTI_SLICE migrate-root-facts --confirm` (or user removes root facts), then re-check.  
2. **Silently** project upstream decision into the eight slots. Do **not** show the slot table or ask the user to review a full dump.  
3. `$MULTI_SLICE write-intake --intake-json '<json>'` (status stays draft).  
4. If any slot is missing or ambiguous: enter **targeted Q&A only for those gaps** (one concern at a time). Write updates via `write-intake` after each batch of answers.  
5. When all slots are filled or explicitly `N/A`: `$MULTI_SLICE complete-intake --confirm` (no separate “please confirm the eight slots” step). Proceed to Step 1.

### Step 1 — Split-or-not

1. Apply trigger/veto standards; present `recommend_split` + `reasons[]` (+ optional suggested cut axes).  
2. Human chooses single vs multi (override allowed with reason — store in intake `override_reason` via another `write-intake` if needed, then `complete-intake` again only if slots still complete).

### Step 2 — Propose

1. Draft dependency tree JSON (`nodes` / `edges` / `order`).  
2. Multi-L: draft `slice-rulers` JSON with `cut_axis` + per-L rulers; refuse cuts that fail plan-self-sufficiency or dual-SSOT.  
3. Single-L: tree with only `L1`; rulers optional (exempt).

### Step 3 — Human lock

1. Human confirms tree (+ rulers when multi-L).  
2. Lock:
   - Single-L: `$MULTI_SLICE lock-tree --tree-json '<tree>' --confirm`  
   - Multi-L: `$MULTI_SLICE lock-tree --tree-json '<tree>' --rulers-json '<rulers>' --confirm`  
3. `$MULTI_SLICE check-split-ready` — non-zero → Blocking; do not return to inductive.

## Completion

Return to compose Step 0.1 when `check-split-ready` is ok. Compose owns inductive / `$L_SLICE` afterward.
