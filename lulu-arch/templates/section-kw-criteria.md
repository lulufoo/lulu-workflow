# Tech Arch (Topic) — Section KW Criteria

Topic-level architecture shaping only — not feature solution design or execution planning.

---

## CTX

| ID | Criterion |
|---|---|
| KW1 | Can state "why architecture shaping happens now" (trigger) |
| KW2 | Can state "current technical situation / verified constraint state" |
| KW3 | Can state "cost of leaving architecture uncertainty unresolved" (impact) without naming the adopted direction |

## AD

| ID | Criterion |
|---|---|
| KW1 | Can name the topic-level architecture direction at reviewable granularity |
| KW2 | Can state high-level realization actions (not an implementation checklist) |
| KW3 | Can state observable criteria that show the direction holds (generic, not product-specific field lists) |

## BD

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "which systems or capability domains this architecture shaping covers" |
| KW2 | Can state "which architecture paths are explicitly excluded and what boundary or invariant each exclusion protects" |
| KW3 | Can state "which invariants must hold for the architecture direction in AD across future features" |
| KW4 | Can state "scope, exclusions, and invariants are unambiguous and non-contradictory" |

## SH

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "which subsystems/components the system is structured into" |
| KW2 | Can state "each component's responsibility, its structural dependencies (calls/reads/writes/data flow), and relationship to existing assets" |
| KW3 | Can state "the structural dependencies are coherent — no dangling or contradictory couplings" |
| KW4 | Can state "the design structure is expressed clearly enough (preferably as an architecture diagram) for the downstream feature cycle to inherit it without re-deriving" |

## FD

| KW | Verifiable intent attributes |
|----|------------------------------|
| KW0 | Cannot be named |
| KW1 | Can state "how future features would attach to the capability domains in SH as dependency-ordered feature-milestone nodes, without re-deriving partitions" |
| KW2 | Can state "each feature-milestone node's depends-on edges and the contract or invariant anchor it must consume" |
| KW3 | Can state "the dependency order is acyclic and each node's prerequisites are fully stated" |
| KW4 | Can state "the downstream feature cycle can inherit the feature-milestone node and its dependencies without re-deriving them; when cross-boundary flows matter, architecturally significant boundaries are named without field-level contract detail" |

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
| KW2 | Can state "relationship to gaps in AD/SH/FD/KD" |
| KW3 | Can state "no repetition of closed KD content" |
| KW4 | Can state "each item is labeled blocks-next-cycle or non-blocking with closure conditions" |
