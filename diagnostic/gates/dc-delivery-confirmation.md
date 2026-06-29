> Part of diagnostic-workflow · gate contract · via `$SKILL_DIR/runners/dc-delivery-runner/SKILL.md`

## Decision-Doc Format

Decision-doc is **not** maintained during execution. Gate payloads live in `gate-payloads/<G>.json`; `$SESSION_INTEGRITY render` builds `decision-doc.md` once before user confirmation. Section layout: `dx_decision_doc_schema.py` / `$SESSION_INTEGRITY render --help`.

**Section filtering:** If Domain Constraints omit sections, render skips them. If no Domain Constraints are present, write all sections.

<HARD-GATE name="Decision-Doc Prerequisites">
Template SSOT: `$FETCH_TEMPLATE --section diagnostic --key decision_doc_template_url`
Apply Section filtering using `$CTX.domain_constraints` after `resolve-context`.
</HARD-GATE>

---

## Self-Review (before Delivery)

Before presenting to user:

1. Run `$GATE_CONTROL check-delivery-ready` (structural audit). Fix every error in stdout before continuing.
2. Run **AI Semantic Review** per `$SKILL_DIR/session-invariants.yaml` (see runner pipeline step 4).
3. Run `$SESSION_INTEGRITY render`.

---

## DC - Delivery Confirmation

**Entry paths (any one satisfies):**
- Path 1: R exit 3 — all assumptions `[已验证]`, no uncertain items (Group Loop B skipped)
- Path 2: V direct — no high-risk, medium/low batch-confirmed, no Risk Release needed
- Path 3: RR exit 1 — all Released, Assumption Log has no new `[待验证]` entries

After structural audit and AI review pass, and after render:

1. Present the following key sections **from `decision-doc.md`** in the conversation (do not show file paths):
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

5. Tell the user `$CTX.after_dc.user_message` from resolve-context.
