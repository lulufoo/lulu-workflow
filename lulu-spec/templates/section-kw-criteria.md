# Product Spec — Section KW Criteria

> Reference for prober-runner execution. KW-level definition per section: what an independent observer can know about this intent without guessing.
>
> **Pairing:** `20-product-spec-section-registry.json` — product intent chain (`PB → RN → GO → UR → SN → SC → IO → FL → NG → AC`).
>
> **Pairing (form):** `25-product-spec-section-form-registry.json` — per-intent F/C (presentation layer only; intent substance stays in section-registry).
>
> **Altitude:** KW checks product-doc substance. Test commands, metric thresholds, owners/RACI, and implementation mechanics are out of altitude unless a KW row explicitly allows an explicit N/A or deferral note.

**Section keys:** match `section_order` / `sections.{key}` in section registry (`pst_section_registry_url`). Locate the block `## {section_key}` below — not outline H2 display titles from product-doc.

---

## PB

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "what the current core problem to solve is" |
| KW2 | Can state "what the problem evidence is (decision-doc or verified facts, not guesses)" and "what user/business impact remains if unsolved" |
| KW3 | Can state "which problems explicitly do not belong to this PB (already elsewhere or out of scope)" |
| KW4 | Can state "under what changes PB no longer holds and must be rewritten" |

## RN

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "why this is to be done now (trigger/window/urgency)" |
| KW2 | Can state "the checkable basis for the timing judgment (not a vague 'this is important')" |
| KW3 | Can state "why 'do it later' is not acceptable, or when delay would be acceptable" |
| KW4 | Can state "how RN should be adjusted when the window closes or priorities reverse" |

## GO

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "what is different after completion (before → after or target outcome)" |
| KW2 | Can state "why this goal direction, rather than other reasonable directions" |
| KW3 | Can state "which other goal directions were rejected, and the rejection reasons" (or that decision-doc names no alternatives) |
| KW4 | Can state "under what premises the goal holds; how the goal should change when those premises break" |

## UR

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "who the primary users are (roles/needs)" |
| KW2 | Can state "the relationship between users and the PB core problem (who is affected by this problem)" |
| KW3 | Can state "which user groups are explicitly not in this round's service targets" (or that no exclusion matters) |
| KW4 | Can state "how UR should be revised when user assumptions change" |

## SN

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "at least one usage scenario (when, where, and how it is used)" — or an explicit N/A with a one-line reason |
| KW2 | Can state "at least one typical example that a third party can arrive at the same understanding" — required unless SN is explicit N/A |
| KW3 | Can state "which scenarios are excluded or placeholder-only (not in this round)" |
| KW4 | Can state "how SN should be adjusted when scenario premises no longer hold" |

## SC

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "which capabilities/features this round covers" |
| KW2 | Can state "why these capabilities are in scope for this round, not out of scope" |
| KW3 | Can state "where the boundary is with adjacent areas not included in scope" |
| KW4 | Can state "under what product premises scope should expand or contract" (decision process/owners are out of altitude) |

## IO

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "what the main inputs, outputs, or objects operated on are" — or explicit N/A with a one-line reason |
| KW2 | Can state "which feature point in SC each I/O object corresponds to" — required unless IO is explicit N/A |
| KW3 | Can state "which I/O is explicitly not in this round (or N/A)" |
| KW4 | Can state "how IO should be revised in sync when the object model changes" |

## FL

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "where the flow entry is (where the user enters)" |
| KW2 | Can state "the key steps of the main path (happy path)" |
| KW3 | Can state "how the flow ends or how the goal is reached (end conditions)" |
| KW4 | Can state "a product-visible empty or key-failure note for a common dead end, or an explicit deferral naming what remains undescribed" (not a full alternate-path tree) |

## NG

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "what is currently explicitly not being done" |
| KW2 | Can state "why it is not being done (active choice vs out of scope)" |
| KW3 | Can state "which GO or SC boundary this exclusion protects" |
| KW4 | Can state "under what product conditions this exclusion would become inclusion" |

## AC

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "how to judge that GO is achieved (goal-achievement criteria)" |
| KW2 | Can state "at least one set of observable, discussable completion conditions (not empty phrases like 'good experience')" |
| KW3 | Can state "how AC traces back to SC and FL (what should be observed after which flow completes)" — and to decision-doc goal/flow ids when present |
| KW4 | Can state "what remains unobserved relative to GO when acceptance fails" (approval/rework owners are out of altitude) |
