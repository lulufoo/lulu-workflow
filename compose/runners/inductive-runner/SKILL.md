---
name: inductive-runner
description: >-
  Pre-compose inductive investigation runner for compose stages. Cold-starts a
  coarse architecture view from the upstream scope doc (e.g. decision-doc),
  validates it against code in the background, then refines it section by section
  along a coarse-to-fine ladder (user-driven, AI-recommended) and recomposes
  per-section, code-anchored scope files for compose Initializing.
---

# inductive-runner

Run this sub-skill only when dispatched from a compose stage `start` (inductive path) — e.g. `lulu-design`.

Produces per-section scope files under `inductive-scope/` (one `<SECTION>.md` per touched section) and `inductive-dqi.json` under the active revision dir (`revision{active_doc}/`). Compose Initializing reads each section's slice on demand (per-section grounding) — there is no merged document.
After completion, control returns to the parent compose stage to proceed with compose Initializing.

This runner is **stage-agnostic**: `coverage_sections`, section weights, and discovery `methods` are profile data fetched as `inductive-scan-criteria` — the authoritative list is whatever the fetched criteria declare.

---

## Dispatch Inputs (from parent compose stage)

The parent passes these in the `## Input` block; do not hardcode stage paths.

| Var | Meaning |
|-----|---------|
| `$COMPOSE_PROFILE` | Compose profile id (drives every `$FETCH_COMPOSE`) |
| `$CYCLE_ID` | Active cycle id |
| `$SCOPE_DOC` | Upstream scope SSOT path — the 派生父级 (Gate 1 reads this; Gate 5 axis reuses it — e.g. `decision-doc.md`) |
| `$INTENT_BASELINE_REFS` | JSON array of 意图基准 refs (e.g. `lulu-spec`); empty → Gate 5 algorithm A is skipped |
| `$NORM_CONSTRAINT_REFS` | JSON array of 规范约束 refs (stage-level); empty → Gate 5 algorithm C is a no-op |
| `$INDUCTIVE_OUT_DIR` | Active revision dir (`revision{active_doc}/`) for inductive state bundle |

## Session Paths (derived)

```
INDUCTIVE_DIR         = $INDUCTIVE_OUT_DIR/inductive-scope          # per-section scope files (the only scope artifacts init reads)
INDUCTIVE_DQI         = $INDUCTIVE_OUT_DIR/inductive-dqi.json
INDUCTIVE_GATE_STATE  = $INDUCTIVE_OUT_DIR/inductive-gate-state.json
INDUCTIVE_SECTION_PTR = $INDUCTIVE_OUT_DIR/inductive-section-pointer.json
INDUCTIVE_EP_LEDGER   = $INDUCTIVE_OUT_DIR/exposed-points.json
INDUCTIVE_GROUNDING   = $INDUCTIVE_OUT_DIR/grounding-notes.json
INDUCTIVE_G2_REPORT   = $INDUCTIVE_OUT_DIR/g2-topology-report.json
INDUCTIVE_G4_REPORT   = $INDUCTIVE_OUT_DIR/g4-recompose-report.json
PROVENANCE_GATE_STATE = $INDUCTIVE_OUT_DIR/provenance-gate-state.json
PROVENANCE_TRACES     = $INDUCTIVE_OUT_DIR/provenance-trace-{intent,scope,norm}.json   # Gate 5 deltas, one per role
```

---

## Script Macros

| Macro | Command |
|-------|---------|
| `$FETCH_COMPOSE` | `python3 "$SKILL_ROOT/compose/scripts/io/fetch_compose_framework.py" --role <role> --profile "$COMPOSE_PROFILE" --project-root "$(pwd)" --cycle-id "$CYCLE_ID"` |
| `$INDUCTIVE_GATE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/inductive_gate_control.py" --out-dir "$INDUCTIVE_OUT_DIR"` |
| `$INDUCTIVE_G3_SECTION_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/inductive_g3_section_control.py" --out-dir "$INDUCTIVE_OUT_DIR"` |
| `$PROVENANCE_GATE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/provenance_gate_control.py" --out-dir "$INDUCTIVE_OUT_DIR"` |

