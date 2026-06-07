---
input:
  domain_constraints: |
    Evaluated by diagnostic kernel `Domain Constraints HARD-GATE`.
    Determines which sections to omit before writing.
    Pass the resolved constraints when applying this template.
---

# Decision: {title}

**Date:** YYYY-MM-DD
**Intent:** {one-line summary of the intent input}

---

## User Prior

{key judgments, preferences, concerns, and excluded options stated by the user during the session}

---

## Problem Definition

{problem statement}

**Known Constraints:** {non-negotiable constraints}

---

## Direction Comparison

| Direction | Core Approach | Pros | Cons |
|-----------|--------------|------|------|
| Option A | | | |
| Option B | | | |

**Excluded Directions:**

| Direction | Reason for Exclusion |
|-----------|---------------------|
| | |

---

## Decision Rationale

Chose **[option]** because {rationale referencing direction comparison trade-offs}.
Excluded **[option]** because {rationale}.

---

## Scope

**Applies to:** {what this decision covers}
**Explicitly excludes:** {what this decision does not cover}

---

## Acceptance Criteria

{observable, verifiable success criteria}

---

## Impact Surface

{affected domains, including outside the system}

---

## External Dependencies

| Dependency | Contract | Authoritative Source | Confirmation Mechanism |
|------------|----------|---------------------|------------------------|
| | | | |

---

## Implementation Cost

{time / people / resource estimate with rationale}

---

## Expected Outcome

{expected output quality and level; alignment with Acceptance Criteria}

---

## Assumptions & Risks

| # | Assumption | Source | Risk Level | Failure Consequence | State |
|---|-----------|--------|------------|---------------------|-------|
| A1 | | | High/Medium/Low | | [待验证] |

---

## Verification Items

| # | Assumption | Verification Method | Owner / Timing | Release Condition | Status |
|---|-----------|---------------------|----------------|-------------------|--------|
| V1 | A{n} | | | | ⬜ |
