---
name: diagnostic
---

# diagnostic-workflow

> Framework reference: [diagnostic-decision-framework.md](https://github.com/lulufoo/lulu-workflow-framework/blob/main/dev/diagnostic/diagnostic-decision-framework.md)

Run a Diagnostic Decision Framework (DDF) session. **Mandatory before starting `/product-plan` or `/tech-plan`.**

---

<HARD-GATE>
Do NOT proceed until you have read `../SKILL.md` and loaded:

- `$SKILL_ROOT`, `$WORKFLOW_DIR`, `$PLATFORM`, `$CACHE_DIR` from `## Platform Context`
- Feature identification logic from `## Session Foundation`
</HARD-GATE>

`$SKILL_DIR` = `$SKILL_ROOT/diagnostic`

---

<HARD-GATE name="Domain Constraints">
Before executing any DDF gate, scan your current instruction context for a `## Domain Constraints`
section (injected by a domain holder such as `product-diagnostic` or `tech-diagnostic`).

**If a `## Domain Constraints` section is present:**
- Apply the X Gate constraints from that section (execute only the listed dimensions; skip the rest).
- Apply the Decision-Doc constraints from that section (omit the listed sections).
- Apply the After DC routing from that section.
- These holder constraints override all kernel defaults below.

**If no `## Domain Constraints` section is present** (direct `/diagnostic` invocation):
- Execute all five X Gate dimensions.
- Write all decision-doc sections.
- After DC: tell user they may proceed to `/product-plan` or `/tech-plan`.
</HARD-GATE>

---

<HARD-GATE>
Do NOT exit diagnostic or transition to the next stage until:
  
- All DDF gates (Q / E / D / X → R → [LoopB if uncertain: V / RR] → DC) have passed
- The decision-doc has been written to disk
- User has explicitly confirmed readiness to proceed

This applies to EVERY intent, regardless of perceived clarity.
"I already know what I want to build" is the most common reason to skip this —
and the most common source of wasted downstream work.
</HARD-GATE>

---

## Core Principles

1. **Expose over conclude** — the goal is to surface assumptions and risks. A conclusion is the output of verification, not the target.
2. **User prior over framework** — user's judgments, intuitions, and concerns shape the session; the framework captures and integrates them, does not override them.
3. **Log assumptions immediately** — any assumption surfaced at any gate goes into the Assumption Log right away; R organizes, does not collect.

---

## Re-open & Invalidation

Two global rules, applicable at any gate, any time:

**Trigger**: Any participant (AI or user) can re-open a prior gate the moment new information shows its pass criterion no longer holds — without waiting for V.

**Propagation**:
- When a gate is re-opened, all gates reachable from it along prerequisite dependency arrows are automatically invalidated and must be re-satisfied.
- Scope is determined by the DAG structure — no enumeration needed.
- When a reopen trigger fires, read and execute `$SKILL_DIR/gates/rs-reopen-state-handler.md`; RS handles state cleanup and re-entry routing.

---

## Parallel Registers

Two registers run throughout the entire session, not attached to any single gate:

**User Prior Log** — captures user's judgments, preferences, concerns, and excluded options. Reviewed before D; verified at R (R签字确认).

**Assumption Log** — captures unverified premises. Risk-graded at R; not collected from scratch there.

**3-state lifecycle:** `[待验证]` (default) → `[已验证]` (confirmed at R or after Risk Release) → `[失效]` (deleted via RS § Register Reopen Protocol)

**Reply Header** — output at the top of every reply once any entry exists:

```
─── DDF ───────────────────────────────────────
Gate: Q✅ E✅ D⬜ X⬜ R⬜ V⬜ RR⬜ DC⬜
Prior：
[P1✓ open] 排除方案B
[P2? Q] 偏好渐进实施
Assumption：
[A1? D H] API批量操作
[A2✓ X L] 管理员权限
───────────────────────────────────────────────
```

- `<state>`: `?` = 待验证 · `✓` = 已验证
- `<source>`: gate where first discovered — `open` / `Q` / `E` / `D` / `X` / `R` / `V` / `RR`
- `<risk>`: `H`/`M`/`L` — assigned by R gate; omitted until then
- Omit `Prior：` or `Assumption：` block if empty; omit entire Header if no entries exist; stop after DC Delivered

**On reopen:**
- Gate line: reopened gate G + all downstream → `⬜`
- Register entries are not auto-modified by DAG propagation — changes only occur when reopen is triggered.

---

## Start

**Step 1: Identify active cycle** — See `## Session Foundation` in `../SKILL.md`

> Ambiguity signals: no footer in conversation · user mentions a different feature · user says "switch" / "new" / "choose"

**Step 2: Confirm output path**

Decision-doc will be written to:
```
$CACHE_DIR/<cycle_id>/{cache_subdir}/decision-doc.md
```

Where `{cache_subdir}` is determined by the `--stage` argument:
- `--stage product-diagnostic` → `product/diagnostic`
- `--stage tech-diagnostic` → `tech/diagnostic`
- `--stage diagnostic` (default) → `diagnostic`

**Step 3: Run start.py**

```bash
python3 "$SKILL_DIR/scripts/start.py" \
  --project-root "$(pwd)" \
  --cycle-id "<cycle_id>" \
  --stage "<stage_name>"
```

Where `<stage_name>` is `product-diagnostic`, `tech-diagnostic`, or `diagnostic` (from the holder or the routing context).

Creates `session-state.md` with `current_state: InProgress`.

**Do not** run start again after Delivery (`Delivered`) on the same feature — use a new feature for a new diagnostic.

---

## Execution Rules

### Global Rules

**G0. User prior capture (throughout)** — at any gate: if user states a judgment, preference, concern, or historically excluded option, capture it in the User Prior Log immediately, confirm briefly, then continue the current gate without interruption. User Prior Log is reviewed twice: before D (direction alignment) and at R (R签字确认 — see User Prior Log).

**G1.** One question at a time — never stack multiple questions in a single message.

**G2.** Multiple choice preferred; open-ended is fine when options are not enumerable.

**G3.** Each gate has a pass criterion. Do not advance until the criterion is met.

**G4. Gate status tracking** — Gate status is always visible in the Reply Header (see `## Parallel Registers`). No separate gate status report is needed.

**G5.** Upstream input error — if the intent input itself has a fundamental error, exit the loop; tell the user to fix the input and restart.

**G6. Override Guard (reactive)** — when override signal detected ("skip" / "just implement it" / etc.):
1. Stop immediately — do not execute
2. State which gates are not yet closed
3. Ask: "Continue diagnostic or exit intentionally?"

If user confirms exit → exit gracefully; mark as incomplete.

**G7. Collect-or-Ask** (applies to all information-gathering):
1. Check: is this information already explicitly stated by user?
2. Yes → quote original + restate + confirm ("Is this correct?")
3. No → ask normally

**Prohibited:** re-asking information already stated.

**G8. Gate confirmation (all gates)** — AI cannot unilaterally declare a gate as passed. Each gate requires an explicit user confirmation step before it closes. Silence does not constitute confirmation.

**G9. Reopen check at gate close** — before closing any gate, check: does the evidence gathered in this gate invalidate any prior gate's pass criterion? If yes, do not close current gate; trigger Reopen State Handler (RS) instead.

---

### Gate Rules

**Phase grouping (for re-open scope identification):**
- [LoopA] Q → E → D → X  (decision construction loop)
- [LoopB] V → RR  (verification release loop)
- [RS]  Reopen State Handler (standalone subroutine, not in any loop)
- [DC]  Delivery Confirmation (terminal gate)

#### Open channel (before Q)

Before entering Q, invite the user to dump existing knowledge:

> "Before we begin — share what you'd like me to know: direction preferences, concerns, or options you've already ruled out. It doesn't need to be complete; you can add more at any point."

Capture input in User Prior Log. This step is not part of Q and does not count toward Q's question quota.

---

### Gate Routing

<HARD-GATE>
Before executing any gate, Read the corresponding gate file first.
Do NOT rely on memory or prior context for gate execution steps.
</HARD-GATE>

| Gate | File | Load condition |
|------|------|----------------|
| Q | `$SKILL_DIR/gates/q-problem-clarification.md` | Entering Q |
| E | `$SKILL_DIR/gates/e-direction-exploration.md` | Q closed |
| D | `$SKILL_DIR/gates/d-decision-scope.md` | E closed |
| X | `$SKILL_DIR/gates/x-full-diagnosis.md` | D closed |
| R | `$SKILL_DIR/gates/r-expose-bets.md` | X closed |
| V | `$SKILL_DIR/gates/v-verification.md` | R → uncertain assumptions |
| RR | `$SKILL_DIR/gates/rr-risk-release.md` | V → high-risk items |
| DC | `$SKILL_DIR/gates/dc-delivery-confirmation.md` | Verification complete |
| RS | `$SKILL_DIR/gates/rs-reopen-state-handler.md` | Reopen triggered |
| Human Decision | `$SKILL_DIR/gates/hd-human-decision.md` | RR → ❌ Failed |