Fetch schedule (do not read `workflow-config.json` directly):
- **At Gate 1 start:** `$FETCH_COMPOSE --role inductive-scan-criteria` → `SCAN_CRITERIA`: Gate 1 shape field specs (`shape_extraction.fields`) and Gate 3 configuration (`expose_axis` — coverage axis, methods + weights, KW semantics, mandatory coverage).
- **Before Gate 3:** `$FETCH_COMPOSE --role section-form-registry` → the per-section carrier vocabulary (`sections.{key}.presentation`); `$FETCH_COMPOSE --role section-kw-criteria` → `KW_CRITERIA`: each section's per-KW intent rows (`## {section}` → KW0..KW4 "verifiable intent attributes"). `KW_CRITERIA` is the **altitude register** — the row at a section's current `frontier_kw` is what an open point is selected against and worded at (Gate 3 step 2/3). (`SCAN_CRITERIA` already loaded from Gate 1.)

---

## Method (why a gate spine, not a section checklist)

Producing scope is an **inductive** task: from the upstream scope doc + observed reality, *discover* what design decisions are still missing. This is parts → whole inference, not whole → parts derivation.

`section-registry` is a **completeness predicate over a finished document** — the deductive instrument that compose uses downstream to expand a known scope. A predicate can *test* and *attribute*, but it cannot *generate* substance or tell you what to examine. So here it is used **only inside Gate 3** as the coverage + attribution axis — never as the driver.

The driver is the gate spine below. Sections enter at Gate 3 as a destination, never at Gate 1 as a starting point.

**One shape artifact, refined by frontier sweep, persisted per section.** A single **shape artifact** (named per `SCAN_CRITERIA.shape_extraction.artifact_label`) is the carrier. It starts coarse (Gate 1), is validated against code in the background (Gate 2), then refined in Gate 3 by **frontier sweep**: each sweep surfaces every unsettled section's *coarsest* open point — at that section's current **frontier KW** — and advances all sections' maturity together, so the whole view sharpens at a roughly uniform resolution rather than one section being drilled to KW3 while the rest stay blank. `SCAN_CRITERIA.expose_axis.coverage_sections` supplies the coverage checklist + default order. Convergence is felt as the whole figure getting finer **sweep by sweep** — not as a summary, then an audit, then a flat checklist.

**Two axes, not one "tier".** The descent has two independent axes: **across sections** = a **coverage / breadth axis** (crossing sections changes *design dimension*, not resolution) and **within a section** = the **KW gradient** (the only coarse → fine / granularity axis; `frontier_kw` 0..4). There is no separate "tier" enum — the iteration unit is one open point, and granularity is KW.

**Each section owns its own figure, deepening across KW.** A section's figure deepens across KW levels as successive sweeps revisit it; other sections' figures stay intact as the map — never overwrite another section's figure. Each figure is drawn in the **carrier its section prescribes** (`section-form-registry.presentation.allowed`). This is what stops every step from being described in `file:line` code prose (`presentation.forbidden`). Because each figure belongs to a section, the figure stack lands naturally **per section** — appended to that section's bucket, which is also how the output is stored and how compose Initializing loads it.

**methods discover, KW judges.** `methods` are the discovery action: at a section they emit candidate gaps. **KW is a ruler, not a loop** — a candidate is a real open point only if it leaves one of the section's KW criteria false, and KW also decides when the section is clear enough to leave (default KW3). The iteration unit is the open point, never section × KW.

**Shape claims are constraints, not re-openable questions.** The Gate 1 load-bearing claims, once confirmed, become invariants. Gate 3 discovery **subtracts** what they already fix — it does not re-surface a settled call as an open point with shape-contradicting options.

Understanding a design is itself a process: the user resolves a sweep's open points, then chooses to re-sweep. So the descent is **user-driven**: each sweep AI presents the **frontier map** — every unsettled section's coarsest open point, fueled by background grounding; the user picks which point to expand, may skip, may inject a point AI missed, and decides when to re-sweep and when the whole view is detailed enough.

---

## Pipeline

**Gate 1 Shape → Gate 2 Grounding (background) → Gate 3 Refine (frontier sweep) → Gate 4 Recompose → Gate 5 Provenance**

The gates progressively refine the **same shape artifact** from coarse to fine. Each gate has an observable close criterion. Do not advance until it is met.

