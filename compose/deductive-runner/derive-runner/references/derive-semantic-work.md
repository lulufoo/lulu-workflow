# Derive semantic work (Floor · Ceiling · Cascade)

Load only from `derive-runner` Execution after Prepare.
Session vars and macros: `../SKILL.md` (Prepare · Script Macros).

Main path: Floor → Ceiling. Cascade: re-enter Floor then Ceiling when new holes
appear.

## Floor

Scope: each hole in `$VAR_EDGE_HOLES`.

1. Projectable from decided substance → emit derived  
   `{text, lens_tags:[L], origin:{type:derived, ref:[upstream F-id, …]}, source?}`  
   with **exact** upstream `F-id` in `origin.ref` (prefer `source`).
2. Not projectable → `$DEDUCTIVE_CTL pending-add` (kind=`edge_hole`).
3. KW upper/target does **not** apply here.

## Ceiling

Scope: each required lens in topo order (same `$VAR_ORDER`, then any remaining
required). Thickness ruler: `$VAR_KW_CRITERIA` only.

### Pool and ruler

1. Materials: **carried** + Intent — **not** default `quarantined` /
   `not_needed` pool.
2. Ruler: that lens’s block in `$VAR_KW_CRITERIA` (published criteria only; **no**
   separate target-thickness number).
3. Judgment: whether current facts satisfy that lens’s rows in
   `$VAR_KW_CRITERIA` (agent semantic judgment).

### Branch

| State | Action |
|-------|--------|
| Satisfied | Stop thickening that lens (KW stop line). |
| Unsatisfied | Drive means (§ Means); then re-judge. |
| Means exhausted and still unsatisfied | `$DEDUCTIVE_CTL pending-add` (kind=`kw_shortfall`, `--lens <L>`, summary = table gap). Do **not** silently pass. |

### Means

1. List Intent should-cover / thicken opportunities.
2. Emit `derived` with `F-id` refs only if **all** hold: projectable · on a
   `decompose` / `instantiate` edge · not past the depth the table asks for.
3. Gap recovery when still thin (sequence): carried → quarantined ledger →
   not_needed ledger → pending.
4. Off-edge / undecided → `$DEDUCTIVE_CTL pending-add`
   (kind=`off_edge` \| `undecided`) — **never** `origin.type=derived` off-edge.
5. **Forbidden:** inventing to pad KW with no edge.

## Cascade (re-entry)

Applies when Ceiling appends create new holes.

1. Later lenses see facts appended earlier.
2. New `$VAR_EDGE_HOLES` → re-enter Floor then Ceiling for affected lenses.

## Emit invariants

1. **Must not** produce `origin.type=discovered`.
2. **Do not** batch-retag quarantine/not_needed.
