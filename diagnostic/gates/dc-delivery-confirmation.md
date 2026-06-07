> Part of diagnostic-workflow · loaded by Gate Routing in `$SKILL_DIR/SKILL.md`

## Decision-Doc Format

Write to `$CACHE_DIR/<cycle_id>/{cache_subdir}/decision-doc.md` (where `{cache_subdir}` is derived from `--stage` as described in §Start Step 2).

**Section filtering:** If a `## Domain Constraints` section lists forbidden sections, omit those sections entirely from the written document. If no Domain Constraints are present, write all sections below.

<HARD-GATE name="Decision-Doc Prerequisites">
Read `$SKILL_DIR/templates/decision-doc.template.md`.
Apply Section filtering above using resolved Domain Constraints before writing.
</HARD-GATE>

---

## Self-Review (before Delivery)

Before presenting to user, scan the written decision-doc for:

1. **Completeness:** all sections filled; no empty cells in tables; User Prior captured
2. **Consistency:** Decision Rationale references E trade-offs; Verification Items map to High-risk assumptions
3. **Gap check:** if Expected Outcome < Acceptance Criteria, the gap is documented (not silently dropped)

Fix inline. No separate review round needed.

---

## DC - Delivery Confirmation

**Entry paths (any one satisfies):**
- Path 1: R exit 3 — all assumptions `[已验证]`, no uncertain items (Group Loop B skipped)
- Path 2: V direct — no high-risk, medium/low batch-confirmed, no Risk Release needed
- Path 3: RR exit 1 — all Released, Assumption Log has no new `[待验证]` entries

After self-review passes (decision-doc already written, Risk Release statuses updated):
1. Present the following key sections **in the conversation** (do not just show file path):
   - Decision Rationale
   - Scope (including explicit exclusions)
   - Assumptions & Risks (all items with risk levels)
   - Verification Items
2. Ask user: "Are these decisions correct? Any items to re-open?"
3. If any item is flagged: trigger RS on the corresponding gate; re-close all invalidated gates before proceeding.
   > **DC-triggered RS baseline:** when RS is triggered from DC, use the already-written decision-doc as the authoritative baseline snapshot — do not reconstruct state from conversation memory. RS step 2 (clear conclusion zones) and step 3 (propose 3-state labeling) are executed against the decision-doc's recorded state.
4. Only after user's explicit confirmation that everything is correct, write terminal state:

```bash
# session-state.md at <cycle_id>/{cache_subdir}/session-state.md
current_state: Delivered
```

5. Tell user the next step.

> **HARD GATE — skipping the plan stage is forbidden.**
> The decision-doc is the required input for the next stage, not a substitute for it.
> Do NOT suggest `/tech-work-order`, `/tech-code`, or any other stage directly.

Follow the After DC routing from `## Domain Constraints` (if present). If running standalone with no
domain constraints:
   - Product-level decision → **must** proceed to `/product-plan` (alias: `pp`)
   - Tech-level decision → **must** proceed to `/tech-plan` (alias: `tp`)
   - Mixed → **must** proceed to `/product-plan` first