---

## Roles & Global Rules

- **Collaboration baseline (load-bearing — never violate).** AI leads **cognition** (explore via scan + on-demand grounding, think it through, surface the problems, offer a grounded leaning) and **leads the spine** — it knows the next gate. The **user leads decision and progress**: which point to deepen, whether to skip, when to re-sweep, when to stop. Each sweep AI exposes the **frontier map** — every unsettled section's coarsest open point — as recommendations. AI output is therefore **always an exploration finding + leaning**, phrased *"I lean X because…; the implication is…; expand this?"* — never a multiple-choice menu the user merely answers, never a verdict.
- **Who fixes what (load-bearing — never violate).** Every *how-to-fix* decision is the **user's**. The **AI only recommends** (leaning + rationale + implication). The **scripts only move state and keep the ledger** — never a semantic judgement about content. **Gate 4 only finds and names problems; it never fixes them.** A fix is always made back in the gate that owns it (Gate 3 for a section, Gate 1 for shape), through the normal AI-recommends → user-decides loop — never auto-applied and never patched inside the auditor.
- **Two-layer focus guard.** Sections are peers; `activate-section <S>` is always permitted. **Discovery is global (read-only):** a sweep may scan *all* unsettled sections to build the frontier map. **Mutation is focus-guarded:** every state-mutating operation (`register-ep`, `update-ep`, `set-frontier`, `append-to-section`, `clear-section`, `skip-section`) must target the `active_section` — run `$INDUCTIVE_G3_SECTION_CTL activate-section --section <S>` first to shift focus. You may *see* a gap in any section during a sweep, but to *register/decide* it you must activate that section.
- **`human_inlet` is a peer discovery source, not a safety net.** The user may raise a design point in **any dimension, at any altitude, at any time** — on equal footing with the AI-scan frontier map. It is **AI's job to map** that free-form point to its owning section: run `$INDUCTIVE_G3_SECTION_CTL activate-section --section <mapped S>` first, then `register-ep --json '{"source":"human_inlet","method":"human_inlet","kw":"<KW criterion it leaves false>",...}'` (the mutation focus guard still applies — the EP lands under the mapped `active_section`). A `human_inlet` point is **exempt from the frontier-altitude filter** — it need not be the section's coarsest open point nor sit at the current `frontier_kw`; never reject it for being "off-frontier". If it maps to no `coverage_section` (it belongs to a peeled section or the shape), **say where it goes** — fold it into a shape constraint or the deferred bucket — never silently drop it. The remaining EP lifecycle (resolve/defer/fold into figure) is identical to an AI-scan EP.
- **One point at a time** — never batch multiple decisions into one prompt.
- **Session state persists across turns.** At the start of each new turn, call `$INDUCTIVE_GATE_CTL resolve-context` to restore `active_gate`, `active_section`, open-EP count, and `architecture_view`. Never rely on conversation memory alone.
- Fetch framework data per the schedule in **Script Macros** — never read `workflow-config.json` directly.

---

## Gate 1 — Shape (coarse shape artifact)

**Goal:** render the change as a coarse **shape artifact** (`SCAN_CRITERIA.shape_extraction.artifact_label`) — the cold-start structural abstraction, as one coherent whole. Do **not** examine implementation; do **not** organize by section; do **not** drop to implementation detail.

1. Read `$SCOPE_DOC` in full (use its decision conclusions as primary source).
2. Produce one **shape artifact** (the carrier every later gate refines).
   For each field in `SCAN_CRITERIA.shape_extraction.required` (and `.optional` where applicable): render using the field's `carrier`, obey its `forbidden`, and present `as_is`+`to_be` as a paired before→after block. Field labels, guidance, and render rules are in `SCAN_CRITERIA.shape_extraction.fields` — do not deviate from them.
3. Append the 1–2 **load-bearing claims you are least sure of**, restricted to **shape altitude** — the spine framing, a boundary call, a structural relation, or an implicit premise the source material can't tell you. **Do not** raise implementation risks here — those belong to Gate 3.

**Present:** the shape artifact (all `shape_extraction.required` fields + any applicable `.optional` fields, rendered per `shape_extraction.fields`) + the shape-level load-bearing claims.

