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

Run this sub-skill only when dispatched from a compose stage `start` (inductive path) — e.g. `tech-design`.

Produces per-section scope files under `inductive-scope/` (one `<SECTION>.md` per touched section) and `inductive-dqi.json` in the stage's compose cache dir. Compose Initializing reads each section's slice on demand (per-section grounding) — there is no merged document.
After completion, control returns to the parent compose stage to proceed with compose Initializing.

This runner is **stage-agnostic**: which design dimensions (`coverage_sections`), weights, and discovery `methods` are profile data, fetched as the `inductive-scan-criteria` template. The concrete section keys shown below (`I`, `ST`, …) are the `tech-design` profile's example — the authoritative list is whatever the fetched criteria declare.

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
| `$FETCH_COMPOSE` | `python3 "$SKILL_ROOT/compose-kernel/scripts/io/fetch_compose_framework.py" --role <role> --profile "$COMPOSE_PROFILE" --project-root "$(pwd)" --cycle-id "$CYCLE_ID"` |
| `$INDUCTIVE_GATE_CTL` | `python3 "$SKILL_ROOT/compose-kernel/scripts/inductive/inductive_gate_control.py" --out-dir "$INDUCTIVE_OUT_DIR"` |
| `$INDUCTIVE_SECTION_CTL` | `python3 "$SKILL_ROOT/compose-kernel/scripts/inductive/inductive_section_control.py" --out-dir "$INDUCTIVE_OUT_DIR"` |

Before Gate 3, fetch two roles (do not read `workflow-config.json` directly):
- `$FETCH_COMPOSE --role inductive-scan-criteria` → `SCAN_CRITERIA`: the coverage ladder (`coverage_sections`), methods + weights, KW stop-gate semantics, and mandatory coverage.
- `$FETCH_COMPOSE --role section-form-registry` → the per-section carrier vocabulary (`sections.{key}.presentation`).

---

## Method (why a gate spine, not a section checklist)

Producing scope is an **inductive** task: from the upstream scope doc + code reality, *discover* what design decisions are still missing. This is parts → whole inference, not whole → parts derivation.

`section-registry` is a **completeness predicate over a finished document** — the deductive instrument that compose uses downstream to expand a known scope. A predicate can *test* and *attribute*, but it cannot *generate* substance or tell you which code to read. So here it is used **only inside Gate 3** as the coverage + attribution axis — never as the driver.

The driver is the gate spine below. Sections enter at Gate 3 as a destination, never at Gate 1 as a starting point.

**One architecture view, refined section by section, persisted per section.** A single **architecture view** is the carrier. It starts coarse (Gate 1), is validated against code in the background (Gate 2), then refined **one section step at a time along the coverage ladder, coarse → fine** (Gate 3), in `SCAN_CRITERIA.expose_axis.coverage_sections` order (tech-design example: `I` → `ST` → `KD` → `IF` → `VD` → `OD`). Within a section, the figure deepens across **KW levels** (KW1 readable → KW3 boundary-clear). Convergence is felt as the view getting finer section by section — not as a summary, then an audit, then a flat checklist.

**Two axes, not one "tier".** The descent has two independent gradients: **across sections** (the design-dimension ladder above) and **within a section** (KW maturity). There is no separate "tier" enum — a step is one section, and granularity inside it is KW.

**Each section step gets its own figure, not an edit of the previous one.** Within a section the figure deepens across KW levels; moving to the next section opens a *new* figure for that dimension — earlier figures stay intact as the map. Each figure is drawn in the **carrier its section prescribes** (`section-form-registry.presentation.allowed`). This is what stops every step from being described in `file:line` code prose (`presentation.forbidden`). Because each figure belongs to a section, the figure stack lands naturally **per section** — which is also how the output is stored and how compose Initializing loads it.

**methods discover, KW judges.** `methods` are the discovery action: at a section they emit candidate gaps. **KW is a ruler, not a loop** — a candidate is a real open point only if it leaves one of the section's KW criteria false, and KW also decides when the section is clear enough to leave (default KW3). The iteration unit is the open point, never section × KW.

