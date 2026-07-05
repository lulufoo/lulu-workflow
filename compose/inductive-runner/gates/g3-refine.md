> Part of inductive-runner · gate execution entry · loaded from `../SKILL.md`

# Gate 3 — Refine (frontier sweep)

**Prerequisites:** `$INDUCTIVE_GATE_CTL resolve-context` reports `active_gate` is `G3` (G2 closed with `verdict=ok`).

**Goal:** refine the shape artifact by **frontier sweep** — each sweep surfaces every unsettled section's *coarsest* open point (at its current `frontier_kw`); the user expands and decides points one at a time, each decision is appended to its section bucket, then the user re-sweeps. Sweeps repeat (recomputing each section's frontier) until every section reaches its target maturity. (Why the sweep shape, not section-at-a-time: `../SKILL.md` § Method.)

**Setup:** breadth = `SCAN_CRITERIA.expose_axis.coverage_sections` (checklist + default order; sections **not** listed are **peeled** — covered by the Gate 1 shape or the deferred bucket, not discovered here); depth = per-section `frontier_kw` 0..4 (default leave at KW3). Discovery has two peer sources: **AI methods** (run the `methods` whose `sections` include the unsettled section at its `frontier_kw`) and **`human_inlet`** (the user proposes a point in any dimension, at any altitude, at any time — exempt from the `frontier_kw` filter; AI maps it to its owning section — full mapping + `register-ep` call in `../SKILL.md` § Roles & Global Rules). **KW is the ruler, not a loop** — a candidate is a real open point only if it leaves the section's current `frontier_kw` row of `KW_CRITERIA` false; the iteration unit is always the open point, never section × KW. Resume any turn via `$INDUCTIVE_GATE_CTL resolve-context`; all section/EP mutations go through `$INDUCTIVE_G3_SECTION_CTL` (subcommands + flags in its `--help`).

## Sweep spine

1. **Shallow-ground** (subagent, whole sweep) → gate: `grounding-check --sweep K` passes.
2. **Discover + register** — run methods across all unsettled sections using sweep receipts as fuel; register ≥1 open EP per unsettled section surfaced this sweep.
3. **Present frontier map** — each unsettled section's coarsest open point (problem + leaning), handed back as exploration, not a menu.
4. **Expand one chosen point:**
   - **4a. Deep-ground it** (subagent, one point) → gate: fetch its receipt via `deep-grounding-list`.
   - **4b. Form leaning → user decides** → `update-ep` (resolved/deferred) → `append-to-section`.
5. **Advance maturity** — `set-frontier` the section to its new KW.
6. **Re-sweep or clear** — re-sweep (→ step 1) or `clear-section` once a section reaches target with no blocking-open EP.

### Step 1 — Shallow-ground (subagent, whole sweep)

Dispatch `g3-shallow-grounding-runner` via `$SUBAGENT_TOOL` with `$SUBAGENT_AWAIT_SYNC`:

```text
Load {actual $SKILL_ROOT}/compose/inductive-runner/g3-shallow-grounding-runner/SKILL.md and follow its instructions.

## Input
SWEEP: <K>
INDUCTIVE_OUT_DIR: {actual $INDUCTIVE_OUT_DIR}
COMPOSE_PROFILE: {actual $COMPOSE_PROFILE}
CYCLE_ID: {actual $CYCLE_ID}
PROJECT_ROOT: {actual $PROJECT_ROOT}
```

Then run `$INDUCTIVE_GATE_CTL grounding-check --sweep <K>` **once** — immediately after the subagent returns, as the gate before step 2. Must pass before step 2. **Do not** re-run `grounding-check` later in the same sweep (e.g. after `set-frontier`) — receipts are frozen at grounding-time `frontier_kw`; advancing a section invalidates its sweep-K receipt for re-check; only a new sweep's step 1 re-validates. **Ignore** the subagent Task return beyond confirming completion — fuel step 2 only via `$INDUCTIVE_GATE_CTL grounding-list --sweep <K>`. **Do not** read source inline in step 1.

### Step 2 — Discover + register

For each unsettled section S, run S's methods at its `frontier_kw` **using only** sweep receipts from step 1 — **do not** inline-read source again in this step (re-read happens only in step 4a for the chosen point). Keep a candidate only if it leaves **the `frontier_kw` row of S in `KW_CRITERIA`** false — a concern that belongs to a deeper KW row is *not* in scope this sweep (it surfaces in a later sweep once S advances). **First subtract the shape constraints** (Gate 1 confirmed claims): a point those already settle is not an open point — do not re-surface it with shape-contradicting options; if a constraint settles only part of a point, keep the open residue. Discovery may scan any section (read-only); **registering** a point requires activating that section (mutation focus guard). (`human_inlet` points are exempt from this `frontier_kw` filter — see `../SKILL.md` § Roles & Global Rules.)

