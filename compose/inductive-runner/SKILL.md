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
| `$INTENT_BASELINE_REFS` | JSON array of 意图基准 refs (e.g. `lulu-spec`); a G3 generative source (via the `intent_coverage` method) **and** the G5 algorithm-A safety-net; empty → both no-op |
| `$NORM_CONSTRAINT_REFS` | JSON array of 规范约束 refs (stage-level); a G3 generation-time precondition (leanings form *within* it — a boundary, not a gate) **and** the G5 algorithm-C audit baseline; empty → both no-op |
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

**Three discovery sources feed one EP ledger** (the inductive dual `Induce`; see `compose/references/compose-theory.md`): `ai_scan` (methods over code), `human_inlet` (user-proposed, AI-mapped to a section), and — when the profile declares the `intent_coverage` method — `intent_baseline` (that method compares each section's mapped demands against its figure at `frontier_kw`). All three subtract `¬Settled`; `ai_scan`/`intent_baseline` apply the frontier-KW filter, `human_inlet` is exempt. Design SSOT: `docs/biz/inductive-intent-baseline-source.md`.

**Shape claims are constraints, not re-openable questions.** The Gate 1 load-bearing claims, once confirmed, become invariants. Gate 3 discovery **subtracts** what they already fix — it does not re-surface a settled call as an open point with shape-contradicting options.

Understanding a design is itself a process: the user resolves a sweep's open points, then chooses to re-sweep. So the descent is **user-driven**: each sweep AI presents the **frontier map** — every unsettled section's coarsest open point, fueled by background grounding; the user picks which point to expand, may skip, may inject a point AI missed, and decides when to re-sweep and when the whole view is detailed enough.

---

## Pipeline

**Gate 1 Shape → Gate 2 Grounding (background) → Gate 3 Refine (frontier sweep) → Gate 4 Recompose → Gate 5 Provenance**

The gates progressively refine the **same shape artifact** from coarse to fine. Each gate has an observable close criterion, defined in that gate's own file. Do not advance until it is met.

### Gate routing

<HARD-GATE>
Before executing any gate, read the corresponding gate file first — each gate file is that gate's execution entry (its steps, subagent dispatch, close criterion, and reopen routing all live there; this index does not duplicate them). Every gate file's first step is `$INDUCTIVE_GATE_CTL resolve-context` (Gate 5: `$PROVENANCE_GATE_CTL resolve-context`) — mandatory, do not skip or rely on memory.
On a `gate-reopen` call from within a gate file, load the target gate's file next — do not re-execute the reopening gate's already-closed steps.
Do NOT rely on memory or prior context for gate execution steps.
</HARD-GATE>

| Gate | File | Load condition |
|------|------|-----------------|
| G1 — Shape | `gates/g1-shape.md` | Dispatched from parent compose stage `start` (session init), or resuming with `active_gate=G1` |
| G2 — Grounding | `gates/g2-grounding.md` | G1 closed |
| G3 — Refine | `gates/g3-refine.md` | G2 closed (`verdict=ok`) |
| G4 — Recompose + Audit | `gates/g4-recompose.md` | G3 closed (`check-coverage` passes) |
| G5 — Provenance | `gates/g5-provenance.md` | G4 closed |

---

## Roles & Global Rules

- **Collaboration baseline (load-bearing — never violate).** AI leads **cognition** (explore via scan + on-demand grounding, think it through, surface the problems, offer a grounded leaning) and **leads the spine** — it knows the next gate. The **user leads decision and progress**: which point to deepen, whether to skip, when to re-sweep, when to stop. Each sweep AI exposes the **frontier map** — every unsettled section's coarsest open point — as recommendations. AI output is therefore **always an exploration finding + leaning**, phrased *"I lean X because…; the implication is…; expand this?"* — never a multiple-choice menu the user merely answers, never a verdict.
- **Who fixes what (load-bearing — never violate).** Every *how-to-fix* decision is the **user's**. The **AI only recommends** (leaning + rationale + implication). The **scripts only move state and keep the ledger** — never a semantic judgement about content. **Gate 4 only finds and names problems; it never fixes them.** A fix is always made back in the gate that owns it (Gate 3 for a section, Gate 1 for shape), through the normal AI-recommends → user-decides loop — never auto-applied and never patched inside the auditor.
- **Two-layer focus guard.** Sections are peers; `activate-section <S>` is always permitted. **Discovery is global (read-only):** a sweep may scan *all* unsettled sections to build the frontier map. **Mutation is focus-guarded:** every state-mutating operation (`register-ep`, `update-ep`, `set-frontier`, `append-to-section`, `clear-section`, `skip-section`) must target the `active_section` — run `$INDUCTIVE_G3_SECTION_CTL activate-section --section <S>` first to shift focus. You may *see* a gap in any section during a sweep, but to *register/decide* it you must activate that section.
- **`human_inlet` is a peer discovery source, not a safety net.** The user may raise a design point in **any dimension, at any altitude, at any time** — on equal footing with the AI-scan frontier map. It is **AI's job to map** that free-form point to its owning section: run `$INDUCTIVE_G3_SECTION_CTL activate-section --section <mapped S>` first, then `register-ep --json '{"source":"human_inlet","method":"human_inlet","kw":"<KW criterion it leaves false>",...}'` (the mutation focus guard still applies — the EP lands under the mapped `active_section`). A `human_inlet` point is **exempt from the frontier-altitude filter** — it need not be the section's coarsest open point nor sit at the current `frontier_kw`; never reject it for being "off-frontier". If it maps to no `coverage_section` (it belongs to a peeled section or the shape), **say where it goes** — fold it into a shape constraint or the deferred bucket — never silently drop it. The remaining EP lifecycle (resolve/defer/fold into figure) is identical to an AI-scan EP.
- **`intent_baseline` is a peer source via the `intent_coverage` method (active only when the profile declares it).** Each sweep, after `ai_scan` registers, the method compares each section's mapped demands (from the delivered demand manifest, else `scan-criteria` fallback) against its figure at `frontier_kw`; per unmet demand it attaches `intent_ref` to a matching open EP or registers a new one under the same `(section, KW, topic)` identity. Completeness is a close-time recheck against the manifest (no separate ledger); `$INTENT_BASELINE_REFS` empty or no method declared → no-op.
- **One point at a time** — never batch multiple decisions into one prompt.
- **Session state persists across turns.** At the start of each new turn, call `$INDUCTIVE_GATE_CTL resolve-context` to restore `active_gate`, `active_section`, open-EP count, and `architecture_view`. Never rely on conversation memory alone.
- Fetch framework data per the schedule in **Script Macros** — never read `workflow-config.json` directly.

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

**`INDUCTIVE_DQI`** (`inductive-dqi.json`) is assembled by `$INDUCTIVE_GATE_CTL` — not hand-written. Top-level keys: `version`, `source_scope_doc`, `architecture_view`, `exposed_points`, `recompose_check`. It aggregates the already-documented parts: `architecture_view` + `shape_constraints` (the G1 close payload), an `exposed_points` snapshot (the EP ledger; per-EP contract in `inductive_exposed_points_schema.py`), and `recompose_check` (the merged structural + semantic predicates written on G4 close — see `gates/g4-recompose.md` step 4).

---

## Constraints

The mechanical invariants the gates above must not violate (the *why* is in **Method**; these are the hard guardrails):

- **One view, a figure stack per section:** each section owns its own figure in that section's `presentation.allowed` carrier (deepening across KW within), obeys `presentation.forbidden` — never `file:line` / code-edit prose, never a flat prose/audit/checklist artifact, never overwrite another section's figure.
- **Two axes, not a tier enum:** breadth (`coverage_sections`) + within-section KW gradient (the only granularity axis); never iterate once per KW — the iteration unit is the open point.
- **Frontier sweep, not section-at-a-time:** Gate 3 advances all unsettled sections' maturity together — each sweep surfaces every section's coarsest open point at its `frontier_kw`; a section clears only when its `frontier_kw` reaches the target (default KW3) with no blocking-open EP.
- **Open-point altitude = frontier KW:** every frontier-map open point is *selected* and *worded* at its section's `frontier_kw` row of `KW_CRITERIA` — no deeper-KW substance (signatures / counts / `file:line`) in the problem statement; that detail lives only in the leaning/接地 part. `human_inlet` points are exempt (any altitude, any dimension; AI maps them to a section).
- **Collaboration baseline:** AI leads cognition (explore / think / surface + a grounded leaning); the user leads decision and progress. AI output is an exploration finding + leaning — never a multiple-choice menu the user answers, never a verdict.
- **Lazy, one at a time:** examine source material only as each section requires (no unrelated scans); decide one point at a time (no batching); never raise an EP for content already settled by the scope doc or a shape constraint. Gate 3 shallow grounding runs in a dispatched subagent (whole sweep, step 1); deep grounding for the chosen point also runs in a dispatched subagent (one point, step 4a); leanings and decisions stay inline (step 3–4b). Gate 4's semantic audit (`conflicts` / `buildable` / `reversible` / `verifiable`) also runs in a dispatched subagent (step 2) — only its mechanical structural half (`reforms_shape` / `shape_absorbed`, step 1) is a direct script call.