**Shape claims are constraints, not re-openable questions.** The Gate 1 load-bearing claims, once confirmed, become invariants. Gate 3 discovery **subtracts** what they already fix — it does not re-surface a settled call as an open point with shape-contradicting options.

Understanding an architecture is itself a process: the user resolves the current section's open points, then chooses to move on. So the ladder is **user-driven**: AI recommends the open points at the current section (fueled by background grounding) and proposes the next section; the user picks what to expand, may skip, may inject a point AI missed, and decides when it is detailed enough.

---

## Pipeline

**Gate 1 Shape → Gate 2 Grounding (background) → Gate 3 Refine (section ladder) → Gate 4 Recompose**

The gates progressively refine the **same architecture view** from coarse to fine. Each gate has an observable close criterion. Do not advance until it is met.

---

## Roles & Global Rules

- **Who fixes what (load-bearing — never violate).** Every *how-to-fix* decision is the **user's**. The **AI only recommends** (leaning + rationale + implication). The **scripts only move state and keep the ledger** — never a semantic judgement about content. **Gate 4 only finds and names problems; it never fixes them.** A fix is always made back in the gate that owns it (Gate 3 for a section, Gate 1 for shape), through the normal AI-recommends → user-decides loop — never auto-applied and never patched inside the auditor.
- **AI leads the spine, the user drives the descent.** AI knows the next gate and exposes the section ladder + the open points at the current section (recommendations). The **user chooses** which point to expand, whether to skip it, and when to move on or stop.
- **AI output is a recommendation, not a verdict.** Phrase as "I lean X because…; the implication is…; expand this?" — leave the decision to the human.
- **Focus guard, not auto-advance.** Sections are peers on the ladder; `activate-section <S>` to any section is always permitted — the user may jump into any section at any time. All state-mutating operations (`register-ep`, `update-ep`, `commit-section`, `skip-section`) must target the `active_section`: run `$INDUCTIVE_SECTION_CTL activate-section --section <S>` first to shift focus. AI must not discover into a section other than the current `active_section`.
- **`human_inlet` is a peer discovery source, not a safety net.** At any section, the user may propose a design point AI did not surface — this is a first-class `human_inlet` EP, on equal footing with AI-scan EPs. Register it via `$INDUCTIVE_SECTION_CTL register-ep --json '{"source":"human_inlet","method":"human_inlet","kw":"<KW criterion it leaves false>",...}'` under the current `active_section`. The remaining EP lifecycle (resolve/defer/fold into figure) is identical to an AI-scan EP.
- **One point at a time** — never batch multiple decisions into one prompt.
- **Session state persists across turns.** At the start of each new turn, call `$INDUCTIVE_GATE_CTL resolve-context` to restore `active_gate`, `active_section`, open-EP count, and `architecture_view`. Never rely on conversation memory alone.
- Fetch both pre-Gate-3 roles once and cache (see **Script Macros**): `SCAN_CRITERIA` (coverage ladder + methods/weights + KW semantics + mandatory coverage) and `section-form-registry` (each touched section's `presentation.allowed` / `presentation.forbidden`).

---

## Gate 1 — Shape (coarse architecture view)

**Goal:** render the change as a coarse **architecture view** — the cold-start technical abstraction, as one coherent whole. Do **not** read code; do **not** organize by section; do **not** drop to implementation detail.

1. Read `$SCOPE_DOC` in full (use its decision conclusions as primary source).
2. Produce one **architecture view** (the carrier artifact every later gate refines):
   - **As-Is → To-Be** — the structural before→after: main components/containers, their topology and relations. A small block diagram (ASCII) is expected — not a prose paragraph.
   - **Change scope** — which capability/domain is In, which is explicitly Out (capability-level, not a file list).
   - **Affected files (coarse)** — the module/file blocks the change lands in, one line each (no line-level detail).
   - **Spine** — one line naming the center of gravity (what fundamentally becomes what).
   - **traces_to** — which upstream direction/goal this realizes.
3. Append the 1–2 **load-bearing claims you are least sure of**, restricted to **shape altitude** — the spine framing, a boundary call, a structural relation, or an implicit premise the code can't tell you. **Do not** raise implementation risks (event binding, call timing, contract fields) here — those belong to Gate 3.

**Present:** the architecture view (As-Is/To-Be diagram + scope + affected files + spine + traces_to) + the shape-level load-bearing claims.

**Close criterion:** the user confirms the spine, the To-Be structure, and the boundary (e.g. "形状确认" / "shape confirmed"). Corrections are folded in and the view re-presented until confirmed. On confirmation, call `$INDUCTIVE_GATE_CTL gate-close --gate G1 --payload '{"architecture_view": {...}, "shape_constraints": [...]}'` — this persists the `architecture_view` to the DQI, freezes the load-bearing claims into **shape constraints** (invariants Gate 3 must respect and must not re-open), and advances the spine to Gate 2.

**Session init (once per session, at Gate 1 start):** call `$INDUCTIVE_GATE_CTL init-session --sections <coverage_sections CSV> --mandatory <mandatory_coverage_prompt CSV>` to seed both the gate state and section pointer. Skip if resuming an existing session — `$INDUCTIVE_GATE_CTL resolve-context` will confirm the current active gate.

---

## Gate 2 — Grounding (background)

**Goal:** a fast, autonomous sanity-check that the confirmed shape's spine/topology is not fundamentally wrong. **Not** a user-facing audit; **not** an exhaustive line-level grounding (that happens lazily per section in Gate 3).

1. Read only enough code to confirm the spine and the To-Be topology are real (the main blocks exist / can exist, the key relations are plausible).
2. **Surface upward only if a divergence breaks the shape** — i.e. the spine or topology is wrong. Then stop and reopen Gate 1 with the specific shape correction.
3. Otherwise stay silent: record grounding notes as fuel for Gate 3. **Do not** present a confirmation table and **do not** ask the user to confirm grounding.

**Close criterion (automatic):** no shape-breaking divergence. Call `$INDUCTIVE_GATE_CTL gate-close --gate G2` (no payload — automatic close) to advance the spine to Gate 3; do not pause for a user checkpoint. (A shape-breaking divergence is the only thing that interrupts the user — then `$INDUCTIVE_GATE_CTL gate-reopen --gate G1` instead and correct the shape.)

---

## Gate 3 — Refine (section ladder)

**Goal:** refine the architecture view **one section at a time along the coverage ladder, coarse → fine**. At each section: discover the open points in that design dimension, let the user expand and decide them, then commit the section result. Discover and decide are interleaved per section — not two global batches. This is what makes convergence feel like understanding an architecture, not triaging a bug list.

**Ladder (from `SCAN_CRITERIA.expose_axis.coverage_sections`, ordered):** the ladder is a **peer list with a default sequence** (tech-design example: `I` → `ST` → `KD` → `IF` → `VD` → `OD`). Sections may be visited in any order — the user may jump to any section at any time via `activate-section`. The default order is AI's recommendation and the coverage checklist; it is not a lock. Sections **not** in `coverage_sections` are **peeled** — covered by the Gate 1 shape or the deferred bucket, not re-discovered here.

**Two discovery sources inside a step:**
- **AI methods = the action.** At section S, run the `methods` whose `sections` include S; each scans (view + on-demand grounding) and emits candidate gaps of its type (`finds`).
- **`human_inlet` = peer discovery source.** The user may propose a design point at any section, at any time. This is a first-class EP on equal footing with AI-scan EPs — not a safety net. See Global Rules for the `register-ep` call.
- **KW = the ruler, not a loop.** A candidate (from either source) is a real open point only if it leaves one of S's KW criteria false. KW is evaluated to (a) qualify candidates and (b) signal when S is clear enough to commit (default KW3). **Never iterate once per KW** — the iteration unit is the open point.

**State management for Gate 3:**
- Resume / start: `$INDUCTIVE_GATE_CTL resolve-context` — confirms `active_gate=G3`, `active_section`, and open-EP count. (Session was seeded at Gate 1 start.)
- Switch focus: `$INDUCTIVE_SECTION_CTL activate-section --section <S>` (free; previous active section transitions to `open` if uncommitted).
- Register EP: `$INDUCTIVE_SECTION_CTL register-ep --json '{...}'`
- Update EP: `$INDUCTIVE_SECTION_CTL update-ep --id <id> --status resolved|deferred [--resolution ...]`
- Commit section: `$INDUCTIVE_SECTION_CTL commit-section --section <S> --content <markdown>` (AI supplies the section body via `--content`; the script validates no blocking-open EPs → writes `<S>.md` → marks `cleared`)

**Per section step S (default order; user may reorder):**

1. **Ground on demand (background):** read only the code S needs as fuel. No audit table.
2. **Discover in S's dimension:** run S's methods; keep a candidate only if it leaves a KW criterion of S false. **First subtract the shape constraints** (Gate 1 confirmed claims): a point those already settle is not an open point — do not re-surface it with shape-contradicting options. If a constraint settles only part of a point, keep the open residue. A gap that belongs to a different section (dimension) is **not** registered here — it waits for that section's `activate-section` step (focus guard).

> Register each open point via `register-ep --json` under the `active_section`. The EP field contract — `id` · `section` · `block` · `method` · `kw` · `type` · `description` · `code_refs` · `confidence` · `blocking` · `source` · `status` (+ `resolution` when resolved) — and its allowed values live in `inductive_exposed_points_schema.py` (no `tier` field). Key bindings: `section` must equal `active_section`; `method` is the surfacing method ID or `human_inlet`; `kw` is the KW criterion it leaves false.

3. **Draw S's figure + recommend (not a dump):** present S's figure in the carrier its section prescribes (`presentation.allowed`; e.g. a dependency/flow/state-machine diagram for a structure section, a contract/field table for an interface section), obeying `presentation.forbidden` (no `file:line`/code-edit prose). Within S the figure deepens across KW (coarse → fine); earlier sections' figures stay as the map — do not overwrite them. Hang S's open points under their blocks (blocking marked) as recommendations — "in this dimension these are open; which to expand?".
4. **User drives:** the user expands a point, skips it, or proposes one via `human_inlet` (peer, not just "AI missed"). For each expanded point, decide it **one at a time** — AI gives leaning + rationale + implication; user decides; call `update-ep --status resolved` + `resolution` and fold the decision into S's figure. Skipped → `update-ep --status deferred`.
5. **Section soft gate + commit:** when every `blocking` EP in S is resolved or deferred, AI surfaces a soft reminder ("S is clear to commit — any residual points?") and proposes `commit-section`. The user confirms; **AI assembles S's figure(s) + resolved decisions into the section body** (the `<!-- section-key:S -->` markdown shown under **Write outputs**) and passes it as `--content`: `$INDUCTIVE_SECTION_CTL commit-section --section <S> --content <markdown>`. The script validates no blocking-open EP, writes `<S>.md`, and marks the section `cleared`. Uncommitted blocking EPs block `commit-section` (hard gate at commit, not at navigation).
6. **Next section:** AI recommends the next section from the default order (or the user names one); call `activate-section` to shift focus.

**Mandatory coverage:** `$SCAN_CRITERIA.mandatory_coverage_prompt` sections (tech-design example: `OD`, `VD`) must reach `cleared` or `skipped` before G3 can close. For any with no discovered point, explicitly ask whether a degradation / rollback / observability / verification point should be added — the guaranteed hearing for `human_inlet`.

**Close criterion:** call `$INDUCTIVE_SECTION_CTL check-coverage` — all `coverage_sections` are `cleared` or `skipped`, no `(blocking ∧ open)` EP remains, mandatory sections covered; then call `$INDUCTIVE_GATE_CTL gate-close --gate G3 --payload '{...}'` after user confirms the ladder is detailed enough.

---

## Gate 4 — Recompose + Audit

**Goal:** audit the already-committed section files for cross-section coherence. This gate prevents the decomposition from losing the whole. It **only finds and names problems — it never fixes them**: it does not discover new EPs, does not run methods, does not write section files, and changes no decision. Every finding is routed back to the gate that owns it (see step 2).

1. Call `$INDUCTIVE_SECTION_CTL recompose-check` to audit the committed artifacts (reads `inductive-scope/<S>.md` files + `exposed-points.json` + `architecture_view`):
   - **reforms_shape** — do the resolved points still constitute the Gate 1 shape?
   - **shape_absorbed** — is every confirmed shape constraint folded into its owning section file (topology → `ST`, invariants/spine → `I`, boundary → its section)? No load-bearing constraint may live only in working memory — `_overview` is a cold-start scaffold, not an output, so anything it held must now have a section home.
   - **conflicts** — do any two decisions contradict (e.g. lifecycle vs state authority)?
   - **buildable / reversible / verifiable** — does the integrated solution hold as one whole?
2. Present the recompose self-check — **naming each problem, not fixing it**. Route every finding back to the gate that owns it; Gate 4 registers no EP and changes no decision (the fix is made there through the normal AI-recommends → user-decides loop):
   - **Section-level** (`shape_absorbed=false`, or a `conflict` owned by one section): move the spine back first — `$INDUCTIVE_GATE_CTL gate-reopen --gate G3` — then `$INDUCTIVE_SECTION_CTL rewind-section --to <S>` for each affected section. `rewind-section` alone only moves the section pointer; `gate-reopen` is what returns the spine to Gate 3, so the two stay consistent. Fix via the Gate 3 step-4 loop, re-`commit-section`, then re-run `recompose-check`.
   - **Cross-section conflict** (a contradiction owned by no single section, e.g. lifecycle in `ST` vs state authority in `I`): the user picks **one owning section** to host the reconciliation. `activate-section` it, register the reconciliation as a normal EP there (focus guard applies — it lives under that one `active_section`), decide it one at a time, then re-`commit-section` any other affected section to match.
   - **Shape-level** (`reforms_shape=false`): `$INDUCTIVE_GATE_CTL gate-reopen --gate G1`, correct the shape with the user, then re-descend the spine. Committed `<S>.md` files and the EP ledger survive a reopen — only gate status resets.

**Close criterion:** `recompose_check` passes all fields; call `$INDUCTIVE_GATE_CTL gate-close --gate G4 --payload '<recompose_check JSON>'` after the user confirms the integrated solution is coherent.

### Write outputs

**Per-section files** are written incrementally during Gate 3 at `commit-section` — not here. Gate 4 only finalises the DQI. There is **no merged document** and **no `_overview` file**.

Each `<SECTION>.md` written at `commit-section` holds that section's figure(s) — deepening across KW where it refined — and resolved decisions, drawn in the section's `presentation.allowed` carrier, obeying `presentation.forbidden`:

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

- **One view, a figure stack per section:** each section step gets its own figure in that section's `presentation.allowed` carrier (deepening across KW within), obeys `presentation.forbidden` — never `file:line` / code-edit prose, never a flat prose/audit/checklist artifact, never overwrite an earlier section's figure.
- **Two axes, not a tier enum:** the cross-section ladder (`coverage_sections`) and the within-section KW gradient. `methods` discover (action); KW judges (ruler) — never iterate once per KW; the iteration unit is the open point.
- **Gate altitudes:** Gate 1 is shape-first (no sections, no code, no implementation detail; load-bearing claims at shape altitude → shape constraints on confirm). Gate 2 is background (no checkpoint; interrupt only on a shape-breaking divergence). Gate 3 is the only discovery gate and the only dialogue-by-section gate; Gate 4 audits and **never discovers or fixes** — it names problems and routes them back to the owning gate, where the fix is user-decided.
- **Focus guard is mechanical:** sections are peers with a default order; `activate-section` to any section is free, but every state-mutating command (`register-ep`, `update-ep`, `commit-section`, `skip-section`) is rejected unless its target equals `active_section`.
- **Write timing:** per-section `<S>.md` is written at `commit-section` (Gate 3); `inductive-dqi.json` is finalized in Gate 4. No merged document, no `_overview` file.
- **Lazy, one at a time:** read code only as each section requires (no unrelated scans); decide one point at a time (no batching); never raise an EP for content already settled by the scope doc or a shape constraint.
- **Stage-agnostic:** never hardcode a stage's cache subdir / upstream path / section set — use the dispatch inputs and the fetched `coverage_sections`.