**Register before you present (mandatory):** for each open point kept from discovery, `activate-section` its section, then `register-ep --json` with `status: open` **before** step 3. Step 3 presents EPs already in `exposed-points.json` — not a substitute for registration. The frontier map needs at least one registered open EP per unsettled section surfaced this sweep (or an explicit `deferred` EP if the user already chose to skip).

> EP field contract + allowed values live in `inductive_exposed_points_schema.py` (no `tier` field). Orchestration bindings: `section` must equal `active_section`; `method` is the surfacing method ID or `human_inlet`; `kw` is the KW criterion it leaves false.

### Step 3 — Present frontier map

Present **each unsettled section's coarsest open point** (one per section, keyed to its registered EP id) as two paired parts:
- **the problem, stated plainly** — worded at that section's `frontier_kw` altitude from `KW_CRITERIA` (e.g. at KW1 just *name which decision / constraint / contract is undecided*); **no signatures, counts, or `file:line` evidence in this part** — that depth belongs to step 4a;
- **my reading / leaning (接地)** — a grounded recommendation that *may* carry the concrete detail (signature, count, code anchor) the problem line withholds. This is where exploration touches ground; it never replaces the user's decision.

The problem part describes; the leaning part grounds. This is the coarse, roughly uniform-resolution view of the whole change; earlier sweeps' deeper figures stay as the map — never overwrite them. Hand it back to the driver as exploration, not a quiz: *"I explored each dimension — these are the coarsest open problems I found and my reading of each; you decide which to deepen, skip, or add one I missed."* — never "pick option A/B/C".

### Step 4 — Expand one chosen point

The user picks a point to expand, skips it, or proposes one via `human_inlet`. For the chosen point, `activate-section` its section, then:

**4a. Deep-ground it (subagent, one point):** dispatch `g3-deep-grounding-runner` via `$SUBAGENT_TOOL` with `$SUBAGENT_AWAIT_SYNC`:

```text
Load {actual $SKILL_ROOT}/compose/inductive-runner/g3-deep-grounding-runner/SKILL.md and follow its instructions.

## Input
EP_ID: {actual EP id}
SECTION: {actual active_section}
FRONTIER_KW: {actual frontier_kw}
PROBLEM: {actual one-line problem statement from step 3}
SWEEP: {actual current sweep number}
INDUCTIVE_OUT_DIR: {actual $INDUCTIVE_OUT_DIR}
COMPOSE_PROFILE: {actual $COMPOSE_PROFILE}
CYCLE_ID: {actual $CYCLE_ID}
PROJECT_ROOT: {actual $PROJECT_ROOT}
```

Then run `$INDUCTIVE_GATE_CTL deep-grounding-list --sweep <K> --ep-id <EP_ID>` **once** — immediately after the subagent returns — to fetch its receipt as fuel for 4b. **Ignore** the subagent Task return beyond confirming completion. **Do not** read source inline for this point — that is the deep-grounding-runner's job (targeted Read only, no whole-file reads).

**4b. Form leaning → user decides:** AI gives leaning + rationale + implication, grounded in the 4a receipt's `facts` / `code_refs`, → user decides → `update-ep --status resolved` + `resolution`, then `append-to-section` folds the decision into that section's figure. Skipped → `update-ep --status deferred`.

### Step 5 — Advance maturity

Once a section's points for this sweep are resolved/deferred, `set-frontier` it to its new KW.

### Step 6 — Re-sweep or clear

The user re-sweeps (recompute frontiers → step 1; the map deepens), or — for any section that reached the target with no blocking-open EP — confirms `clear-section`. A blocking-open EP, an unmet frontier, or an empty bucket blocks `clear-section` (hard gate at clear, not at navigation).

**Mandatory coverage:** `$SCAN_CRITERIA.mandatory_coverage_prompt` sections must reach `cleared` or `skipped` before G3 can close. For any with no discovered point, explicitly ask whether a coverage point should be added for this section — the guaranteed hearing for `human_inlet`.

**Close criterion:** call `$INDUCTIVE_G3_SECTION_CTL check-coverage` — all `coverage_sections` are `cleared` or `skipped`, no `(blocking ∧ open)` EP remains, mandatory sections covered; then call `$INDUCTIVE_GATE_CTL gate-close --gate G3 --payload '{...}'` after user confirms the view is detailed enough.
