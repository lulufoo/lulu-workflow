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

Produces per-section scope files under `inductive-scope/` (one `<SECTION>.md` per touched section) and `inductive-dqi.json` in the stage's compose cache dir. Compose Initializing reads each section's slice on demand (per-section grounding) — there is no merged document.
After completion, control returns to the parent compose stage to proceed with compose Initializing.

This runner is **stage-agnostic**: `coverage_sections`, section weights, and discovery `methods` are profile data fetched as `inductive-scan-criteria` — the authoritative list is whatever the fetched criteria declare.

---

## Dispatch Inputs (from parent compose stage)

The parent passes these in the `## Input` block; do not hardcode stage paths.

| Var | Meaning |
|-----|---------|
| `$COMPOSE_PROFILE` | Compose profile id (drives every `$FETCH_COMPOSE`) |
| `$CYCLE_ID` | Active cycle id |
| `$SCOPE_DOC` | Upstream scope SSOT path (Gate 1 reads this — e.g. `decision-doc.md`) |
| `$INDUCTIVE_OUT_DIR` | Output dir for inductive artifacts (the stage's compose cache dir) |

## Session Paths (derived)

```
INDUCTIVE_DIR         = $INDUCTIVE_OUT_DIR/inductive-scope          # per-section scope files (the only scope artifacts init reads)
INDUCTIVE_DQI         = $INDUCTIVE_OUT_DIR/inductive-dqi.json
INDUCTIVE_GATE_STATE  = $INDUCTIVE_OUT_DIR/inductive-gate-state.json
INDUCTIVE_SECTION_PTR = $INDUCTIVE_OUT_DIR/inductive-section-pointer.json
INDUCTIVE_EP_LEDGER   = $INDUCTIVE_OUT_DIR/exposed-points.json
```

---

## Script Macros

| Macro | Command |
|-------|---------|
| `$FETCH_COMPOSE` | `python3 "$SKILL_ROOT/compose/scripts/io/fetch_compose_framework.py" --role <role> --profile "$COMPOSE_PROFILE" --project-root "$(pwd)" --cycle-id "$CYCLE_ID"` |
| `$INDUCTIVE_GATE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/inductive_gate_control.py" --out-dir "$INDUCTIVE_OUT_DIR"` |
| `$INDUCTIVE_SECTION_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/inductive_section_control.py" --out-dir "$INDUCTIVE_OUT_DIR"` |

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

**Gate 1 Shape → Gate 2 Grounding (background) → Gate 3 Refine (frontier sweep) → Gate 4 Recompose**

The gates progressively refine the **same shape artifact** from coarse to fine. Each gate has an observable close criterion. Do not advance until it is met.

---

## Roles & Global Rules

- **Collaboration baseline (load-bearing — never violate).** AI leads **cognition**: it explores (scan + on-demand grounding), thinks the findings through, surfaces the problems, and offers a grounded leaning. The **user leads decision and progress**: which point to deepen, whether to skip, when to re-sweep, when to stop. Therefore AI output is always an **exploration finding + leaning** — never a multiple-choice menu the user merely answers, never a verdict. Frame every gate the same way: *"I explored X; here is what I found and my reading; you decide where to go."*
- **Who fixes what (load-bearing — never violate).** Every *how-to-fix* decision is the **user's**. The **AI only recommends** (leaning + rationale + implication). The **scripts only move state and keep the ledger** — never a semantic judgement about content. **Gate 4 only finds and names problems; it never fixes them.** A fix is always made back in the gate that owns it (Gate 3 for a section, Gate 1 for shape), through the normal AI-recommends → user-decides loop — never auto-applied and never patched inside the auditor.
- **AI leads the spine, the user drives the descent.** AI knows the next gate and, each sweep, exposes the **frontier map** — every unsettled section's coarsest open point (recommendations). The **user chooses** which point to expand, whether to skip it, when to re-sweep, and when to stop.
- **AI output is a recommendation, not a verdict.** Phrase as "I lean X because…; the implication is…; expand this?" — leave the decision to the human.
- **Two-layer focus guard.** Sections are peers; `activate-section <S>` is always permitted. **Discovery is global (read-only):** a sweep may scan *all* unsettled sections to build the frontier map. **Mutation is focus-guarded:** every state-mutating operation (`register-ep`, `update-ep`, `set-frontier`, `append-to-section`, `clear-section`, `skip-section`) must target the `active_section` — run `$INDUCTIVE_SECTION_CTL activate-section --section <S>` first to shift focus. You may *see* a gap in any section during a sweep, but to *register/decide* it you must activate that section.
- **`human_inlet` is a peer discovery source, not a safety net.** The user may raise a design point in **any dimension, at any altitude, at any time** — on equal footing with the AI-scan frontier map. It is **AI's job to map** that free-form point to its owning section: run `$INDUCTIVE_SECTION_CTL activate-section --section <mapped S>` first, then `register-ep --json '{"source":"human_inlet","method":"human_inlet","kw":"<KW criterion it leaves false>",...}'` (the mutation focus guard still applies — the EP lands under the mapped `active_section`). A `human_inlet` point is **exempt from the frontier-altitude filter** — it need not be the section's coarsest open point nor sit at the current `frontier_kw`; never reject it for being "off-frontier". If it maps to no `coverage_section` (it belongs to a peeled section or the shape), **say where it goes** — fold it into a shape constraint or the deferred bucket — never silently drop it. The remaining EP lifecycle (resolve/defer/fold into figure) is identical to an AI-scan EP.
- **One point at a time** — never batch multiple decisions into one prompt.
- **Session state persists across turns.** At the start of each new turn, call `$INDUCTIVE_GATE_CTL resolve-context` to restore `active_gate`, `active_section`, open-EP count, and `architecture_view`. Never rely on conversation memory alone.
- Fetch per schedule (see **Script Macros**): `SCAN_CRITERIA` at Gate 1 start (`shape_extraction.fields` for Gate 1 + `expose_axis` for Gate 3); `section-form-registry` (carriers) and `KW_CRITERIA` (per-section KW altitude rows) before Gate 3.

---

## Gate 1 — Shape (coarse shape artifact)

**Goal:** render the change as a coarse **shape artifact** (`SCAN_CRITERIA.shape_extraction.artifact_label`) — the cold-start structural abstraction, as one coherent whole. Do **not** examine implementation; do **not** organize by section; do **not** drop to implementation detail.

1. Read `$SCOPE_DOC` in full (use its decision conclusions as primary source).
2. Produce one **shape artifact** (the carrier every later gate refines).
   For each field in `SCAN_CRITERIA.shape_extraction.required` (and `.optional` where applicable): render using the field's `carrier`, obey its `forbidden`, and present `as_is`+`to_be` as a paired before→after block. Field labels, guidance, and render rules are in `SCAN_CRITERIA.shape_extraction.fields` — do not deviate from them.
3. Append the 1–2 **load-bearing claims you are least sure of**, restricted to **shape altitude** — the spine framing, a boundary call, a structural relation, or an implicit premise the source material can't tell you. **Do not** raise implementation risks here — those belong to Gate 3.

**Present:** the shape artifact (all `shape_extraction.required` fields + any applicable `.optional` fields, rendered per `shape_extraction.fields`) + the shape-level load-bearing claims.

**Close criterion:** the user confirms the spine, the To-Be structure, and the boundary (e.g. "形状确认" / "shape confirmed"). Corrections are folded in and the view re-presented until confirmed. On confirmation, call `$INDUCTIVE_GATE_CTL gate-close --gate G1 --payload '{"architecture_view": {...}, "shape_constraints": [...]}'` — this persists the `architecture_view` to the DQI, freezes the load-bearing claims into **shape constraints** (invariants Gate 3 must respect and must not re-open), and advances the spine to Gate 2.

**Session init (once per session, at Gate 1 start):** call `$INDUCTIVE_GATE_CTL init-session --sections <coverage_sections CSV> --mandatory <mandatory_coverage_prompt CSV>` to seed both the gate state and section pointer. Skip if resuming an existing session — `$INDUCTIVE_GATE_CTL resolve-context` will confirm the current active gate.

---

## Gate 2 — Grounding (background)

**Goal:** a fast, autonomous sanity-check that the confirmed shape's spine/topology is not fundamentally wrong. **Not** a user-facing audit; **not** an exhaustive line-level grounding (that happens lazily per section in Gate 3).

1. Examine only enough to confirm the spine and the To-Be topology are real (the main blocks exist / can exist, the key relations are plausible).
2. **Surface upward only if a divergence breaks the shape** — i.e. the spine or topology is wrong. Then stop and reopen Gate 1 with the specific shape correction.
3. Otherwise stay silent: record grounding notes as fuel for Gate 3. **Do not** present a confirmation table and **do not** ask the user to confirm grounding.

**Close criterion (automatic):** no shape-breaking divergence. Call `$INDUCTIVE_GATE_CTL gate-close --gate G2` (no payload — automatic close) to advance the spine to Gate 3; do not pause for a user checkpoint. (A shape-breaking divergence is the only thing that interrupts the user — then `$INDUCTIVE_GATE_CTL gate-reopen --gate G1` instead and correct the shape.)

---

## Gate 3 — Refine (frontier sweep)

**Goal:** refine the shape artifact by **frontier sweep**. Each sweep surfaces every unsettled section's *coarsest* open point (at that section's current frontier KW); the user expands and decides points one at a time, and each decision is appended to its section bucket; then the user re-sweeps. Sweeps repeat — recomputing each section's frontier — until every section reaches its target maturity. The whole view sharpens together (coarse → fine globally), not one section drilled to the end before the next. Discover and decide are interleaved per sweep — not two global batches.

