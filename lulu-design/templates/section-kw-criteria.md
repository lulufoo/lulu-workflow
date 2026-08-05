# Tech Design — Section KW Criteria

---

## CTX

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "what the current state or problem to solve is"; first paragraph opens with problem narrative — reader understands the situation without first reading file:line references |
| KW2 | Can state "trigger, current state, and impact (problem cost) — all three elements are present and self-contained; reader needs no external links to form a complete problem picture" |
| KW3 | Can state "content focuses on problem narrative; no GOAL / SCOPE content is mixed in" |
| KW4 | Can state "narrative is unambiguous; reviewer can proceed to design without follow-up questions about context" |

## GOAL

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "what will be different after design is complete (before → after, reviewer can judge)" |
| KW2 | Can state "how this success state traces back to goals or AC semantics in decision-doc" |
| KW3 | Can state "success state does not conflict with SCOPE / SCOPE boundaries" |
| KW4 | Can state "success state is specific enough at review level that ST can be elaborated within the design document, without relying on task decomposition or run commands" |

## SCOPE

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state in-scope surfaces and explicit out-of-scope / deferred items |
| KW2 | Can state why these boundaries hold, with decision or context basis |
| KW3 | Can state where boundaries with GOAL success state are, and what each exclusion protects |
| KW4 | Can state reviewer can judge scope sufficiency with no conflicts relative to GOAL |

## DECISION

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "what key decisions were made (including confirmed premises and human-adopted design intents)" |
| KW2 | Can state "why this judgment — based on design reasoning, not guesswork" |
| KW3 | Can state "which alternatives were rejected and the rejection rationale (including rejected AI-proposed alternatives, if any); and not violating I / SCOPE" |
| KW4 | Can state "under what conditions this judgment would be invalidated, or a decision needs to be reopened" |

## I

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "what constraints or invariants must always hold" |
| KW2 | Can state "what violation of this constraint would break (verifiable)" |
| KW3 | Can state "how to judge whether this constraint is satisfied or violated (semantic level, not test commands)" |
| KW4 | Can state "whether this constraint has exceptions, and the control conditions for those exceptions" |

## ST

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "where this solution sits in the existing system, and what the core components / modules and their responsibility divisions are" |
| KW2 | Can state "why this structure (including cross-boundary dependencies), with decision-doc or system constraint basis; for non-obvious structural choices, can point to the corresponding DECISION entry" |
| KW3 | Can state "what the key dependency directions, cross-boundary data or control flow paths are, and that they are consistent with GOAL / SCOPE / I" |
| KW4 | Can state "system position and cross-boundary relationships are unambiguous at review level; structure division is stable so IF / DECISION can continue to elaborate; tech-plan needs no inference about this section's design intent; and no construction checklist is introduced"; **when interaction or state changes are involved: can state named states, transition trigger conditions, and end-state semantics for each path (including idle-state UI control semantics when applicable), consistent with GOAL / I** |

## IF

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "what the cross-module contracts are (API / event / data / error semantics)" |
| KW2 | Can state "why this contract design (field structure, error classification, etc.) — with design or codebase basis" (note: protocol selection belongs to DECISION; cross-version coexistence does not belong in the Lens V2 intent table (optional arc-leaf narrative only); this level verifies design choices within the current contract only) |
| KW3 | Can state "contracts map one-to-one with module divisions in ST; no dangling interfaces" |
| KW4 | Can state "contract semantics are complete: reviewer can judge coverage and error semantics; tech-plan needs no inference about contract design intent; and does not rely on specific use-case paths or execution commands"; **for success / error paths with different terminal semantics, those are distinguishable to contract consumers** |

## SEAM

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state which adjacent layers/components the seam connects |
| KW2 | Can state who provides / who consumes / who must not demand what |
| KW3 | Can state obligations are distinct from internal I/IF/ST norms and from DEP version ledgers |
| KW4 | Can state both sides are named so reviewer can judge ownership without follow-up |

## VERIFY

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "how to verify design correctness (unit / integration / E2E / contract test division)" |
| KW2 | Can state "why this verification approach fits this design, with GOAL / IF basis" |
| KW3 | Can state "how ACs or success states are semantically mapped to verification approaches, consistent with IF contracts" |
| KW4 | Can state "verification strategy is complete: includes positive mapping (AC → verification approach, consistent with IF contracts) and reverse criterion (what observable outcome would indicate the design is wrong); design assumptions are closed in DECISION/facts or scope shrink; design-external blockers are tracked on stage agenda" |

## RISK

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state known risks, fragile assumptions, or open questions relevant to this design |
| KW2 | Can state what cost is accepted or what remains unresolved |
| KW3 | Can state risks are not rewritten locked norms (I/IF/ST) and not a DEP ledger |
| KW4 | Can state reviewer can see residual uncertainty without mistaking it for deferred SCOPE |

## DEP

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "coarse-grained external technical dependencies for delivery (release collaboration and/or dependency upgrades) and this design's placement at design level" |
| KW2 | Can state "why these dependency / upgrade / placement constraints matter for delivery (design reasoning, not a project schedule)" |
| KW3 | Can state "dependency ledger is consistent with ST overall structure and IF provided/consumed contracts; distinct from DECISION selection rationale and RISK traffic shifting; schedules and owners are out of scope" |
| KW4 | Can state "technical dependencies are complete at review level for this demand; remaining process follow-ups are tracked outside this Intent" |