**Close criterion:** the user confirms the spine, the To-Be structure, and the boundary (e.g. "形状确认" / "shape confirmed"). Corrections are folded in and the view re-presented until confirmed. On confirmation, call `$INDUCTIVE_GATE_CTL gate-close --gate G1 --payload '{"architecture_view": {...}, "shape_constraints": [...]}'` — this persists the `architecture_view` to the DQI, freezes the load-bearing claims into **shape constraints** (invariants Gate 3 must respect and must not re-open), and advances the spine to Gate 2.

**Session init (once per session, at Gate 1 start):** call `$INDUCTIVE_GATE_CTL init-session --sections <coverage_sections CSV> --mandatory <mandatory_coverage_prompt CSV> --cycle-id <cycle_id> --stage <compose stage>` to seed both the gate state and section pointer. Skip if resuming an existing session — `$INDUCTIVE_GATE_CTL resolve-context` will confirm the current active gate.

---

## Gate 2 — Grounding (background)

**Goal:** a fast, autonomous sanity-check that the confirmed shape's spine/topology is not fundamentally wrong. **Not** a user-facing audit; **not** an exhaustive line-level grounding (that happens lazily per section in Gate 3).

**Read discipline (context guard):** confirm existence and topology only — main blocks exist / can exist, key relations are plausible. **Do not** read whole files; **do not** drop to line-level or signature-level detail in persisted facts. Gate 2 source reads run in `g2-grounding-runner` subagent only — **do not** inline-read project source during G2.

1. **Topology ground (subagent):** dispatch `g2-grounding-runner` via `$SUBAGENT_TOOL` with `$SUBAGENT_AWAIT_SYNC`:

```text
Load {actual $SKILL_ROOT}/compose/runners/g2-grounding-runner/SKILL.md and follow its instructions.

## Input
INDUCTIVE_OUT_DIR: {actual $INDUCTIVE_OUT_DIR}
COMPOSE_PROFILE: {actual $COMPOSE_PROFILE}
CYCLE_ID: {actual $CYCLE_ID}
PROJECT_ROOT: $(pwd)
```

Do **not** paste `architecture_view` in the Task prompt — the subagent reads `$INDUCTIVE_DQI` from disk.

Then run `$INDUCTIVE_GATE_CTL g2-check-report` **once** — immediately after the subagent returns. **`g2-check-report` exit 1 on `shape_breaking` is an expected branch — still run `$INDUCTIVE_GATE_CTL g2-list-report` next.** **Ignore** the Task return beyond confirming completion — decide next step only via `$INDUCTIVE_GATE_CTL g2-list-report`.

2. **If `verdict=ok`:** stay silent (no user checkpoint). Call `$INDUCTIVE_GATE_CTL gate-close --gate G2` (no payload) to advance to Gate 3.
3. **If `verdict=shape_breaking`:** present `divergences[]` from `$INDUCTIVE_GATE_CTL g2-list-report` stdout only; call `$INDUCTIVE_GATE_CTL gate-reopen --gate G1` and correct the shape with the user.

**Breaking SSOT:** only a **direct contradiction** with G1 `architecture_view` / `shape_constraints` is shape-breaking. **To-Be gaps (not yet implemented) are not breaking** — route those to Gate 3.

**Close criterion (automatic when ok):** `g2-topology-report.json` exists with `verdict=ok`. Mechanical gate-close rejects missing report or `shape_breaking`. No user checkpoint on success.

---

## Gate 3 — Refine (frontier sweep)

**Goal:** refine the shape artifact by **frontier sweep** — each sweep surfaces every unsettled section's *coarsest* open point (at its current `frontier_kw`); the user expands and decides points one at a time, each decision is appended to its section bucket, then the user re-sweeps. Sweeps repeat (recomputing each section's frontier) until every section reaches its target maturity. (Why the sweep shape, not section-at-a-time: **Method**.)

