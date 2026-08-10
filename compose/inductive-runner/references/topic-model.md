> Part of inductive-runner · Topic modeling layer (Topic, Grain, DAG)

# Topic Model

Defines the reusable Topic model for inductive seeking: Topic and states, Grain,
and the Topic DAG. Seeking-landscape and adopted-topic portrait tool contracts
are separate reference files; callers supply inputs and decide when to invoke
each tool.

**Scope:** Applies to inductive flows. Views are recomputed from declared
inputs; this model owns no persistence.

---

## Inputs

- **Induction context** — required. Supplies the cognitive frame and intent
  anchor for the design commitment under discussion.
- **Settled facts** — required. Situate the induction and constrain Topic work.
- **Cognitive frame** — required to apply Grain (from induction context).

---

## Topic

A **Topic** is a design-commitment slice that dialogue must settle within an
induction context.

### States

| State | Meaning |
|-------|---------|
| `gap` | A temporary, non-adopted Topic in a seeking view. |
| `adopted` | Human-adopted and in active work. |
| `concluded` | Conclusion summarized and human-confirmed; ready for fact production. |

Transitions: `gap` → `adopted` → `concluded`.

## Grain

**Grain** places a Topic's design commitment on an ordered abstraction scale:
smaller grades are coarser; larger grades are finer.

AI assigns grain after understanding the Topic. Grades default to **1–3** but
are extensible. Grain is independent of Topic state. Seeking views may display
it for `gap` Topics, but grain determines neither seeking priority nor DAG
direction.

Derive grain from the cognitive frame in the induction context alone. The
cognitive frame supplies the commitment's domain or genre, not the scale
itself; do not use the intent anchor or participant-specific inputs. A missing
cognitive frame is an input-resolution failure. This model defines no tier
table or coarse/fine examples and owns no grain persistence.

---

## Topic DAG

The **Topic DAG** represents prerequisite or upstream-support dependencies
among the temporary `gap` Topics. Each node carries grain. Grain does not
determine direction: a fine-grained Topic may still be upstream.

The DAG excludes adopted Topics. A seeking view may also draw settled context
nodes beside this DAG; that drawing is a presentation concern, not part of the
Topic DAG itself.

The **upstream frontier** is the set of nodes with no unresolved upstream
prerequisite in the current DAG. It supplies guidance, not mandatory selection
order.

---

## Boundaries

- Topic state and grain are independent of Topic DAG topology.
- Topic DAG semantics live here; discovery, seeking presentation, review,
  selection, and adopted-topic portrait live in their tool contracts.
- The question driver is distinct from Topic views and owns no Topic state.
- This model defines neither caller workflow, persistence, nor close proof.
