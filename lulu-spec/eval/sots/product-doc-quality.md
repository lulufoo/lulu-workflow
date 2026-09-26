# Product Document Quality SoT

**Role:** EvalSoT (A) for `lulu-spec` dimension `product-doc-quality`.
**Status:** ⚠️ Proposed runtime template.

## Boundary

This SoT is the twelve PDQA quality criteria for a product-doc EvalTarget **B**.
The paired Method defines altitude, traversal, Decision Traceability evidence,
severity priority, and finding serialization.

## Lens Substance

### 1 — Opening Arc

**Checks:** Are problem, timing, and observable goal reviewable?

**Pass:** A reviewer can restate the problem, why now, and the observable goal
without guessing.

**Gap:** Problem, timing, or goal is missing, implicit, or unreviewable.

### 2 — User Grounding

**Checks:** Do primary users and an interpretable usage situation exist?

**Pass:** Primary users and at least one concrete usage situation are named.

**Gap:** Users or usage situation are missing or generic beyond interpretation.

### 3 — Capability and Surfaces

**Checks:** Are in-scope capabilities and visible objects enumerable without
technical detail?

**Pass:** Capabilities and visible objects can be listed at product altitude.

**Gap:** Scope is a slogan, or capabilities leak into implementation detail.

### 4 — Flow and Boundaries

**Checks:** Are one main path and protected exclusions clear?

**Pass:** A main path and the exclusions that protect it are explicit.

**Gap:** Main path or exclusions are missing, mixed, or unbounded.

### 5 — Acceptance Closure

**Checks:** Are done conditions observable and traced to the goal?

**Pass:** Done conditions are observable and map back to the stated goal.

**Gap:** Done is unobservable, or does not trace to the goal.

## Cross-Lens Integrity

### 6 — Internal Consistency

**Checks:** Do sections contradict on capability, user, or outcome?

**Pass:** Capability, user, and outcome claims agree across sections.

**Gap:** Two sections contradict on a material capability, user, or outcome.

### 7 — Unambiguity and Terminology

**Checks:** Do scope, actors, and object names admit one reasonable
interpretation?

**Pass:** Names and scope terms have one reviewable reading.

**Gap:** A material term admits two readings that change the product.

### 8 — Decision Traceability

**Checks:** Does B itself cite a decision basis for goals and scope, and mark
expansions as explicit?

**Pass:** Goals and scope in B have a citable decision basis inside B, or B
names an expansion as such.

**Gap:** B expands or shifts goals or scope without a citable decision basis
in B.

## Sign-off Executability

### 9 — Observability of Done

**Checks:** Can stakeholders judge goal achievement without opening a
technical plan?

**Pass:** Goal achievement is judgeable from the product-doc alone.

**Gap:** Judging done requires a technical plan or implementation artifact.

### 10 — Explicit N/A and Assumptions

**Checks:** Are thin surfaces and product assumptions declared without forcing
technical feasibility decisions?

**Pass:** N/A surfaces and product assumptions are explicit.

**Gap:** Thin areas are implicit, or the doc forces stack/feasibility choices.

### 11 — Scope Protectors

**Checks:** Do exclusions make adjacent out-of-scope work clear?

**Pass:** Exclusions name the adjacent work that is out of scope.

**Gap:** Exclusions are missing, or do not protect an adjacent scope.

## Non-Happy Visibility

### 12 — Empty and Failure Visibility

**Checks:** Are common empty or key-failure outcomes visible at product
altitude, or explicitly deferred?

**Pass:** Empty and key-failure outcomes are stated or explicitly deferred.

**Gap:** Empty or key-failure outcomes are omitted without a deferral.
