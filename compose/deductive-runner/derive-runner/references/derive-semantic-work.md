# Derive semantic work (floor · ceiling × KW · cascade)

Load only from `derive-runner` Execution. Mutations via `$DERIVE_CTL` /
`$DEDUCTIVE_CTL` / `$FACTS_CTL` only.

## Bindings

| Name | Source |
|------|--------|
| `KW_CRITERIA` | `section_kw_criteria` from `$DERIVE_BUILD_CTL context` stdout |
| `order`, `edge_holes`, `true_gaps`, `materials_total` | `$DERIVE_CTL plan-edge` stdout |

## Floor (means only — no KW)

Scope: each hole in `edge_holes`.

1. Projectable from decided substance → emit derived  
   `{text, lens_tags:[L], origin:{type:derived, ref:[upstream F-id, …]}, source?}`  
   with **exact** upstream `F-id` in `origin.ref` (prefer `source`).
2. Not projectable → `$DEDUCTIVE_CTL pending-add` (kind=`edge_hole`).
3. KW upper/target does **not** apply here.

## Ceiling × KW ruler

Scope: each required lens in topo order (same `order`, then any remaining
required).

### Pool and ruler

1. Materials: **carried** (and legacy no-disposition) + Intent — **not** default
   `quarantined` / `not_needed` pool.
2. Ruler: that lens’s block in `KW_CRITERIA` (published table only; **no**
   separate target-thickness number).
3. Judgment: whether current facts satisfy the table’s “can state…” rows (agent
   semantic judgment).

### Branch

| State | Action |
|-------|--------|
| Satisfied | Stop thickening that lens (KW stop line). |
| Unsatisfied | Drive means (§ Means); then re-judge. |
| Means exhausted and still unsatisfied | `$DEDUCTIVE_CTL pending-add` (kind=`kw_shortfall`, `--lens <L>`, summary = table gap). Do **not** silently pass. |

### Means (when unsatisfied)

1. List Intent should-cover / thicken opportunities.
2. Emit `derived` with `F-id` refs only if **all** hold: projectable · on a
   `decompose` / `instantiate` edge · not past the depth the table asks for.
3. Gap recovery when still thin (order): carried → quarantined ledger →
   not_needed ledger → pending.
4. Off-edge / undecided → `$DEDUCTIVE_CTL pending-add`
   (kind=`off_edge` \| `undecided`) — **never** `origin.type=derived` off-edge.
5. **Forbidden:** inventing to pad KW with no edge.

## Cascade

1. Later lenses see facts appended earlier.
2. New `edge_holes` from ceiling appends → re-run Floor for those holes (**still
   no KW**) → resume Ceiling × KW for affected lenses.

## Emit invariants

1. **Must not** produce `origin.type=discovered`.
2. **Do not** batch-retag quarantine/not_needed (no disposition-patch here).
