> Part of inductive-runner · topic cognition SSOT · loaded from `../gates/g2-topic-loop.md`

# Topic Cognition Model

Cognitive contract for G2 Topic Loop seeking and topic-context views. **Orchestration** (when to invoke named tools) lives in `../gates/g2-topic-loop.md`. This file owns definitions, two portrait lenses, grain, and the inline protocols for `gap-landscape` and `topic-portrait`.

**No** independent runner directories for these two tools (MVP). **No** persistent portrait files. Recompute from current settled facts when a tool runs.

---

## Grain (definition)

**Grain** is the position, on an ordered abstraction-height dimension, of the design commitment under discussion for a gap (smaller grade = higher abstraction / coarser; larger = more concrete / finer).

### Labeling contract

1. This definition is the judgment standard; the AI grades after understanding the gap.
2. No stage `compose-profile` grain-tier instance table is required.
3. Default ordered grades **1–3** (extendable). Grades are orthogonal to the gap DAG and **must not** rank seeking order.
4. Required cognitive input for grading: Domain `cognitive_frame` (D1) only — genre frame for this stage. Do **not** treat D1 as the grain scale itself. Do **not** require Role fields or Domain `intent_anchor` (D2) for grading.
5. D1 is assumed present (domain-instance schema requires it). Runtime absence is a scope/fetch failure, not a grain-side unlabeled branch.
6. Do **not** define an enumeration of “what counts as coarse vs fine” in this definition section.

---

## Portrait — shared pool, two lenses

Shared capability pool (session views only):

| Capability | Answers |
|------------|---------|
| Stance | Where design convergence stands now |
| Facts coverage | What settled facts already pin |
| Visible gaps | What is still open for seeking |

| Lens | Carrying tool | Weight | Delivers |
|------|---------------|--------|----------|
| **1 — DAG lens** | `gap-landscape` | Visible gaps (short stance/coverage OK) | Seeking map for human confirm |
| **2 — Topic lens** | `topic-portrait` | Stance + this topic’s place | Topic-context portrait + positioning triple |

Lens 2 is a **lens change**, not the first invention of a portrait. Lens 1 must have been shown before pretending seeking-side portrait duty is done.

---

## Positioning triple

When proposing or when `topic-portrait` presents the adopted topic, state:

1. **Where** (anchors a gap-DAG node when applicable)
2. **What it is**
3. **What problem it solves**

Gap identity is the DAG node — **not** a fourth “gap tier” field. Grain grades label gaps; they are not a positioning tuple member.

---

## Gap DAG (seeking spine)

1. List visible gaps from lens-1 portrait.
2. Build a **gap** dependency DAG (edge = prerequisite / upstream support). A fine-grained gap may still be upstream of others.
3. Show the full DAG for human confirm (human may edit edges / pick an entry). Default grain grades appear on nodes; grades do **not** sort order.
4. Default progress from the **most upstream** open entry after confirm.
5. Do **not** build a DAG among already-adopted topics.

---

## Tool protocol — `gap-landscape`

**Trigger (gate):** before AI guide-propose; also when human (or AI) asks to refresh the gap map.

**Steps:**

1. Resolve Domain `cognitive_frame` (D1) via existing scope/fetch path.
2. Recompute lens-1 portrait from current settled facts.
3. Derive visible gaps → gap DAG → grade each gap (Grain section).
4. Present the seeking map for human confirmation (medium deferred — any form the human can confirm).
5. After confirm: default next guidance from most-upstream; optional guide-propose may include the positioning triple.
6. Human may **adopt by selecting** a node/entry from this map (same adopt authority as dialogue adopt).

**Forbidden:** skip human confirm; rank by grain; topic↔topic DAG; invent gaps that ignore settled facts.

---

## Tool protocol — `topic-portrait`

**Trigger (gate):** after human adopts a topic · at **clarify entry**.

**Steps:**

1. Recompute or project lens-2 portrait for the adopted topic (stance + place; coverage may be short).
2. Present topic-lens portrait + positioning triple (Where anchors the gap-DAG node when one applies).
3. **Human confirms once** → only then continue deep clarify.
4. Do **not** treat this tool as the seeking spine (that is `gap-landscape`).

**Forbidden:** proceed as if clarify finished without this confirm; use topic-lens output to reorder the gap DAG.

---

## Boundaries

- Domain D1/D2 whole-loop traction and `design_goal_met` ≠ gap DAG ≠ grain.
- KW altitude / conversation L1–L3 ≠ this grain model.
- Production (facts) ⊥ display (collab arc) remains as in the gate.

---

## Hard cuts

- No coarse→fine seeking main axis; no “coarsest gap first.”
- No first portrait only at adopt; lens 1 precedes seeking guidance.
- No product-slogan laundry lists in the gate — invoke tool names; details stay here.
- No dual persistent portrait files; no dedicated runner packages for these tools in this wave.
