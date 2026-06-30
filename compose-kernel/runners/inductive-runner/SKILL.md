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
INDUCTIVE_DIR   = $INDUCTIVE_OUT_DIR/inductive-scope          # per-section scope files (the only scope artifacts init reads)
INDUCTIVE_DQI   = $INDUCTIVE_OUT_DIR/inductive-dqi.json
```

---

## Script Macros

| Macro | Command |
|-------|---------|
| `$FETCH_COMPOSE` | `python3 "$SKILL_ROOT/compose-kernel/scripts/io/fetch_compose_framework.py" --role <role> --profile "$COMPOSE_PROFILE" --project-root "$(pwd)" --cycle-id "$CYCLE_ID"` |

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

- **AI leads the spine, the user drives the descent.** AI knows the next gate and exposes the section ladder + the open points at the current section (recommendations). The **user chooses** which point to expand, whether to skip it, and when to move on or stop.
- **AI output is a recommendation, not a verdict.** Phrase as "I lean X because…; the implication is…; expand this?" — leave the decision to the human.
- **AI gates, it does not auto-advance.** AI blocks moving to the next section until the current section's blocking points are resolved or explicitly skipped by the user. AI never self-judges "good enough" — gate close is the user's.
- **Parallel inlet, open the whole session:** at any section, the user may inject a point AI missed ("add a fallback design"); register it (`source: human_inlet`) under the relevant section and treat it like any other open point — do not side-channel append it.
- **One point at a time** — never batch multiple decisions into one prompt.
- Fetch `SCAN_CRITERIA` once before Gate 3 (`$FETCH_COMPOSE --role inductive-scan-criteria`); it configures the coverage ladder (`coverage_sections`), the methods + weights, the KW stop-gate semantics, and mandatory coverage.
- Fetch `section-form-registry` once before Gate 3 (`$FETCH_COMPOSE --role section-form-registry`); cache each touched section's `presentation.allowed` / `presentation.forbidden`. Every Gate 3 figure uses an allowed carrier for its section and obeys the forbidden list — no `file:line` / code-edit prose as the body form.

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

**Close criterion:** the user confirms the spine, the To-Be structure, and the boundary (e.g. "形状确认" / "shape confirmed"). Corrections are folded in and the view re-presented until confirmed. On confirmation, the load-bearing claims become **shape constraints** — invariants Gate 3 must respect and must not re-open.

---

## Gate 2 — Grounding (background)

**Goal:** a fast, autonomous sanity-check that the confirmed shape's spine/topology is not fundamentally wrong. **Not** a user-facing audit; **not** an exhaustive line-level grounding (that happens lazily per section in Gate 3).

1. Read only enough code to confirm the spine and the To-Be topology are real (the main blocks exist / can exist, the key relations are plausible).
2. **Surface upward only if a divergence breaks the shape** — i.e. the spine or topology is wrong. Then stop and reopen Gate 1 with the specific shape correction.
3. Otherwise stay silent: record grounding notes as fuel for Gate 3. **Do not** present a confirmation table and **do not** ask the user to confirm grounding.

**Close criterion (automatic):** no shape-breaking divergence. Proceed to Gate 3 without a user checkpoint. (A shape-breaking divergence is the only thing that interrupts the user.)

---

## Gate 3 — Refine (section ladder)

**Goal:** refine the architecture view **one section at a time along the coverage ladder, coarse → fine**. At each section: discover the open points in that design dimension, let the user expand and decide them, then move on. Discover and decide are interleaved per section — not two global batches. This is what makes convergence feel like understanding an architecture, not triaging a bug list.

**Ladder (from `SCAN_CRITERIA.expose_axis.coverage_sections`, ordered):** walk the sections in the order the fetched criteria declare (tech-design example: `I` → `ST` → `KD` → `IF` → `VD` → `OD`).
The ladder is a scaffold, not a script: AI prunes sections with no open point and may surface a lateral point before moving on. Sections **not** in `coverage_sections` are **peeled** — covered by the Gate 1 shape or the deferred bucket, not re-discovered here.

**Two axes inside a step:**
- **methods = the action.** At section S, run the `methods` whose `sections` include S; each scans (view + on-demand grounding) and emits candidate gaps of its type (`finds`).
- **KW = the ruler, not a loop.** A candidate is a real open point only if it leaves one of S's KW criteria false (section-kw-criteria). KW is evaluated to (a) qualify candidates and (b) decide when S is clear enough to leave (default KW3). **Never iterate once per KW** — the iteration unit is the open point.

**Per section step S (start at the coarsest in the ladder):**

1. **Ground on demand (background):** read only the code S needs as fuel. No audit table.
2. **Discover in S's dimension:** run S's methods; keep a candidate only if it leaves a KW criterion of S false. **First subtract the shape constraints** (Gate 1 confirmed claims): a point those already settle is not an open point — do not re-surface it with shape-contradicting options. If a constraint settles only part of a point, keep the open residue. A gap that belongs to a different section (dimension) is **not** pulled up — it waits for that section's step.

```
id:           EP-NNN
section:      <section ID — the ladder step; routes the resolution into that section's file>
block:        <To-Be architecture block it hangs under>
method:       <method ID that surfaced it>
kw:           <the KW criterion of this section it leaves false>
type:         broken_invariant | undecided | undefined_contract
description:  <design gap in this dimension>
code_refs:    [<file::symbol (line)>, ...]
confidence:   direct | inferred
blocking:     true | false
source:       ai_scan | human_inlet
status:       open
```

3. **Draw S's figure + recommend (not a dump):** present S's figure in the carrier its section prescribes (`presentation.allowed`; e.g. a dependency/flow/state-machine diagram for a structure section, a contract/field table for an interface section), obeying `presentation.forbidden` (no `file:line`/code-edit prose). Within S the figure deepens across KW (coarse → fine); earlier sections' figures stay as the map — do not overwrite them. Hang S's open points under their blocks (blocking marked) as recommendations — "in this dimension these are open; which to expand?".
4. **User drives:** the user expands a point, skips it, or injects one AI missed (parallel inlet). For each expanded point, decide it **one at a time** — AI gives leaning + rationale + implication; user decides; record `status → resolved` + `resolution` and fold the decision into S's figure. Skipped → `status: deferred`.
5. **Section stop-gate:** AI **blocks moving on** until every `blocking` point in S is resolved or explicitly skipped by the user. (S reaches KW3-level clarity — its KW criteria up to the target hold.)
6. **Next section:** AI proposes the next section on the ladder; the user confirms, or stops if the solution is detailed enough.

**Mandatory coverage:** the `mandatory_coverage_prompt` sections (tech-design example: `OD`, `VD`) must be reached or consciously skipped. For any with no point, explicitly ask whether a degradation / rollback / observability / verification point should be added — the guaranteed hearing for the human inlet.

**Close criterion:** every `blocking` point across visited sections is resolved or deferred, and the user confirms the ladder is detailed enough.

---

## Gate 4 — Recompose + Output

**Goal:** verify the resolved set re-forms a single coherent solution, then write outputs. This gate prevents the decomposition from losing the whole.

1. Reassemble the resolved decisions and self-check:
   - **reforms_shape** — do the resolved points still constitute the Gate 1 shape?
   - **shape_absorbed** — is every confirmed shape constraint folded into its owning section file (topology → `ST`, invariants/spine → `I`, boundary → its section)? No load-bearing constraint may live only in working memory — `_overview` is a cold-start scaffold, not an output, so anything it held must now have a section home.
   - **conflicts** — do any two decisions contradict (e.g. lifecycle vs state authority)?
   - **buildable / reversible / verifiable** — does the integrated solution hold as one whole?
2. Present the recompose self-check. If `reforms_shape` / `shape_absorbed` is false or conflicts exist, return to Gate 1 (shape) or to the relevant Gate 3 section (the conflicting / unabsorbed points).

**Close criterion:** the user confirms the integrated solution is coherent.

### Write outputs

Write **per-section files** — the only scope artifacts init reads. One write pass at Gate 4 only. There is **no merged document** and **no `_overview` file**: the global architecture view is persisted structurally in `INDUCTIVE_DQI.architecture_view`, and its load-bearing constraints are absorbed into the section files (the `shape_absorbed` check above).

**Per-section files** under `INDUCTIVE_DIR/` — one per touched section, in `coverage_sections` order:

```
INDUCTIVE_DIR/<SECTION>.md     ← one file per touched section (ST.md, I.md, IF.md, OD.md, …)
```

Each `<SECTION>.md` holds that section's figure(s) — deepening across KW where it refined — and resolved decisions, drawn in the section's `presentation.allowed` carrier, obeying `presentation.forbidden`:

```markdown
<!-- section-key:<SECTION> -->
### [<SECTION>] <localized section label>

