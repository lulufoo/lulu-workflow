> Part of inductive-runner · adopted-topic portrait tool contract

# `topic-portrait`

Before deep work, establish a grounded adopted-topic view that defines what
must become determinate and what lies outside the Topic. Topic states and Grain
live in [`topic-model.md`](topic-model.md).

**Scope:** Inductive adopted-topic views. Views are recomputed from declared
inputs; this contract owns no persistence.

---

## Purpose

Ground the adopted Topic, state its closure target, and bound what it does not
settle.

## Prerequisite

A current Topic with `adopted` state is available.

## Inputs

Induction context, settled facts, the current Topic, and verified project
material relevant to that Topic.

## Delivers

One compact view in this semantic order:

1. **Grounding** — the system/capability location, relevant component or
   contract/state boundary, and settled design facts that locate the Topic.
2. **Closure target** — what design result must become determinate, why it
   matters to the overall induction, and which unresolved area it closes.
3. **Boundary** — adjacent Topics, implementation detail, or unauthorized
   higher-level changes that this Topic does not settle.

## Facts-first grounding

Apply evidence in this order:

1. settled design facts define the target design;
2. the adopted Topic scope and induction context constrain that target;
3. project evidence locates the current system and its constraints.

Project evidence must not override settled target design. When current
implementation and target design differ, show the current → target gap instead
of collapsing the target into the current state.

## Grounding outcomes

- If the design has no existing implementation surface, state that explicitly
  and continue.
- If the Topic requires an existing-system location but evidence cannot locate
  it, return `Blocked`; do not enter deep work or invent a location.

## Closure-target authority

Refine the target from the provisionally adopted Topic scope, induction
context, and settled facts. The portrait creates no new persisted field. If the
human materially corrects the target, the caller must rebind the corrected
Topic scope before continuing.

## Rules

Grounding, Closure target, and Boundary must refer to the same design object.
Keep the view short and scannable; the semantic order is fixed, but no visual
template is required. Do not repeat the seeking landscape or its global
unresolved-area overview.

## Constraints

Present it only for an adopted Topic. It may return `Blocked` but must not
mutate Topic state, confirm a conclusion, produce facts, or own caller routing.

## Boundaries

- Owns adopted-topic grounding, closure target, and boundary only.
- Does not own seeking discovery, Topic DAG assembly, caller workflow, or close
  proof.