**Setup:** breadth = `SCAN_CRITERIA.expose_axis.coverage_sections` (checklist + default order; sections **not** listed are **peeled** — covered by the Gate 1 shape or the deferred bucket, not discovered here); depth = per-section `frontier_kw` 0..4 (default leave at KW3). Discovery has two peer sources: **AI methods** (run the `methods` whose `sections` include the unsettled section at its `frontier_kw`) and **`human_inlet`** (the user proposes a point in any dimension, at any altitude, at any time — exempt from the `frontier_kw` filter; AI maps it to its owning section — full mapping + `register-ep` call in Global Rules). **KW is the ruler, not a loop** — a candidate is a real open point only if it leaves the section's current `frontier_kw` row of `KW_CRITERIA` false; the iteration unit is always the open point, never section × KW. Resume any turn via `$INDUCTIVE_GATE_CTL resolve-context`; all section/EP mutations go through `$INDUCTIVE_G3_SECTION_CTL` (subcommands + flags in its `--help`).

### Sweep spine

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
Load {actual $SKILL_ROOT}/compose/runners/g3-shallow-grounding-runner/SKILL.md and follow its instructions.

## Input
SWEEP: <K>
INDUCTIVE_OUT_DIR: {actual $INDUCTIVE_OUT_DIR}
COMPOSE_PROFILE: {actual $COMPOSE_PROFILE}
CYCLE_ID: {actual $CYCLE_ID}
PROJECT_ROOT: $(pwd)
```

Then run `$INDUCTIVE_GATE_CTL grounding-check --sweep <K>` **once** — immediately after the subagent returns, as the gate before step 2. Must pass before step 2. **Do not** re-run `grounding-check` later in the same sweep (e.g. after `set-frontier`) — receipts are frozen at grounding-time `frontier_kw`; advancing a section invalidates its sweep-K receipt for re-check; only a new sweep's step 1 re-validates. **Ignore** the subagent Task return beyond confirming completion — fuel step 2 only via `$INDUCTIVE_GATE_CTL grounding-list --sweep <K>`. **Do not** read source inline in step 1.

### Step 2 — Discover + register

For each unsettled section S, run S's methods at its `frontier_kw` **using only** sweep receipts from step 1 — **do not** inline-read source again in this step (re-read happens only in step 4a for the chosen point). Keep a candidate only if it leaves **the `frontier_kw` row of S in `KW_CRITERIA`** false — a concern that belongs to a deeper KW row is *not* in scope this sweep (it surfaces in a later sweep once S advances). **First subtract the shape constraints** (Gate 1 confirmed claims): a point those already settle is not an open point — do not re-surface it with shape-contradicting options; if a constraint settles only part of a point, keep the open residue. Discovery may scan any section (read-only); **registering** a point requires activating that section (mutation focus guard). (`human_inlet` points are exempt from this `frontier_kw` filter — see Global Rules.)

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
Load {actual $SKILL_ROOT}/compose/runners/g3-deep-grounding-runner/SKILL.md and follow its instructions.

## Input
EP_ID: {actual EP id}
SECTION: {actual active_section}
FRONTIER_KW: {actual frontier_kw}
PROBLEM: {actual one-line problem statement from step 3}
SWEEP: {actual current sweep number}
INDUCTIVE_OUT_DIR: {actual $INDUCTIVE_OUT_DIR}
COMPOSE_PROFILE: {actual $COMPOSE_PROFILE}
CYCLE_ID: {actual $CYCLE_ID}
PROJECT_ROOT: $(pwd)
```

Then run `$INDUCTIVE_GATE_CTL deep-grounding-list --sweep <K> --ep-id <EP_ID>` **once** — immediately after the subagent returns — to fetch its receipt as fuel for 4b. **Ignore** the subagent Task return beyond confirming completion. **Do not** read source inline for this point — that is the deep-grounding-runner's job (targeted Read only, no whole-file reads).

**4b. Form leaning → user decides:** AI gives leaning + rationale + implication, grounded in the 4a receipt's `facts` / `code_refs`, → user decides → `update-ep --status resolved` + `resolution`, then `append-to-section` folds the decision into that section's figure. Skipped → `update-ep --status deferred`.

### Step 5 — Advance maturity

Once a section's points for this sweep are resolved/deferred, `set-frontier` it to its new KW.

### Step 6 — Re-sweep or clear

The user re-sweeps (recompute frontiers → step 1; the map deepens), or — for any section that reached the target with no blocking-open EP — confirms `clear-section`. A blocking-open EP, an unmet frontier, or an empty bucket blocks `clear-section` (hard gate at clear, not at navigation).