**Two axes:** the **cross-section coverage axis** (`SCAN_CRITERIA.expose_axis.coverage_sections` — coverage checklist + default order; crossing sections changes design *dimension*, not resolution) and the **within-section KW gradient** (the only coarse → fine axis; `frontier_kw` 0..4, default leave at KW3). Sections may be visited in any order via `activate-section`. Sections **not** in `coverage_sections` are **peeled** — covered by the Gate 1 shape or the deferred bucket, not discovered here.

**Two discovery sources inside a sweep:**
- **AI methods = the action.** For each unsettled section S at its `frontier_kw`, run the `methods` whose `sections` include S; each scans (view + on-demand grounding) and emits candidate gaps of its type (`finds`).
- **`human_inlet` = peer discovery source.** The user may propose a design point in **any dimension, at any altitude, at any time** — first-class, on equal footing with AI-scan EPs, not a safety net. **AI maps it to its owning section** and registers it there; it is **exempt from the frontier-altitude filter** below. See Global Rules for the mapping + `register-ep` call.
- **KW = the ruler, not a loop.** A candidate from an AI method is a real open point only if it leaves S's current `frontier_kw` row of `KW_CRITERIA` false (a deeper-row concern waits for a later sweep); a `human_inlet` candidate qualifies at any row. KW is evaluated to (a) qualify + altitude-word candidates and (b) signal when S is clear enough to clear (default KW3). **Never iterate once per KW** — the iteration unit is the open point.

