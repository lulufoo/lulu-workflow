# Tech Arch (Topic) — Section KW Criteria

Topic-level architecture shaping only — not feature solution design or execution planning.

---

## SI

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "what triggered this architecture exploration and what the current technical situation is" |
| KW2 | Can state "trigger, current situation, and cost of unresolved architecture uncertainty — all three present and self-contained" |
| KW3 | Can state "the intended topic-level architecture direction is named without mixing BD/SH/KD content" |
| KW4 | Can state "a reviewer can judge direction readiness without follow-up on context" |

## BD

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "which systems or capability domains this architecture shaping covers" |
| KW2 | Can state "which architecture paths are explicitly excluded and what boundary or invariant each exclusion protects" |
| KW3 | Can state "which invariants must hold for the architecture direction in SI across future features" |
| KW4 | Can state "scope, exclusions, and invariants are unambiguous and non-contradictory" |

## SH

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "core modules/subsystems and their responsibilities at topic granularity" |
| KW2 | Can state "dependency directions and relationship to existing assets at structural level — without decision trade-off reasoning" |
| KW3 | Can state "how future features would attach to this structure without re-deriving partitions" |
| KW4 | Can state "topic structure is stable enough for downstream lulu-design to inherit partitions and premises; when cross-boundary flows matter, architecturally significant boundaries are named without field-level contract detail" |

## KD

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "what key architecture choices were adopted at topic level" |
| KW2 | Can state "why each choice — architecture trade-off reasoning, not authorization alone" |
| KW3 | Can state "which alternatives were rejected and why, without violating BD invariants" |
| KW4 | Can state "conditions under which a decision would be reopened" |

## OQ

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "what each open assumption/risk is at topic level" |
| KW2 | Can state "relationship to gaps in SI/SH/KD" |
| KW3 | Can state "no repetition of closed KD content" |
| KW4 | Can state "each item is labeled blocks-next-cycle or non-blocking with closure conditions" |