<the section's figure(s) in its form carrier — coarse→fine across KW where it deepened>
- <resolved decision (one bullet), with code anchor>

> 代码引用：<this section's code_refs, deduplicated>
> 待决（deferred）：<this section's deferred points — become OQ in design-doc>
```

> The `<!-- section-key:KEY -->` anchor is what the grounding resolver maps and compose Initializing reads to load a section's slice as its `I*` grounding (alongside the decision-doc SSOT).

**`INDUCTIVE_DQI`** (`inductive-dqi.json`):

```json
{
  "version": "1",
  "source_scope_doc": "<path>",
  "architecture_view": {
    "as_is": "<structural before: blocks + topology>",
    "to_be": "<structural after: blocks + topology>",
    "scope": { "in": ["..."], "out": ["..."] },
    "affected_files": ["<file/module block>", "..."],
    "spine": "<center of gravity>",
    "traces_to": "<upstream direction>"
  },
  "exposed_points": [
    {
      "id": "EP-001", "section": "OD", "block": "<To-Be block>",
      "method": "operability_check", "kw": "<KW criterion left false>",
      "type": "undecided", "description": "...", "code_refs": ["..."],
      "confidence": "inferred", "blocking": true,
      "source": "human_inlet", "status": "resolved", "resolution": "..."
    }
  ],
  "recompose_check": {
    "reforms_shape": true, "shape_absorbed": true, "conflicts": [],
    "buildable": true, "reversible": true, "verifiable": true
  }
}
```

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

- **One architecture view, a stack of figures:** all gates refine the same view coarse→fine; each section step gets its *own figure* in that section's carrier (deepening across KW within), and earlier figures stay as the map — do not overwrite, and do not emit a flat prose/audit/checklist artifact per step.
- **Form carrier per figure:** every figure uses one of its section's `presentation.allowed` carriers and obeys `presentation.forbidden` — never `file:line` / code-edit prose as the body form.
- Gate 1 is shape-first: a coarse architecture view (As-Is/To-Be + scope + affected files), no sections, no code reading, no implementation detail. Load-bearing claims stay at shape altitude; implementation risks belong to Gate 3. On confirmation they become shape constraints.
- Gate 2 is background: no user checkpoint; interrupt only to reopen Gate 1 on a shape-breaking divergence.
- Gate 3 advances **one section at a time** along `coverage_sections`. Discover **only in the current section's dimension** — a gap belonging to another section waits for that section's step. Subtract shape constraints before exposing a point. AI blocks moving on until the section's blocking points are resolved or skipped; the user drives which points to expand and when to move on.
- **Two axes, not a tier enum:** the cross-section ladder (`coverage_sections`) and the within-section KW gradient. **`methods` discover (action); KW judges (ruler) — never iterate once per KW.** The iteration unit is the open point.
- Sections are never the Gate 1 driver and never the Gate 1 grouping. In Gate 3 the section **is** the dialogue step; the **persisted output is filed per section** (KW-layered within).
- Read code only as each section requires; do not scan unrelated modules.
- Decisions are taken one point at a time; do not batch.
- Do not write the per-section files or `inductive-dqi.json` until Gate 4 (Recompose). There is no merged document and no `_overview` file: the global architecture view lives in `INDUCTIVE_DQI.architecture_view`, and its load-bearing constraints must be absorbed into the owning section files (`shape_absorbed`).
- Do not generate exposed points for content already fully resolved in the scope doc or fixed by a shape constraint.
- **Stage-agnostic:** never hardcode a stage's cache subdir or upstream path — use the dispatch inputs; never hardcode the section set — use the fetched `coverage_sections`.
