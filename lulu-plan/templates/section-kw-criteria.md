# Tech Plan — Section KW Criteria

> Reference for prober-runner execution. KW-level definition per section: what an independent observer can know about this intent without guessing.
>
> **Pairing:** `42-tech-plan-section-registry.json` — execution-readiness intent chain (`CTX → GO → SC → AR → I → SK → T → VF`).
>
> **Pairing (form):** `49-tech-plan-section-form-registry.json` — per-intent F/C (presentation layer only; intent substance stays in section-registry).
>
> **Thickness (Plan):** KW is the stop/continue ruler for deductive ceiling on that lens — not a rewrite of intake tags. Prefer thin upstream lenses (CTX/GO/SC/AR sketch) and thicker T/VF execution and verification. See archive design `compose-plan-kw-criteria-thick-thin-design.md`.

**Section keys:** match `section_order` / `sections.{key}` in section registry (`tpt_section_registry_url`). Locate the block `## {section_key}` below — not H2 display titles from tech-doc.

---

## CTX

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "what the current state or problem to solve is" |
| KW2 | Can state "why this is a problem / why action is needed now (with checkable evidence)" |

Note: Scope Non-Goals / exclusions belong to `SC`. Plan CTX does not require invalidation-trigger rows.

## GO

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "what the before and after states each are (checkable)" |

Note: Observable acceptance criteria, layered behavioral verdicts, and AC↔task mapping belong to `VF` (not Goal).

## SC

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "which surfaces this change touches (systems/repos/modules/boundaries)" |
| KW2 | Can state "which items are explicitly out of scope or deferred (Non-Goals)" |
| KW3 | Can state "where the boundary is with adjacent areas not included in scope" |

Note: No RACI / collaboration-protocol essays in SC (use `AR` sketch or `T` collaboration tasks).

## AR

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "what the core components / responsibility split are" |
| KW2 | Can state "why this structure, rather than another architectural form" |
| KW3 | Can state "what the key interfaces, data-flow, or control-flow paths are" at structural-sketch depth only |

Note: File-level edits and stepwise implementation recipes belong to `T`. Do not thicken AR to task-level depth (paired with thick `T`).

## I

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "what constraints must always hold" |
| KW2 | Can state "what violating this constraint would break" |
| KW3 | Can state "how to judge whether this constraint is satisfied or violated" |

Note: Few hard, independently checkable post-ship constraints. Not SC/AR restatements. Constraint judgment is not a VF test-case inventory.

## SK

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "what phases execution is divided into" |
| KW2 | Can state "what the completion definition is for each phase (Done When criteria)" |
| KW3 | Can state "what the prerequisites are for entering the next phase (including dependencies and reversibility)" |

Note: Each table field once; phase content column = short intent only (do not duplicate the Done When cell). No per-file tasks.

## T

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "what steps need to be executed (key file paths must be locatable when included)"; Task Index summary must state what changes (not only Create/Modify) |
| KW2 | Can state "what the completion criteria are for this step" |
| KW3 | Can state "what the prerequisites of this step are, why the execution order is as such, and which Skeleton phase it corresponds to" |
| KW4 | Can state "how to handle step failure" (including whether failure blocks downstream work; may be per phase group) |

Note: Primary home for implementation-recipe thickness (paired with thin AR).

## VF

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "how to judge that Goal (before→after) is achieved" (hosts AC / layered behavioral criteria; Goal states Before→After only) |
| KW2 | Can state "how to confirm Scope coverage has no omissions" |
| KW3 | Can state "how to verify each Invariant holds or is violated" |
| KW4 | Can state "acceptance commands/steps for completed Tasks; how to handle verification failure; which open assumptions must be closed before implementation (Must Close Before — explicit none if empty); and how to block when not closed" |

Note: When AC rows exist, AC→Task mapping is required for VF completeness.
