> Part of diagnostic-workflow · loaded by Gate Routing in `$SKILL_DIR/SKILL.md`

## Decision-Doc Format

Decision-doc is maintained incrementally on disk at `$CACHE_DIR/<cycle_id>/{cache_subdir}/decision-doc.md` (see §Start). Each gate-close patches its sections; registers sync into §6 via `$REGISTER_CONTROL`.

**Section filtering:** If a `## Domain Constraints` section lists forbidden sections, omit those sections from init and patches. If no Domain Constraints are present, write all sections.

<HARD-GATE name="Decision-Doc Prerequisites">
Template SSOT: `$FETCH_TEMPLATE --section diagnostic --key decision_doc_template_url`
Apply Section filtering using resolved Domain Constraints at session start.
</HARD-GATE>

---

## Self-Review (before Delivery)

Before presenting to user, scan the written decision-doc for:

1. **Completeness:** all sections filled; no empty cells in tables; User Prior captured with type tags
2. **Consistency:** Decision Rationale references E trade-offs; all H-risk rows in Assumptions & Risks have Verification content (Method / Owner / Timing / Release condition)
3. **Gap check:** if `Gap (if any)` is non-empty, the gap is documented and a reopen was either triggered or explicitly accepted

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
   - Assumptions & Risks (all items with risk levels and Verification content)
2. Ask user: "Are these decisions correct? Any items to re-open?"
3. If any item is flagged: load `$SKILL_DIR/runners/rs-reopen-runner/SKILL.md` on the corresponding gate; re-close all invalidated gates before proceeding.
   > **DC-triggered RS baseline:** when RS is triggered from DC, use the already-written decision-doc as the authoritative baseline snapshot — do not reconstruct state from conversation memory. RS step 2 (clear conclusion zones) and step 3 (propose 3-state labeling) are executed against the decision-doc's recorded state.
4. Only after user's explicit confirmation:

```bash
$GATE_CONTROL gate-close --gate DC --payload '{"user_confirmed": true}'
$GATE_CONTROL deliver
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
