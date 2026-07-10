> Part of inductive-runner · gate execution entry · loaded from `../SKILL.md`

# Gate 2 — Grounding (FOLDED)

**Status (section-SoT, design Turn 44):** Independent G2 is **folded** into capability **④**'s per-open `attach-code-refs` step. Early global topology check is covered by **Shape-confirm** + later **Audit (G4/G5)**.

**Prerequisites:** `$INDUCTIVE_GATE_CTL resolve-context` reports `active_gate` is `G2` (G1 closed).

**What to do:**

1. **Default (no topology report):** Call `$INDUCTIVE_GATE_CTL gate-close --gate G2` with **no payload**. Mechanical close **auto-passes** when `g2-topology-report.json` is absent.
2. **Optional legacy topology pass (deprecated):** Prefer **not** to dispatch `g2-grounding-runner`. If a report already exists, close still requires `verdict=ok`. New work should ground at expand time via `attach-code-refs` instead. The legacy runner, if used, must read shape claims from section JSON / checkpoint — not treat DQI `architecture_view` as SoT.

**Do not** treat G2 as a user-facing audit or exhaustive line-level grounding.

**Close criterion:** Gate advances to G3. Report optional; absent report = pass.