**State management for Gate 3:**
- Resume / start: `$INDUCTIVE_GATE_CTL resolve-context` — confirms `active_gate=G3`, `active_section`, per-section `frontier`, and open-EP count. (Session was seeded at Gate 1 start.)
- Switch focus: `$INDUCTIVE_SECTION_CTL activate-section --section <S>` (free; previous active section transitions to `open` if uncleared).
- Register EP: `$INDUCTIVE_SECTION_CTL register-ep --json '{...}'`
- Update EP: `$INDUCTIVE_SECTION_CTL update-ep --id <id> --status resolved|deferred [--resolution ...]`
- Declare maturity: `$INDUCTIVE_SECTION_CTL set-frontier --section <S> --kw <0-4>` (AI declares S's reached KW once this sweep's S-points are resolved/deferred).
- Append to bucket: `$INDUCTIVE_SECTION_CTL append-to-section --section <S> --content <markdown>` (folds one resolved figure/decision into `<S>.md`; incremental, called per decision).
- Clear section: `$INDUCTIVE_SECTION_CTL clear-section --section <S>` (validates `frontier_kw ≥ target` + no blocking-open EP + non-empty bucket → marks `cleared`).

**Per sweep:**

1. **Ground on demand (background):** examine only the source material the unsettled sections need as fuel. No audit table.
2. **Discover across sections (read-only):** for each unsettled section S, run S's methods at its `frontier_kw`; keep a candidate only if it leaves **the `frontier_kw` row of S in `KW_CRITERIA`** false — a concern that belongs to a deeper KW row is *not* in scope this sweep (it surfaces in a later sweep once S advances). **First subtract the shape constraints** (Gate 1 confirmed claims): a point those already settle is not an open point — do not re-surface it with shape-contradicting options; if a constraint settles only part of a point, keep the open residue. Discovery may scan any section (read-only); **registering** a point requires activating that section (mutation focus guard). (`human_inlet` points are exempt from this `frontier_kw` filter — see Global Rules.)

