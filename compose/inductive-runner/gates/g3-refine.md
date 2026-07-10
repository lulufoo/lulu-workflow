> Part of inductive-runner · gate execution entry · loaded from `../SKILL.md`

# Gate 3 — Refine (user-driven capabilities)

**Prerequisites:** `$INDUCTIVE_GATE_CTL resolve-context` reports `active_gate` is `G3` (G2 closed).

**Goal:** refine section SoT via the **capability surface** (design §7). **Do not** auto-sweep after Shape-confirm — wait for the user.

**Setup:** breadth = `SCAN_CRITERIA.expose_axis.coverage_sections`; depth = per-section `frontier_kw`. Discovery sources (trigger × means): human `probe|direct|view`; ai `ai_scan|intent_baseline|probe`. KW is the ruler. Mutations via `$INDUCTIVE_G3_SECTION_CTL` only.

**Norm precondition:** if `$NORM_CONSTRAINT_REFS` non-empty, hold as generation boundary (not a gate). Empty → inert.

## Capabilities (user-triggered)

### ① View (anytime)
`$INDUCTIVE_G3_SECTION_CTL view --synthesis on|off --scope <all|ST,IF> [--granularity <hint>]`  
Fidelity only when presenting as View (V2). Compose init uses `synthesis off`.

### ② 碰撞 / human probe
User questions → answer from SoT + grounding with ✅/⚠️ → gaps →  
`add-open --trigger human --means probe …` → capability ④.

### ③ Detect (passive — only when asked)
For unsettled sections at `frontier_kw`:
- **ai_scan** — run applicable `SCAN_CRITERIA` methods over code; qualify with KW.
- **intent_baseline** — `intent_coverage` vs demand manifest when present.
- **ai/probe** — black-box 4 lenses (failure / boundary / assumption / seam); silence ∧ KW-false → gap; no correctness judging (that is G4).

Each hit → `add-open --trigger ai --means <ai_scan|intent_baseline|probe> …` (dedup by section, KW, topic — attach provenance when colliding). Present a **batch** (problem + leaning) for user selection.

### ④ Process batch
User picks auto / manual / ignore after seeing problem+leaning:
- ground → `attach-code-refs`
- settle → `settle-open --text …` (inherits trigger/means/intent_ref)
- or `defer-open --note …`
Then user may ①/② to confirm; request next ③ batch.

### ⑤ User-proposed open
`add-open --trigger human --means direct …` → immediately ④ (no view required).

## Maturity & clear
- After settles: AI re-judges KW → `set-frontier`
- `clear-section` when frontier ≥ target and no blocking open (reads section JSON)

## Close G3
When Exit predicate holds (`check-coverage` ok): `$INDUCTIVE_GATE_CTL gate-close --gate G3`.  
Do **not** enter G4 until the user asks for delivery audit.

## Optional shallow/deep grounding subagents
Still available for code facts during detect/expand; they must **not** register opens — parent calls `add-open`. Prefer `attach-code-refs` on the open/decision being processed.
