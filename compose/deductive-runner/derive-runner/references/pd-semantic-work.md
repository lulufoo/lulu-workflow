# Pd semantic work (floor · ceiling × KW · cascade)

Load only from `derive-runner` Execution. Session cognition for means; mutations
still via `$DERIVE_CTL` / `$DEDUCTIVE_CTL` / `$FACTS_CTL` in the parent SKILL.

`KW_CRITERIA` = `section_kw_criteria` from `$DERIVE_BUILD_CTL context` stdout.
Plan fields (`order`, `edge_holes`, …) = `$DERIVE_CTL plan-edge` stdout.

## Floor (means only — no KW)

For each hole in `edge_holes`: if projectable from decided substance → emit
derived fact `{text, lens_tags:[L], origin:{type:derived, ref:[upstream F-id, …]}, source?}`
with **exact** upstream `F-id` in `origin.ref` (and prefer `source`). If not
projectable → `$DEDUCTIVE_CTL pending-add` (kind=`edge_hole`). KW upper/target
does **not** apply here.

## Ceiling × KW ruler

For each required lens in topo order (same `order`, then any remaining required):

- Materials: **carried** (and legacy no-disposition) + Intent — **not** default
  `quarantined`/`not_needed` pool.
- Ruler: that lens’s block in `KW_CRITERIA` (published table only; **no**
  separate target-thickness number).
- Estimate whether current facts satisfy the table’s “can state…” rows (agent
  semantic judgment).
- **If unsatisfied** → drive ceiling means: list Intent should-cover / thicken
  opportunities; projectable **and** on a `decompose`/`instantiate` edge **and**
  not past the depth the table asks for → `derived` with `F-id` refs. Gap
  recovery when still thin: carried → quarantined ledger → not_needed ledger →
  pending. Off-edge / undecided → `$DEDUCTIVE_CTL pending-add`
  (kind=`off_edge` \| `undecided`) — **never** `origin.type=derived` off-edge.
  **Forbidden:** inventing to pad KW with no edge.
- **If satisfied** → stop thickening that lens (KW stop line).
- **If means exhausted and still unsatisfied** → `$DEDUCTIVE_CTL pending-add`
  (kind=`kw_shortfall`, `--lens <L>`, summary = table gap). Do **not** silently
  pass.

## Cascade

Later lenses see facts appended earlier. If ceiling appends create new
`edge_holes`, re-run floor for those holes (**still no KW**), then resume
ceiling×KW for affected lenses. Complete cascade in this subagent run (parent
does not re-dispatch mid-cascade).

## Origin

**Must not** produce `origin.type=discovered`.
