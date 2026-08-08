> Part of inductive-runner · G2 Topic Loop contract only · loaded from `../gates/g2-topic-loop.md`

# G2 Topic Model

Defines G2's topic cognitive model and topic-view tool contracts. The Gate owns
topic operations and decides when to invoke each tool.

**Scope:** G2 only. Do not load this file from another gate or flow. These tools
have no dedicated runner directories or persisted views. Recompute each view
from its declared inputs on every run.

---

## Cognitive model

### Topic

A **topic** is a design-commitment slice that dialogue must settle relative to
the Topic Loop's D1 (`cognitive_frame`) and D2 (`intent_anchor`) goals.

It is not `cycle_type=topic`, blueprint topic-level product grain, or a G3
`open`.

#### States

| State | Meaning |
|-------|---------|
| `gap` | Visible on the seeking map; not human-adopted. Colloquial「缺口」means this state only. |
| `adopted` | Human-adopted and in deep work. |
| `concluded` | Conclusion summarized and human-confirmed; ready for `fact-runner`. |

Transitions: `gap` → `adopted` → `concluded`.

#### Grain

**Grain** places a `gap` topic's design commitment on an ordered abstraction
scale: smaller grades are coarser; larger grades are finer.

**Rules:** AI assigns grain after understanding the topic. Grades default to
**1–3** but are extensible. Grain neither determines seeking order nor applies
to `adopted` or `concluded` topics.

**Input and exclusions:** Derive grain from D1 only. D1 supplies the stage's
genre frame, not the scale itself; do not use D2 or Role fields. Because the
domain-instance schema requires D1, its absence is a scope/fetch failure. This
model defines no `compose-profile` tier table or coarse/fine examples.

#### Framing

A topic's **framing** captures:

1. **Source anchor** — its seeking-DAG node, when one exists
2. **Definition** — what it is
3. **Purpose** — what problem it solves

On the seeking map, the DAG node identifies the topic. Grain labels a `gap`
topic's abstraction level; it is neither topic identity nor part of framing.

### Topic DAG

The **Topic DAG** represents prerequisite or upstream-support dependencies
among visible `gap` topics. Granularity does not determine direction: a
fine-grained topic may still be upstream.

AI derives `gap` candidates from D1, D2, and settled facts, then arranges them
into the DAG. This uses autonomous judgment, not a scripted detector.

The DAG excludes adopted topics and G3 `open` items. Stage-specific discovery
from decision/spec inputs is out of scope.

### Induction portrait

An **Induction portrait** summarizes the Topic Loop's overall induction state.
It is a session view recomputed from D1, D2, and settled facts and supplies
shared context for topic tools.

It answers:

1. **Direction** — what D1 and D2 require the Topic Loop to settle
2. **Settled coverage** — what settled facts already pin
3. **Overall status** — what is stable and which broad areas remain unresolved,
   without enumerating topic candidates
4. **Current-topic relation** — when an adopted topic is in focus, why it
   matters, which unresolved area it addresses, and how settling it advances
   the overall induction

The first three answers form the shared core. The current-topic relation is
optional context on the same model, not a second portrait type. An Induction
portrait does not contain topic framing, candidate lists, Topic DAG nodes or
edges, or grain labels.

---

## Tool contracts

### `topic-landscape`

**Purpose:** Assemble a seeking view: first the Induction portrait without a
current-topic relation, then the Topic DAG.

**Inputs:** D1, D2, and settled facts for both the Induction portrait and
candidate discovery; D1 alone for grain.

**Delivers:** A human-confirmable view containing the Induction portrait,
followed by the Topic DAG and grain labels on its `gap` nodes. Selecting a map
node supplies a candidate for the Gate's Adopt operation.

**Persistence:** Every run writes a receipt through
`$INDUCTIVE_GATE_CTL record-topic-landscape`, with `purpose` (`seek`, `refresh`,
or `pre_close`), a new `run_id`, and caller-reported `gap_remaining`. Do **not**
hand-write the receipt.

**Constraints:** The assembled view requires human confirmation. Do not rank by
grain, build an adopted-topic DAG, invent candidates that ignore settled facts,
or treat candidates as G3 `open`. The caller judges `gap_remaining`; the script
does not discover gaps. Keep candidates, DAG nodes and edges, and grain outside
the Induction portrait.

---

### `topic-portrait`

**Purpose:** Assemble an adopted-topic view: first the Induction portrait with
its current-topic relation, then the adopted topic's framing.

**Prerequisite:** A current adopted-topic binding is readable through
`$TOPIC_CURRENT_CTL` (`set` during Adopt).

**Inputs:** D1, D2, settled facts, and the adopted binding.

**Delivers:** The contextualized Induction portrait followed by the adopted
topic's framing.

**Constraints:** Invoke and present it only after Adopt; presentation is
required, but confirmation is not. Do not use its output as the seeking spine
or to reorder the Topic DAG. Keep the current-topic relation in the Induction
portrait; do not duplicate it in framing.

---

## Boundaries

- The Induction portrait summarizes D1+D2 traction and settled coverage; it
  does not decide or replace `design_goal_met`.
- The Induction portrait, Topic DAG, and grain are distinct: shared context,
  dependency map, and abstraction label, respectively.
- Grain is unrelated to KW altitude or conversation L1–L3.
- Fact production, collab-arc display, current-topic binding, and close proof
  are Gate concerns; this model defines none of them.
