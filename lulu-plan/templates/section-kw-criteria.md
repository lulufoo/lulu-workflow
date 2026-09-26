# Tech Plan — Section KW Criteria

> Per-lens KW altitude ruler: what an independent observer can know about that intent without guessing.

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
| KW1 | Can state executable steps and what each step changes (not Create/Modify labels only); each code-facing task has ≥1 workspace-locatable path from codebase read. Non-code tasks: path optional only if explicitly marked; they alone do not satisfy KW1 |
| KW2 | Can state "the Done When / completion criteria for each step" |
| KW3 | Can state "prerequisites, execution-order rationale, and the SK phase id (or explicit cross-phase) for each step" |
| KW4 | Can state "how to handle step failure" (including whether failure blocks downstream; may be per phase group; Fail may be soft for explicitly marked ops tasks) |

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