**Mandatory coverage:** `$SCAN_CRITERIA.mandatory_coverage_prompt` sections must reach `cleared` or `skipped` before G3 can close. For any with no discovered point, explicitly ask whether a coverage point should be added for this section — the guaranteed hearing for `human_inlet`.

**Close criterion:** call `$INDUCTIVE_G3_SECTION_CTL check-coverage` — all `coverage_sections` are `cleared` or `skipped`, no `(blocking ∧ open)` EP remains, mandatory sections covered; then call `$INDUCTIVE_GATE_CTL gate-close --gate G3 --payload '{...}'` after user confirms the view is detailed enough.

---

## Gate 4 — Recompose + Audit

**Goal:** audit the already-committed section files for cross-section coherence. This gate prevents the decomposition from losing the whole. It **only finds and names problems — it never fixes them**: it does not discover new EPs, does not run methods, does not write section files, and changes no decision. Every finding is routed back to the gate that owns it (step 3 table).

**Read discipline (context guard):** the **semantic** half of the audit (`conflicts` / `buildable` / `reversible` / `verifiable`) runs in `g4-recompose-runner` subagent only — **do not** inline-read section files, the EP ledger, or the DQI during G4. The **structural** half (`reforms_shape` / `shape_absorbed`) is mechanical and stays a direct script call (step 1) — it needs no subagent.

### Audit spine

1. **Structural check** (script) → `reforms_shape` / `shape_absorbed`.
2. **Semantic audit** (subagent) → gate: fetch its verdict via `g4-check-report` / `g4-list-report`.
3. **Present + route** — name each problem, route it to the gate that owns it; fix there, then re-run from step 1.
4. **Close** — report-driven; no payload the caller can forge.

### Step 1 — Structural check

Call `$INDUCTIVE_G3_SECTION_CTL recompose-check` to audit the committed artifacts (reads `inductive-scope/<S>.md` files + `exposed-points.json` + `architecture_view`):
- **reforms_shape** — do the resolved points still constitute the Gate 1 shape?
- **shape_absorbed** — is every confirmed shape constraint folded into its owning section file? No load-bearing constraint may live only in working memory — `_overview` is a cold-start scaffold, not an output, so anything it held must now have a section home.

Both are mechanical (file-presence / ledger checks) — no semantic judgement, so no subagent is needed here.

### Step 2 — Semantic audit (subagent)

Dispatch `g4-recompose-runner` via `$SUBAGENT_TOOL` with `$SUBAGENT_AWAIT_SYNC`:

```text
Load {actual $SKILL_ROOT}/compose/runners/g4-recompose-runner/SKILL.md and follow its instructions.

## Input
INDUCTIVE_OUT_DIR: {actual $INDUCTIVE_OUT_DIR}
COMPOSE_PROFILE: {actual $COMPOSE_PROFILE}
CYCLE_ID: {actual $CYCLE_ID}
PROJECT_ROOT: $(pwd)
```

Do **not** paste section-file contents in the Task prompt — the subagent reads `inductive-scope/<S>.md`, `exposed-points.json`, and `$INDUCTIVE_DQI` from disk.

Then run `$INDUCTIVE_GATE_CTL g4-check-report` **once** — immediately after the subagent returns. **Exit 1 (unresolved conflicts, or `buildable`/`reversible`/`verifiable`=false) is an expected branch — still run `$INDUCTIVE_GATE_CTL g4-list-report` next** to get the findings for step 3. **Ignore** the Task return beyond confirming completion — decide next step only via `$INDUCTIVE_GATE_CTL g4-list-report`. **Do not** read source inline in this step.

### Step 3 — Present + route

Present the recompose self-check — **naming each problem, not fixing it**. Route every finding back to the gate that owns it; Gate 4 registers no EP and changes no decision (the fix is made there through the normal AI-recommends → user-decides loop). After the fix, re-run from step 1 (structural + semantic must both be re-checked — a stale verdict is never reused).

