> Part of inductive-runner · G2 Topic Loop contract only · loaded from `../gates/g2-topic-loop.md`

# G2 Topic Model

Contract for G2 Topic Loop seeking and topic-context views. **Orchestration** (when to invoke named tools) lives in `../gates/g2-topic-loop.md`. This file owns topic definition/states, grain, two portrait lenses, and the inline protocols for `topic-landscape` and `topic-portrait`.

**G2-only.** Other gates/flows must not load this file. **No** independent runner directories for these two tools (MVP). **No** persistent portrait files. Recompute from current settled facts when a tool runs.

---

## Topic

A **topic** is the Topic Loop session work unit: a design-commitment slice that still needs dialogue to pin, relative to the design-convergence goals pulled by Domain D1 (`cognitive_frame`) + D2 (`intent_anchor`).

**Not** `cycle_type=topic`, **not** blueprint topic-level product grain, **not** a G3 `open`.

### States

| State | Meaning |
|-------|---------|
| `gap` | On the seeking map; not yet human-adopted. Colloquial「缺口」= a topic in this state only. |
| `adopted` | Human-adopted; deep work in progress |
| `concluded` | Summarized and human confirmed the conclusion (handoff toward fact-runner) |

Transitions: `gap` → `adopted` → `concluded`.

### Discovery (MVP)

AI enumerates **`gap`-state topic candidates** against D1+D2 and settled facts (autonomous judgment; no scripted detector). Then build the seeking DAG → human confirm → default most-upstream.

Future stage-specific discovery (e.g. decision/spec inputs) is out of this wave.

---

## Grain (definition)

**Grain** is the position, on an ordered abstraction-height dimension, of the design commitment under discussion for a topic in state **`gap`** (smaller grade = higher abstraction / coarser; larger = more concrete / finer).

### Labeling contract

1. This definition is the judgment standard; the AI grades after understanding the `gap`-state topic.
2. No stage `compose-profile` grain-tier instance table is required.
3. Default ordered grades **1–3** (extendable). Grades are orthogonal to the seeking DAG and **must not** rank seeking order.
4. Required cognitive input for grading: Domain `cognitive_frame` (D1) only — genre frame for this stage. Do **not** treat D1 as the grain scale itself. Do **not** require Role fields or Domain `intent_anchor` (D2) for grading.
5. D1 is assumed present (domain-instance schema requires it). Runtime absence is a scope/fetch failure, not a grain-side unlabeled branch.
6. Do **not** define an enumeration of “what counts as coarse vs fine” in this definition section.
7. Label **only** topics in state `gap` (not `adopted` / `concluded`).

---

## Portrait — shared pool, two lenses

Shared capability pool (session views only):

| Capability | Answers |
|------------|---------|
| Stance | Where design convergence stands now |
| Facts coverage | What settled facts already pin |
| Visible gap-state topics | What is still open for seeking |

| Lens | Carrying tool | Weight | Delivers |
|------|---------------|--------|----------|
| **1 — DAG lens** | `topic-landscape` | Visible `gap`-state topics (short stance/coverage OK) | Seeking map for human confirm |
| **2 — Topic lens** | `topic-portrait` | Stance + this topic’s place | Topic-context portrait + positioning triple |

Lens 2 is a **lens change**, not the first invention of a portrait. Lens 1 must have been shown before pretending seeking-side portrait duty is done — except when the human **direct-adopts** without a prior landscape in this turn (direct adopt is legal; close-time landscape still required).

---

## Positioning triple

When proposing or when `topic-portrait` presents the adopted topic, state:

1. **Where** (anchors a seeking-DAG node when applicable)
2. **What it is**
3. **What problem it solves**

Topic identity on the seeking map is the DAG node — **not** a fourth “gap tier” field. Grain grades label `gap`-state topics; they are not a positioning tuple member.

---

## Seeking DAG (`gap`-state topics)

1. List visible `gap`-state topics from discovery / lens-1 portrait.
2. Build a **dependency DAG among `gap`-state topics** (edge = prerequisite / upstream support). A fine-grained topic may still be upstream of others.
3. Show the full DAG for human confirm (human may edit edges / pick an entry). Default grain grades appear on nodes; grades do **not** sort order.
4. Default progress from the **most upstream** open entry after confirm.
5. Do **not** build a DAG among already-adopted topics. Do **not** treat this DAG as G3 opens.

---

## Tool protocol — `topic-landscape`

**Trigger (gate):** before AI guide-propose; when human (or AI) asks to refresh the seeking map; **before G2 close** (detection pass).

**Not required** before human dialogue direct-adopt.

**Steps:**

1. Resolve Domain `cognitive_frame` (D1) via existing scope/fetch path (grading). Use D1+D2 + settled facts for Discovery (MVP).
2. Recompute lens-1 portrait from current settled facts.
3. Enumerate `gap`-state topic candidates → seeking DAG → grade each `gap` node (Grain section).
4. Present the seeking map for human confirmation (medium deferred — any form the human can confirm). On close-time detection, the map may be shorter but must still support confirm of clear / hard-skip.
5. After confirm (seek/refresh): default next guidance from most-upstream; optional guide-propose may include the positioning triple.
6. Human may **adopt by selecting** a node/entry from this map **after pre-adopt clarify** (same adopt authority as dialogue adopt).

**Forbidden:** skip human confirm when the tool ran for propose/refresh/close-detect; rank by grain; DAG among adopted topics; invent candidates that ignore settled facts; treat candidates as G3 `open`.

---

## Tool protocol — `topic-portrait`

**Trigger (gate):** after human adopts a topic (dialogue or map select) · **before deep work**.

**Steps:**

1. Require a macro-readable adopted binding already written (`$TOPIC_CURRENT_CTL set` at adopt).
2. Recompute or project lens-2 portrait for the adopted topic (stance + place; coverage may be short).
3. Present topic-lens portrait + positioning triple (Where anchors the seeking-DAG node when one applies).
4. **Human confirms once** → only then continue deep work (solve / summarize path).
5. Do **not** treat this tool as the seeking spine (that is `topic-landscape`).

**Forbidden:** proceed into deep work without this confirm; use topic-lens output to reorder the seeking DAG; invoke before adopt binding exists.

---

## Boundaries

- Domain D1/D2 whole-loop traction and `design_goal_met` ≠ seeking DAG ≠ grain.
- KW altitude / conversation L1–L3 ≠ this grain model.
- Production (facts) ⊥ display (collab arc) remains as in the gate.
- `gap` here is a **topic state**, not a second ontology and not G3 `open`.

---

## Hard cuts

- No coarse→fine seeking main axis; no “coarsest gap first.”
- No first portrait only at adopt as if lens 1 never existed when seeking guidance was used; lens 1 precedes guide-propose.
- No product-slogan laundry lists in the gate — invoke tool names; details stay here.
- No dual persistent portrait files; no dedicated runner packages for these tools in this wave.
- No loading this file outside G2.
