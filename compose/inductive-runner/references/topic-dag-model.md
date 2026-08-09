> Part of inductive-runner · reusable seeking-map model and tool contract

# Topic DAG Model

Defines AI discovery and seeking-only structure over `gap` Topics from
[`topic-model.md`](topic-model.md). This model depends on the Topic and Grain
definitions there; `topic-model.md` does not depend on this file.

**Scope:** Applies to inductive seeking views. Landscapes are recomputed from
declared inputs and are not persisted by this model.

---

## Inputs

- **Induction context** — required.
- **Settled facts** — required.
- **Cognitive frame** — required to apply the Grain contract from
  `topic-model.md`.
- **Human corrections** — optional review controls after initial presentation:
  add, correct, or remove a Topic.

---

## Discovery

AI autonomously derives the initial working set of temporary `gap` Topics from
the induction context and settled facts. This is the main discovery path; use
autonomous judgment, not a scripted detector.

Each build recomputes discovery from its declared inputs. It keeps no hidden
Topic registry and grants neither priority nor adoption authority.

Human changes are corrections to the presented landscape, not a parallel
discovery source. The Review step below owns them.

## Topic DAG

The **Topic DAG** represents prerequisite or upstream-support dependencies
among the temporary `gap` Topics in a returned landscape. Each node carries
grain assigned under `topic-model.md`. Grain does not determine direction: a
fine-grained Topic may still be upstream.

The DAG excludes adopted Topics.

The **upstream frontier** is the set of nodes with no unresolved upstream
prerequisite in the current DAG. It supplies guidance, not mandatory selection
order.

---

## `topic-landscape`

**Purpose:** Discover and assemble a global seeking view: first the context
needed to judge what remains unresolved, then the Topic DAG.

**Inputs:** Induction context, settled facts, and cognitive frame. After initial
presentation, accept optional human corrections.

**Delivers:** A human-confirmable view containing:

1. **Seeking context**
   - **Direction** — what the induction context requires dialogue to settle;
   - **Settled coverage** — what settled facts already pin;
   - **Overall unresolved areas** — broad areas still unresolved, without
     embedding Topic nodes or edges.
2. **Topic DAG** — temporary `gap` Topics, their upstream-support dependencies,
   grain labels, and upstream frontier.

**Build:** AI discovers the initial Topic set, applies Grain, assembles the DAG,
and presents the view.

**Review:** The human may add, correct, or remove Topics. AI reconciles the
requested changes with settled facts, recomputes affected grain and edges, and
re-presents the complete view. Repeat until the human confirms it. Corrections
remain active while visible and relevant in the current dialogue; after a
context transition, the human must restate any correction that must carry
forward.

**Select:** Human confirmation authorizes node selection but does not adopt a
Topic. Selecting a node supplies that Topic and a **source anchor** identifying
the selected DAG node. The anchor is absent before selection, required for
adoption, and discarded afterward; do not copy it into Topic state or a
landscape-receipt summary.

**Invalidate:** A relevant change to the induction context, settled facts, or
human corrections before selection invalidates the current landscape and any
confirmation. Rebuild, re-present, and reconfirm before selection.

**Constraints:** Do not rank by grain, build an adopted-Topic DAG, invent
Topics that ignore settled facts, persist Topics or corrections, or fold
Topics, DAG nodes and edges, or grain into Seeking context.

---

## Boundaries

- Discovery, seeking-map structure, review, and selection live here; Topic
  states and Grain live in `topic-model.md`.
- Seeking context belongs to `topic-landscape`; it is not a shared portrait
  model.
- This model does not adopt Topics, persist state, write receipts, own caller
  routing, or prove close.
