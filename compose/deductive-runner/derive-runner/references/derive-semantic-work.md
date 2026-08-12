# Derive semantic work (Floor · Ceiling · Cascade)

Load only from `derive-runner` Execution after Prepare.
Session vars and macros: `../SKILL.md` (Prepare · Script Macros).

Main path: Floor Loop → Ceiling. Cascade: after Ceiling append, `edge-scan`;
holes → Floor Loop then full Ceiling again.

## Floor Loop

Scope: lenses in `$VAR_EDGE_HOLES` (not full `$VAR_LENS_ORDER`).
KW does **not** apply. Floor-internal re-enter ≤ **3** (separate from Cascade).

1. `$DERIVE_CTL edge-scan` → bind `$VAR_EDGE_HOLES` ← `edge_holes`.
2. For each lens in the hole table: projectable from decided substance → emit
   derived  
   `{text, lens_tags:[L], origin:{type:derived, ref:[upstream F-id, …]}, source?}`  
   with **exact** upstream `F-id` in `origin.ref` (prefer `source`).
3. Not projectable → `$DEDUCTIVE_CTL pending-add` (kind=`edge_hole`).
4. After that lens’s derived batch (if any) → `$DERIVE_CTL append`
   `--derived-file` (one lens per batch; CLI has no `--lens`).
5. Re-run step 1; continue until no new holes and no new append, or Floor
   re-enter count hits **3** (leftover holes → `pending-add` kind=`edge_hole`).
6. Exit to Ceiling even if Floor hit the cap (pending may remain open).

## Ceiling

No self-loop. Walk **required** lenses in `$VAR_LENS_ORDER` order (skip
`presence=optional`). Finish the full required pass before Cascade.

For each required lens `L`:

1. `$DERIVE_BUILD_CTL lens-bundle --lens L …` → that lens’s KW slice + material
   facts (`--help`).
2. Thickness ruler: returned `kw_criteria` only (no session-wide KW var).
3. Materials: returned `facts` (Ceiling pool; already filtered).
4. Judgment: whether those facts satisfy that lens’s KW rows (agent semantic).

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
6. When Means yields derived for `L` → `$DERIVE_CTL append` (one lens batch)
   before the next required lens. Do **not** Cascade mid-pass.

## Cascade (re-entry)

Enter only when this Ceiling pass performed ≥1 `$DERIVE_CTL append`.

1. `$DERIVE_CTL edge-scan` → rebind `$VAR_EDGE_HOLES` (never reuse a stale
   hole snapshot).
2. No holes → Cascade ends.
3. Holes and Cascade re-enter count still under **3** → Floor Loop → Ceiling
   **full** required pass again → may re-enter Cascade.
4. Cascade re-enter ≤ **3**; at cap with leftover holes →
   `$DEDUCTIVE_CTL pending-add` (kind=`edge_hole`) then stop Derive semantic
   work (Persist validate).
5. Later Ceiling passes see facts appended earlier.

## Emit invariants

1. **Must not** produce `origin.type=discovered`.
2. **Do not** batch-retag quarantine/not_needed.