| Finding | Route |
|---|---|
| `shape_absorbed=false`, or a `conflict` with a single `owning_section` | **Section-level.** `$INDUCTIVE_GATE_CTL gate-reopen --gate G3` (also clears the stale semantic report) → `$INDUCTIVE_G3_SECTION_CTL rewind-section --to <S>` for each affected section → fix via the Gate 3 step-4 loop (`append-to-section`) → re-`clear-section`. |
| a `conflict` with no `owning_section` (cross-section) | **Cross-section.** User picks **one owning section** to host the reconciliation → `activate-section` it → register the reconciliation as a normal EP there (focus guard applies) → decide it one at a time → re-`append-to-section` + `clear-section` any other affected section to match. |
| `reforms_shape=false` | **Shape-level.** `$INDUCTIVE_GATE_CTL gate-reopen --gate G1` (cascades: clears the stale G2/G4 reports too) → correct the shape with the user → re-descend the spine. |
| `buildable=false` / `reversible=false` / `verifiable=false` | Same as a cross-section or section-level conflict, whichever the subagent's `facts` implicate; if the whole design is unsound, treat as shape-level. |

`rewind-section` alone only moves the section pointer; `gate-reopen` is what returns the spine to Gate 3 (or Gate 1), so the two stay consistent — always pair them. Committed `<S>.md` files and the EP ledger survive a reopen — only gate status (and the now-stale g4 report) resets.

### Step 4 — Close

**Close criterion:** call `$INDUCTIVE_GATE_CTL gate-close --gate G4` (no payload — **report-driven**, mirroring G2). Internally it re-runs `recompose-check` and reads `g4-recompose-report.json`, merges both, and rejects the close if any of `reforms_shape` / `shape_absorbed` / `conflicts==[]` / `buildable` / `reversible` / `verifiable` fails — a caller-supplied payload can never substitute for the actual report. On success it writes the merged predicates to `$INDUCTIVE_DQI.recompose_check` and advances to Gate 5. Call this only after the user confirms the integrated solution is coherent.

On G4 close, proceed to Gate 5 before returning to the parent.

---

## Gate 5 — Provenance (find & name only)

**Goal:** on the G4-coherent section files, **name every deviation** of this stage's output from its upstream references, and drop them into three trace files. Like Gate 4, Gate 5 **only finds and names — it never fixes a decision and never collects sign-off.** All deltas are written `pending-signoff`; sign-off and delivery blocking are a later phase.

**Read discipline (context guard):** runs in `g5-provenance-runner` subagent only — **do not** inline-read section files, `$SCOPE_DOC`, or upstream refs during G5.

1. Call `$PROVENANCE_GATE_CTL init-session --cycle-id "$CYCLE_ID" --stage "$COMPOSE_PROFILE"` (once, on entry after G4) — seeds gate state + three empty traces. Resume: `$PROVENANCE_GATE_CTL resolve-context`.
2. **Provenance scan (subagent):** dispatch `g5-provenance-runner` via `$SUBAGENT_TOOL` with `$SUBAGENT_AWAIT_SYNC`:

```text
Load {actual $SKILL_ROOT}/compose/runners/g5-provenance-runner/SKILL.md and follow its instructions.

## Input
INDUCTIVE_OUT_DIR: {actual $INDUCTIVE_OUT_DIR}
SCOPE_DOC: {actual $SCOPE_DOC}
INTENT_BASELINE_REFS: {actual $INTENT_BASELINE_REFS}
NORM_CONSTRAINT_REFS: {actual $NORM_CONSTRAINT_REFS}
COMPOSE_PROFILE: {actual $COMPOSE_PROFILE}
CYCLE_ID: {actual $CYCLE_ID}
PROJECT_ROOT: $(pwd)
```

Do **not** paste section-file or upstream-ref contents in the Task prompt — the subagent reads them from disk. **Ignore** the Task return beyond confirming completion — read the actual deltas only via `$PROVENANCE_GATE_CTL present` next.

Role/algorithm/file mapping, axis semantics, and bucket vocabulary are the subagent's own SSOT (its Pipeline + `docs/biz/compose-provenance-mechanism.md` §2 + `provenance_trace_schema.py`) — not repeated here.

3. Call `$PROVENANCE_GATE_CTL present` (read-only) and show the user the full delta list — a receipt, **not** a sign-off.

