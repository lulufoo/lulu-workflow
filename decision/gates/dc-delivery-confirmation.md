> Part of decision-workflow · gate contract · via `$SKILL_DIR/runners/dc-delivery-runner/SKILL.md`

## Decision-Doc Format

Decision-doc is **not** maintained during execution. Gate payloads live in `gate-payloads/<G>.json`; `$SESSION_INTEGRITY render` builds `decision-doc.md` once before user confirmation. Section layout: `dec_decision_doc_schema.py` / `$SESSION_INTEGRITY render --help`.

**Section filtering:** If Domain Constraints omit sections, render skips them. If no Domain Constraints are present, write all sections.

<HARD-GATE name="Decision-Doc Prerequisites">
Template SSOT: `$FETCH_TEMPLATE --section decision --key decision_doc_template_url`
Apply Section filtering using `$CTX.domain_constraints` after `resolve-context`.
</HARD-GATE>

---

## Self-Review (before Delivery)

Before presenting to user:

1. Run `$GATE_CONTROL check-delivery-ready` (structural audit). Fix every error in stdout before continuing.
2. Run **Decision Eval** (`$EVAL_CONTROL --workflow lulu-decision` + `$DEC_EVAL`; see dc-delivery-runner). Fail → summarize issues → RS (`realign_gate`); do not remediate inside Eval.
3. On Eval pass, run `$SESSION_INTEGRITY render` (delivery `decision-doc.md`).

EvalTarget is the bound `decision-eval-target.md` (Eval generation rule). Delivery doc remains a separate generation rule from the same authority.

---

## DC - Delivery Confirmation

**Entry paths (any one satisfies):**
- Path 1: R exit 3 — all assumptions are `decision`, `[已验证]`, no uncertain items (Group Loop B skipped; **no** `implementation` on this path)
- Path 2: V direct — no decision RR-scope items; implementation Handoffs recorded; medium/low decision batch-confirmed
- Path 3: RR exit 1 — all RR-scope Released, Assumption Log has no new `[待验证]` entries

After structural audit and Decision Eval pass, and after render:

1. Present the following key sections **from `decision-doc.md`** in the conversation (do not show file paths):
   - Decision Rationale
   - Scope (including explicit exclusions)
   - Assumptions & Risks (all items with risk levels, Class, and Verification content)
   - Call out any `Class=implementation` Handoff lines (remind only; do not block delivery)
2. Ask user: "Are these decisions correct? Any items to realign?"
3. If any item is flagged: load `$SKILL_DIR/runners/rs-realign-runner/SKILL.md` on the corresponding gate; update all `stale` gates before proceeding.
   > **DC-triggered RS baseline:** when RS is triggered from DC, pin fresh `$CTX` via `resolve-context` after any sync — do not reconstruct state from conversation memory alone.
4. Only after user's explicit confirmation:

```bash
$GATE_CONTROL gate-close --gate DC --payload '{"user_confirmed": true}'
$GATE_CONTROL complete
```

5. Tell the user `$CTX.after_dc.user_message` from resolve-context.
