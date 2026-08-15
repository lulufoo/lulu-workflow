> Part of inductive-runner · seeking-landscape tool contract

# `topic-landscape`

Discover and assemble a global seeking view over `gap` Topics. Modeling
primitives (Topic, Grain, Topic DAG) live in
[`topic-model.md`](topic-model.md).

**Scope:** Inductive seeking views. Landscapes are recomputed from declared
inputs and are not persisted by this contract.

---

## Purpose

First the context needed to judge what remains unresolved, then the Topic DAG.

## Inputs

Induction context, settled facts, the project, and cognitive frame (to
apply Grain).

## Delivers

A human-confirmable view containing:

1. **Seeking context**
   - **Direction** — what the induction context requires dialogue to settle;
   - **Settled coverage** — what settled facts already pin (mark per
     Presentation);
   - **Overall unresolved areas** — broad areas still unresolved, without
     embedding Topic nodes or edges.
2. **Landscape graph** — the Topic DAG (`gap` nodes, edges, grain, upstream
   frontier) plus settled context nodes, presented per Presentation.

## Discovery

Applies when deriving the initial temporary `gap` Topic set.

1. **Topic** — One commitment the induction still needs dialogue to settle.
2. **Source** — Declared Inputs.
3. **Method** — Compare settled facts to the project, and whether those
   facts are complete for the induction context. Autonomous; not a
   scripted detector.
4. **Recompute** — Each build rediscovers from declared inputs only; no
   hidden Topic registry.
5. **Authority** — Discovery grants neither priority nor adoption authority.

## Presentation

Applies when presenting a seeking landscape.

1. **Order** — Seeking context, then landscape graph.
2. **Settled coverage** — each settled pin marked `✓`.
3. **Landscape graph** — Mermaid `flowchart`/`graph` of the full landscape
   graph (Topic DAG plus settled context); nodes show title and grain; color =
   settled / frontier / un-frontier.
4. **Must not** — primary list/table; partial graph; `✓` on graph nodes.

## Build

Discover per Discovery, apply Grain, assemble the Topic DAG, and present the
landscape graph per Presentation.

## Review

The human may add, correct, or remove Topics. AI reconciles the requested
changes with settled facts, recomputes affected grain and edges, and
re-presents the complete view per Presentation. Repeat until the human confirms
it. Corrections remain active while visible and relevant in the current
dialogue; after a context transition, the human must restate any correction
that must carry forward.

## Select

Human confirmation authorizes selection of a `gap` node only; settled context
nodes are not selectable and selection does not adopt a Topic. Selecting a
`gap` node supplies that Topic and a **source anchor** identifying the selected
DAG node. The anchor is absent before selection, required for adoption, and
discarded afterward; do not copy it into Topic state or a landscape-receipt
summary.

## Invalidate

A relevant change to the induction context, settled facts, or human corrections
before selection invalidates the current landscape and any confirmation.
Rebuild, re-present, and reconfirm before selection.

## Constraints

Do not rank by grain, build an adopted-Topic DAG as the selectable seeking
topology (settled context nodes on the landscape graph are display-only), invent
Topics that ignore settled facts, persist Topics or corrections, or fold Topics,
DAG nodes and edges, or grain into Seeking context. Do not violate Presentation.

## Boundaries

- Discovery, Seeking context, Presentation, review, and selection belong here;
  Topic / Grain / Topic DAG semantics live in `topic-model.md`.
- Seeking context is not a shared portrait model.
- This contract does not adopt Topics, persist state, write receipts, own
  caller routing, or prove close.