> Register each open point via `register-ep --json` under the `active_section`. The EP field contract — `id` · `section` · `block` · `method` · `kw` · `type` · `description` · `code_refs` · `confidence` · `blocking` · `source` · `status` (+ `resolution` when resolved) — and its allowed values live in `inductive_exposed_points_schema.py` (no `tier` field). Key bindings: `section` must equal `active_section`; `method` is the surfacing method ID or `human_inlet`; `kw` is the KW criterion it leaves false.

3. **Draw the frontier map as an exploration finding (not a menu, not a dump):** present **each unsettled section's coarsest open point** (one per section) as two paired parts:
   - **the problem, stated plainly** — worded at that section's `frontier_kw` altitude from `KW_CRITERIA` (e.g. at KW1 just *name which decision / constraint / contract is undecided*); **no signatures, counts, or `file:line` evidence in this part** — that depth belongs to deeper KW rows;
   - **my reading / leaning (接地)** — a grounded recommendation that *may* carry the concrete detail (signature, count, code anchor) the problem line withholds. This is where exploration touches ground; it never replaces the user's decision.

   The problem part describes; the leaning part grounds. This is the coarse, roughly uniform-resolution view of the whole change; earlier sweeps' deeper figures stay as the map — never overwrite them. Hand it back to the driver as exploration, not a quiz: *"I explored each dimension — these are the coarsest open problems I found and my reading of each; you decide which to deepen, skip, or add one I missed."* — never "pick option A/B/C".
4. **User drives, one point at a time:** the user picks a point to expand, skips it, or proposes one via `human_inlet`. For the chosen point: `activate-section` its section → AI gives leaning + rationale + implication → user decides → `update-ep --status resolved` + `resolution`, then `append-to-section` folds the decision into that section's figure. Skipped → `update-ep --status deferred`.
5. **Advance maturity:** once a section's points for this sweep are resolved/deferred, `set-frontier` it to its new KW.
6. **Re-sweep or clear:** the user re-sweeps (recompute frontiers → step 2; the map deepens), or — for any section that reached the target with no blocking-open EP — confirms `clear-section`. A blocking-open EP, an unmet frontier, or an empty bucket blocks `clear-section` (hard gate at clear, not at navigation).

**Mandatory coverage:** `$SCAN_CRITERIA.mandatory_coverage_prompt` sections must reach `cleared` or `skipped` before G3 can close. For any with no discovered point, explicitly ask whether a coverage point should be added for this section — the guaranteed hearing for `human_inlet`.

**Close criterion:** call `$INDUCTIVE_SECTION_CTL check-coverage` — all `coverage_sections` are `cleared` or `skipped`, no `(blocking ∧ open)` EP remains, mandatory sections covered; then call `$INDUCTIVE_GATE_CTL gate-close --gate G3 --payload '{...}'` after user confirms the view is detailed enough.

---

## Gate 4 — Recompose + Audit

**Goal:** audit the already-committed section files for cross-section coherence. This gate prevents the decomposition from losing the whole. It **only finds and names problems — it never fixes them**: it does not discover new EPs, does not run methods, does not write section files, and changes no decision. Every finding is routed back to the gate that owns it (see step 2).

1. Call `$INDUCTIVE_SECTION_CTL recompose-check` to audit the committed artifacts (reads `inductive-scope/<S>.md` files + `exposed-points.json` + `architecture_view`):
   - **reforms_shape** — do the resolved points still constitute the Gate 1 shape?
   - **shape_absorbed** — is every confirmed shape constraint folded into its owning section file? No load-bearing constraint may live only in working memory — `_overview` is a cold-start scaffold, not an output, so anything it held must now have a section home.
   - **conflicts** — do any two decisions contradict?
   - **buildable / reversible / verifiable** — does the integrated solution hold as one whole?
2. Present the recompose self-check — **naming each problem, not fixing it**. Route every finding back to the gate that owns it; Gate 4 registers no EP and changes no decision (the fix is made there through the normal AI-recommends → user-decides loop):
   - **Section-level** (`shape_absorbed=false`, or a `conflict` owned by one section): move the spine back first — `$INDUCTIVE_GATE_CTL gate-reopen --gate G3` — then `$INDUCTIVE_SECTION_CTL rewind-section --to <S>` for each affected section. `rewind-section` alone only moves the section pointer; `gate-reopen` is what returns the spine to Gate 3, so the two stay consistent. Fix via the Gate 3 step-4 loop (`append-to-section`), re-`clear-section`, then re-run `recompose-check`.
   - **Cross-section conflict** (a contradiction owned by no single section): the user picks **one owning section** to host the reconciliation. `activate-section` it, register the reconciliation as a normal EP there (focus guard applies — it lives under that one `active_section`), decide it one at a time, then re-`append-to-section` + `clear-section` any other affected section to match.
   - **Shape-level** (`reforms_shape=false`): `$INDUCTIVE_GATE_CTL gate-reopen --gate G1`, correct the shape with the user, then re-descend the spine. Committed `<S>.md` files and the EP ledger survive a reopen — only gate status resets.