**Close criterion:** call `$PROVENANCE_GATE_CTL gate-close` — it re-presents the full delta list (read-only receipt) and marks G5 closed. A clean stage simply closes with zero deltas.

### Return

```
inductive-runner complete.
per-section scope → <INDUCTIVE_DIR>/ (<N> sections)
inductive-dqi.json → <path>
provenance deltas → intent <A> / scope <B> / norm <C> (all pending-signoff)
Deferred points: <N> (will appear in design-doc OQ)
Returning to parent compose stage for compose Initializing.
```

Control returns to the parent compose stage.

---

## Output Contract

Artifacts are written progressively across gates, not authored fresh at the end — this section is the data contract, not a step to execute.

**Per-section files** are built incrementally during Gate 3 via `append-to-section` and finalised at `clear-section`. Gate 4 never writes them. There is **no merged document** and **no `_overview` file**.

Each `<SECTION>.md` — built across sweeps via `append-to-section`, finalised at `clear-section` — holds that section's figure(s) — deepening across KW where it refined — and resolved decisions, drawn in the section's `presentation.allowed` carrier, obeying `presentation.forbidden`:

```markdown
<!-- section-key:<SECTION> -->
### [<SECTION>] <localized section label>

<the section's figure(s) in its form carrier — coarse→fine across KW where it deepened>
- <resolved decision (one bullet), with code anchor>

> 代码引用：<this section's code_refs, deduplicated>
> 待决（deferred）：<this section's deferred points — become OQ in design-doc>
```

> The `<!-- section-key:KEY -->` anchor is what the grounding resolver maps and compose Initializing reads to load a section's slice as its `I*` grounding (alongside the decision-doc SSOT).

**`INDUCTIVE_DQI`** (`inductive-dqi.json`) is assembled by `$INDUCTIVE_GATE_CTL` — not hand-written. Top-level keys: `version`, `source_scope_doc`, `architecture_view`, `exposed_points`, `recompose_check`. It aggregates the already-documented parts: `architecture_view` + `shape_constraints` (the G1 close payload), an `exposed_points` snapshot (the EP ledger; per-EP contract in `inductive_exposed_points_schema.py`), and `recompose_check` (the merged structural + semantic predicates written on G4 close — see Gate 4 step 4).

---

## Constraints

The mechanical invariants the gates above must not violate (the *why* is in **Method**; these are the hard guardrails):

- **One view, a figure stack per section:** each section owns its own figure in that section's `presentation.allowed` carrier (deepening across KW within), obeys `presentation.forbidden` — never `file:line` / code-edit prose, never a flat prose/audit/checklist artifact, never overwrite another section's figure.
- **Two axes, not a tier enum:** breadth (`coverage_sections`) + within-section KW gradient (the only granularity axis); never iterate once per KW — the iteration unit is the open point.
- **Frontier sweep, not section-at-a-time:** Gate 3 advances all unsettled sections' maturity together — each sweep surfaces every section's coarsest open point at its `frontier_kw`; a section clears only when its `frontier_kw` reaches the target (default KW3) with no blocking-open EP.
- **Open-point altitude = frontier KW:** every frontier-map open point is *selected* and *worded* at its section's `frontier_kw` row of `KW_CRITERIA` — no deeper-KW substance (signatures / counts / `file:line`) in the problem statement; that detail lives only in the leaning/接地 part. `human_inlet` points are exempt (any altitude, any dimension; AI maps them to a section).
- **Collaboration baseline:** AI leads cognition (explore / think / surface + a grounded leaning); the user leads decision and progress. AI output is an exploration finding + leaning — never a multiple-choice menu the user answers, never a verdict.
- **Lazy, one at a time:** examine source material only as each section requires (no unrelated scans); decide one point at a time (no batching); never raise an EP for content already settled by the scope doc or a shape constraint. Gate 3 shallow grounding runs in a dispatched subagent (whole sweep, step 1); deep grounding for the chosen point also runs in a dispatched subagent (one point, step 4a); leanings and decisions stay inline (step 3–4b). Gate 4's semantic audit (`conflicts` / `buildable` / `reversible` / `verifiable`) also runs in a dispatched subagent (step 2) — only its mechanical structural half (`reforms_shape` / `shape_absorbed`, step 1) is a direct script call.