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

- [judgment] {user's assessment or conclusion about the problem or options}
- [preference] {preferred approach, without a hard rationale}
- [concern] {risk or worry surfaced during the session}
- [excluded] {direction or option already ruled out, with reason}

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

## Assumptions & Risks

> Status values: `[待验证]` (default) · `[已验证]` (confirmed at R / RR Released / M-L batch-confirmed) · `[失效]` (invalidated via RS Register Reopen Protocol)
> H-risk Verification: Method / Owner / Timing / Release condition. M/L Verification: Accepted.

| # | Assumption | Source | Risk | Failure Consequence | Verification | Status |
|---|-----------|--------|------|---------------------|-------------|--------|
| A1 | | Q/E/D/X | H | | Method: ... / Owner: ... / Timing: ... / Release condition: ... | [待验证] |
| A2 | | | M | | Accepted | [已验证] |

---

## Execution Analysis

### Acceptance Criteria

{observable, verifiable success criteria}

**Gap (if any):** {what the implementation is expected to produce that falls short of the above; if none, write "None"}

---

### Impact Surface

| Layer | Affected Area | Change Type | Notes |
|-------|--------------|-------------|-------|
| | | add / modify / delete / read-only | |

---

### External Dependencies

| Dependency | Contract | Authoritative Source | Confirmation Mechanism |
|------------|----------|---------------------|------------------------|
| | | | |

---

### Implementation Sketch

**Key changes:** {what components / modules / files will be added, modified, or removed}
**Critical constraints:** {non-obvious constraints that affect how this can be implemented}
**Reversibility:** {easy / partial / hard — and why}