**Close criterion:** `recompose_check` passes all fields; call `$INDUCTIVE_GATE_CTL gate-close --gate G4 --payload '<recompose_check JSON>'` after the user confirms the integrated solution is coherent.

### Write outputs

**Per-section files** are built incrementally during Gate 3 via `append-to-section` and finalised at `clear-section` — not here. Gate 4 only finalises the DQI. There is **no merged document** and **no `_overview` file**.

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

**`INDUCTIVE_DQI`** (`inductive-dqi.json`) is assembled by `$INDUCTIVE_GATE_CTL` — not hand-written. Top-level keys: `version`, `source_scope_doc`, `architecture_view`, `exposed_points`, `recompose_check`. It aggregates the already-documented parts: `architecture_view` + `shape_constraints` (the G1 close payload), an `exposed_points` snapshot (the EP ledger; per-EP contract in `inductive_exposed_points_schema.py`), and `recompose_check` (the G4 close payload).

### Return

```
inductive-runner complete.
per-section scope → <INDUCTIVE_DIR>/ (<N> sections)
inductive-dqi.json → <path>
Deferred points: <N> (will appear in design-doc OQ)
Returning to parent compose stage for compose Initializing.
```

Control returns to the parent compose stage.

---

## Constraints

The mechanical invariants the gates above must not violate (the *why* is in **Method**; these are the hard guardrails):

- **One view, a figure stack per section:** each section owns its own figure in that section's `presentation.allowed` carrier (deepening across KW within), obeys `presentation.forbidden` — never `file:line` / code-edit prose, never a flat prose/audit/checklist artifact, never overwrite another section's figure.
- **Two axes, not a tier enum:** the cross-section coverage/breadth axis (`coverage_sections`) and the within-section KW gradient (the only granularity axis). `methods` discover (action); KW judges (ruler) — never iterate once per KW; the iteration unit is the open point.
- **Frontier sweep, not section-at-a-time:** Gate 3 advances all unsettled sections' maturity together — each sweep surfaces every section's coarsest open point at its `frontier_kw`; a section clears only when its `frontier_kw` reaches the target (default KW3) with no blocking-open EP.
- **Open-point altitude = frontier KW:** every frontier-map open point is *selected* and *worded* at its section's `frontier_kw` row of `KW_CRITERIA` — no deeper-KW substance (signatures / counts / `file:line`) in the problem statement; that detail lives only in the leaning/接地 part. `human_inlet` points are exempt (any altitude, any dimension; AI maps them to a section).
- **Collaboration baseline:** AI leads cognition (explore / think / surface + a grounded leaning); the user leads decision and progress. AI output is an exploration finding + leaning — never a multiple-choice menu the user answers, never a verdict.
- **Gate altitudes:** Gate 1 is shape-first (no sections, no implementation detail; load-bearing claims at shape altitude → shape constraints on confirm). Gate 2 is background (no checkpoint; interrupt only on a shape-breaking divergence). Gate 3 is the only discovery gate; Gate 4 audits and **never discovers or fixes** — it names problems and routes them back to the owning gate, where the fix is user-decided.
- **Two-layer focus guard is mechanical:** discovery may scan cross-section (read-only); every state-mutating command (`register-ep`, `update-ep`, `set-frontier`, `append-to-section`, `clear-section`, `skip-section`) is rejected unless its target equals `active_section`.
- **Write timing:** per-section `<S>.md` is built via `append-to-section` and finalised at `clear-section` (Gate 3); `inductive-dqi.json` is finalized in Gate 4. No merged document, no `_overview` file.
- **Lazy, one at a time:** examine source material only as each section requires (no unrelated scans); decide one point at a time (no batching); never raise an EP for content already settled by the scope doc or a shape constraint.
- **Stage-agnostic:** never hardcode a stage's cache subdir / upstream path / section set — use the dispatch inputs and the fetched `coverage_sections`.
