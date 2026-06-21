> Part of diagnostic-workflow · loaded by Gate Routing in `$SKILL_DIR/SKILL.md`

## Decision-Doc Format

Decision-doc is maintained incrementally by `$GATE_CONTROL gate-close` and `$REGISTER_CONTROL sync-registers-to-doc`. Section layout and filtering: `dx_decision_doc_schema.py` / control `--help`.

**Section filtering:** If Domain Constraints omit sections, control scripts skip them at init and patch. If no Domain Constraints are present, write all sections.

<HARD-GATE name="Decision-Doc Prerequisites">
Template SSOT: `$FETCH_TEMPLATE --section diagnostic --key decision_doc_template_url`
Apply Section filtering using `$CTX.domain_constraints` after `resolve-context`.
</HARD-GATE>

---

## Self-Review (before Delivery)

Before presenting to user, run `$GATE_CONTROL check-delivery-ready`. Fix every error in stdout before continuing. Do **not** open session data files directly.

---

## DC - Delivery Confirmation

**Entry paths (any one satisfies):**
- Path 1: R exit 3 — all assumptions `[已验证]`, no uncertain items (Group Loop B skipped)
- Path 2: V direct — no high-risk, medium/low batch-confirmed, no Risk Release needed
- Path 3: RR exit 1 — all Released, Assumption Log has no new `[待验证]` entries

After `check-delivery-ready` passes:
1. Present the following key sections **in the conversation** (from `$CTX` / prior gate-close content — do not show file paths):
   - Decision Rationale
   - Scope (including explicit exclusions)
   - Assumptions & Risks (all items with risk levels and Verification content)
2. Ask user: "Are these decisions correct? Any items to re-open?"
3. If any item is flagged: load `$SKILL_DIR/runners/rs-reopen-runner/SKILL.md` on the corresponding gate; re-close all invalidated gates before proceeding.
   > **DC-triggered RS baseline:** when RS is triggered from DC, pin fresh `$CTX` via `resolve-context` after any sync — do not reconstruct state from conversation memory alone.
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
