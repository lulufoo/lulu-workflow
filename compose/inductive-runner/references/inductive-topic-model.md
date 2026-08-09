> Part of inductive-runner · reusable model and topic-view tool contracts

# Inductive Topic Model

Defines a reusable topic model for inductive work and the contracts for its
topic views and question driver. A calling flow supplies inputs, owns
operations, and decides when to invoke each tool.

**Scope:** The model applies to inductive flows. It has no dedicated runner
directories or persisted views; recompute each view from its declared inputs on
every run.

---

## Inputs

The model accepts:

- **Induction context** — required. Supplies a cognitive frame for the design
  commitment under discussion and an intent anchor for its intended boundary.
- **Settled facts** — required. Established information that constrains
  discovery and situates the overall induction.
- **Human candidate signals** — optional. Potential topics surfaced through
  dialogue.
- **Current topic** — optional. An adopted topic in focus for a contextualized
  topic view.

---

## Domain model

### Topic

A **topic** is a design-commitment slice that dialogue must settle within an
induction context.

#### States

| State | Meaning |
|-------|---------|
| `gap` | Visible on the seeking map; not human-adopted. Colloquial「缺口」means this state only. |
| `adopted` | Human-adopted and in active work. |
| `concluded` | Conclusion summarized and human-confirmed; ready for fact production. |

Transitions: `gap` → `adopted` → `concluded`.

#### Grain

**Grain** places a `gap` topic's design commitment on an ordered abstraction
scale: smaller grades are coarser; larger grades are finer.

**Rules:** AI assigns grain after understanding the topic. Grades default to
**1–3** but are extensible. Grain neither determines seeking order nor applies
to `adopted` or `concluded` topics.

**Input and exclusions:** Derive grain from the cognitive frame alone. The
cognitive frame supplies the commitment's domain or genre, not the scale itself;
do not use the intent anchor or participant-specific inputs. A missing cognitive
frame is an input-resolution failure. This model defines no tier table or
coarse/fine examples.

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

The DAG excludes adopted topics.

## Topic discovery

**Topic discovery** is a dialogue mechanism that makes potential topics visible
as candidates.

Human and AI are parallel candidate sources:

- **Human discovery** — The human surfaces a candidate through dialogue.
- **AI discovery** — AI surfaces a candidate by synthesizing the induction
  context and settled facts; it uses autonomous judgment, not a scripted
  detector.

Discovery only surfaces candidates: it grants neither priority nor adoption
authority, builds no Topic DAG, and changes no topic state. Only human
confirmation adopts a candidate.

## Induction portrait

An **Induction portrait** summarizes the overall induction state. It is a
session view recomputed from the induction context and settled facts and supplies
shared context for topic tools.

It answers:

1. **Direction** — what the induction context requires the dialogue to settle
2. **Settled coverage** — what settled facts already pin
3. **Overall status** — what is stable and which broad areas remain unresolved,
   without enumerating topic candidates
4. **Current-topic relation** — when a current topic is in focus, why it
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

**Inputs:** Induction context, settled facts, human candidate signals, and the
cognitive frame for grain.

**Delivers:** A human-confirmable view containing the Induction portrait,
followed by the Topic DAG and grain labels on its `gap` nodes. Selecting a map
node supplies a candidate to the calling flow.

**Constraints:** Require human confirmation. Do not rank by grain, build an
adopted-topic DAG, invent candidates that ignore settled facts, or fold
candidates, DAG nodes and edges, or grain into the Induction portrait.

---

### `topic-portrait`

**Purpose:** Assemble an adopted-topic view: first the Induction portrait with
its current-topic relation, then the topic's framing.

**Prerequisite:** A current topic with `adopted` state is available.

**Inputs:** Induction context, settled facts, and the current topic.

**Delivers:** The contextualized Induction portrait followed by the current
topic's framing.

**Constraints:** Present it only for an adopted topic. Do not use its output as
the seeking spine or to reorder the Topic DAG. Keep the current-topic relation
in the Induction portrait; do not duplicate it in framing.

---

### `topic-question-driver`

**Purpose:** Optionally work an adopted Topic toward complete closure by
producing one minimum design judgment at a time.

**Prerequisite:** The current Topic is adopted and its `topic-portrait` has been
presented.

**Contract:** [`topic-question-driver.md`](topic-question-driver.md).

**Boundary:** This stateless tool produces dialogue candidates only. The caller
owns invocation, free dialogue, conclusion confirmation, fact production, and
exit.

---

## Boundaries

- The Induction portrait, Topic DAG, and grain are distinct: shared context,
  dependency map, and abstraction label, respectively.
- Grain is an abstraction label, not a workflow priority.
- The question driver is distinct from the topic views and owns no Topic state.
- This model defines neither caller workflow, persistence, nor completion or
  close proof.
