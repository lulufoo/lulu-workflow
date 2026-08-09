> Part of inductive-runner · reusable Topic and adopted-topic view contracts

# Topic Model

Defines the reusable Topic model, Topic grain, and adopted-topic tools. Calling
flows supply inputs, own operations, and decide when to invoke each tool.

**Scope:** Applies to inductive flows. Views are recomputed from declared inputs;
this model owns no persistence.

---

## Inputs

- **Induction context** — required. Supplies the cognitive frame and intent
  anchor for the design commitment under discussion.
- **Settled facts** — required. Situate the induction and constrain
  adopted-topic work.
- **Current Topic** — optional. An adopted Topic in focus for a contextualized
  view.

---

## Topic

A **Topic** is a design-commitment slice that dialogue must settle within an
induction context.

### States

| State | Meaning |
|-------|---------|
| `gap` | A temporary, non-adopted Topic in the current `topic-landscape`. |
| `adopted` | Human-adopted and in active work. |
| `concluded` | Conclusion summarized and human-confirmed; ready for fact production. |

Transitions: `gap` → `adopted` → `concluded`.

## Grain

**Grain** places a Topic's design commitment on an ordered abstraction scale:
smaller grades are coarser; larger grades are finer.

AI assigns grain after understanding the Topic. Grades default to **1–3** but
are extensible. Grain is independent of Topic state. `topic-landscape` displays
it for `gap` Topics, but grain determines neither seeking priority nor DAG
direction.

Derive grain from the cognitive frame in the induction context alone. The
cognitive frame supplies the commitment's domain or genre, not the scale
itself; do not use the intent anchor or participant-specific inputs. A missing
cognitive frame is an input-resolution failure. This model defines no tier
table or coarse/fine examples and owns no grain persistence.

## `topic-portrait`

**Purpose:** Before deep work, establish a grounded adopted-topic view that
defines what must become determinate and what lies outside the Topic.

**Prerequisite:** A current Topic with `adopted` state is available.

**Inputs:** Induction context, settled facts, the current Topic, and verified
project material relevant to that Topic.

**Delivers:** One compact view in this semantic order:

1. **Grounding** — the system/capability location, relevant component or
   contract/state boundary, and settled design facts that locate the Topic.
2. **Closure target** — what design result must become determinate, why it
   matters to the overall induction, and which unresolved area it closes.
3. **Boundary** — adjacent Topics, implementation detail, or unauthorized
   higher-level changes that this Topic does not settle.

**Facts-first grounding:** Apply evidence in this order:

1. settled design facts define the target design;
2. the adopted Topic scope and induction context constrain that target;
3. project evidence locates the current system and its constraints.

Project evidence must not override settled target design. When current
implementation and target design differ, show the current → target gap instead
of collapsing the target into the current state.

**Grounding outcomes:**

- If the design has no existing implementation surface, state that explicitly
  and continue.
- If the Topic requires an existing-system location but evidence cannot locate
  it, return `Blocked`; do not enter deep work or invent a location.

**Closure-target authority:** Refine the target from the provisionally adopted
Topic scope, induction context, and settled facts. The portrait creates no new
persisted field. If the human materially corrects the target, the caller must
rebind the corrected Topic scope before continuing.

**Rules:** Grounding, Closure target, and Boundary must refer to the same design
object. Keep the view short and scannable; the semantic order is fixed, but no
visual template is required. Do not repeat the seeking map or its global
unresolved-area overview.

**Constraints:** Present it only for an adopted Topic. It may return `Blocked`
but must not mutate Topic state, confirm a conclusion, produce facts, or own
caller routing.

---

## Boundaries

- Topic state and grain are independent of seeking-DAG topology. A `gap` Topic
  is nevertheless managed through `topic-landscape`.
- `topic-portrait` owns adopted-topic grounding, closure target, and boundary.
- The question driver is distinct from Topic views and owns no Topic state.
- This model defines neither caller workflow, persistence, nor close proof.
