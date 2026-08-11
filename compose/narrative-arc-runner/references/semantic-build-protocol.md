# Semantic build protocol

Shared cognition for the unified narrative-arc pipeline. Load after Input;
before `contracts/delivery.md`.

## Steps

1. `$NARRATIVE_ARC_BUILD_CTL context …` → `$ARC_CONTEXT`.
   Supplies facts, Role, Domain, and registry. Missing context is failure — never
   fall back to a lens projection. Re-read Role `priority_tendency` and Domain
   `expression_conventions.scannability` from `$ARC_CONTEXT` before building.

2. **Listen-who (arc build):**

   | Decision | Listen to | Hardness |
   |---|---|---|
   | Group/leaf **titles and grouping shape** | Substance story in facts (objects, behaviors, contract surfaces, end-state, verification, …) | **Must** |
   | Group/leaf **order** | Role `priority_tendency` | **Must** (exception: fact dependency forces prerequisite first) |
   | **Intra-tier order** (groups tied in one `priority_tendency` slot) | Descending narrative altitude: whole before its parts | **Should** (tie-breaker; explicit Role order or fact dependency overrides) |
   | Fact membership + phase-2 write-unit split | Lens tags + registry lens relations | **Must** — never whole-document leaf order; never the presentation title schema |
   | Split / do not mix | Domain `expression_conventions.scannability` (full text for active profile) | **Must** |
   | Genre mission / through-line check | Domain `cognitive_frame` / `audience_type` | **Must** (enforced by step 5) |

3. Build the tree from the facts' substance story; topic is provenance only.
   Optional `tree` packaging, depth unrestricted. Map each fact exactly once.
   Composite / pending-split facts → `excluded` (or `unresolved` if blocked).

4. **Top-level title discipline** (`tree` roots only):

   | Principle | Rule |
   |---|---|
   | Single duty | One chapter duty per top title. Never glue duties with 与/及/和, `and`, or `&`. |
   | Chapter altitude | Top level = through-line chapter stations only. Demote leaf-level concerns to children. |
   | Flow | After shape is set, reorder only. Flow never decides split/merge. |

   Conflict exits: overflow → child under a single-duty parent; never glue for
   flow; never merge unequal altitudes to shorten the path.

   **Non-top title discipline** (all titles below `tree` roots):

   | Principle | Rule |
   |---|---|
   | Name, don't assert | Title = station name (object, surface, behavior area), never a compressed fact claim; claims live in content. |
   | No claim chains | Pairing related aspects is fine; chaining assertions is not — name their shared object instead. |
   | Altitude nesting | Child strictly narrower than parent; siblings at comparable altitude. |

5. **Pre-persist self-check (hard gate).** Run every item; any hit → rebuild
   titles/shape and re-run this step. Never persist a failing candidate.
   - **Lens-catalog detector:** list each top-level group's member-fact lens
     set. All (or nearly all) groups single-lens-pure → the tree is a lens
     projection with laundered titles → rebuild. Business-sounding titles do
     not exempt; splitting one lens into several pure groups does not exempt.
   - **Mapping-not-narrative detector:** a majority of leaves each holding
     one fact under a title that restates that fact → this is fact mapping,
     not narrative building → regroup leaves around shared objects,
     behaviors, and end-states.
   - Top titles glued with 与/及/和 (or `and`/`&`), or too many tops that
     read as leaf concerns → split or demote (title discipline above).
   - Non-top titles reading as fact claims or assertion chains → rename to
     station names, or merge same-object siblings (non-top discipline above).
   - Single-leaf mix that violates Domain `scannability` → split.
   - Order inverted vs `priority_tendency` with no fact-dependency reason →
     reorder.
   - Outline drifted from Domain `cognitive_frame`, or not a reviewable
     through-line for `audience_type` → fix (thicken opening info if needed;
     do not force a fixed N-act directory).

   Record the outcome in the candidate's `meta.note` when useful, e.g.
   `self-check: lens-catalog=clear; grouping=narrative`.

6. `$NARRATIVE_ARC_BUILD_CTL validate-candidate …` before each persistence.
   Machine validation gates structure and coverage only — it cannot detect a
   lens catalog; that is what step 5 exists for.

## Build prohibitions

Do not use registry lens order, Role priority, lens tags/relations, or Role
vocabulary as the presentation title schema — Role `priority_tendency` orders
groups/leaves and never generates titles or a mandatory top count; lens
relations guide argumentation within content, not the visible directory. Do
not force background / analysis / solution — or any fixed N-act label set —
as the **only** allowed top-level packaging (reading aids OK); do not glue
top-level duties with 与/及/和, `and`, or `&`; do not invent facts.

A `write_ready` candidate must not contain a mapped fact with empty
`lens_tags`, and each chapter `lens` must be ∈ that fact's `lens_tags`.
