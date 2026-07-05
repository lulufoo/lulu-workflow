> Part of inductive-runner · gate execution entry · loaded from `../SKILL.md`

# Gate 2 — Grounding (background)

**Prerequisites:** `$INDUCTIVE_GATE_CTL resolve-context` reports `active_gate` is `G2` (G1 closed).

**Goal:** a fast, autonomous sanity-check that the confirmed shape's spine/topology is not fundamentally wrong. **Not** a user-facing audit; **not** an exhaustive line-level grounding (that happens lazily per section in Gate 3).

**Read discipline (context guard):** confirm existence and topology only — main blocks exist / can exist, key relations are plausible. **Do not** read whole files; **do not** drop to line-level or signature-level detail in persisted facts. Gate 2 source reads run in `g2-grounding-runner` subagent only — **do not** inline-read project source during G2.

1. **Topology ground (subagent):** dispatch `g2-grounding-runner` via `$SUBAGENT_TOOL` with `$SUBAGENT_AWAIT_SYNC`:

```text
Load {actual $SKILL_ROOT}/compose/inductive-runner/g2-grounding-runner/SKILL.md and follow its instructions.

## Input
INDUCTIVE_OUT_DIR: {actual $INDUCTIVE_OUT_DIR}
COMPOSE_PROFILE: {actual $COMPOSE_PROFILE}
CYCLE_ID: {actual $CYCLE_ID}
PROJECT_ROOT: $(pwd)
```

Do **not** paste `architecture_view` in the Task prompt — the subagent reads `$INDUCTIVE_DQI` from disk.

Then run `$INDUCTIVE_GATE_CTL g2-check-report` **once** — immediately after the subagent returns. **`g2-check-report` exit 1 on `shape_breaking` is an expected branch — still run `$INDUCTIVE_GATE_CTL g2-list-report` next.** **Ignore** the Task return beyond confirming completion — decide next step only via `$INDUCTIVE_GATE_CTL g2-list-report`.

2. **If `verdict=ok`:** stay silent (no user checkpoint). Call `$INDUCTIVE_GATE_CTL gate-close --gate G2` (no payload) to advance to Gate 3.
3. **If `verdict=shape_breaking`:** present `divergences[]` from `$INDUCTIVE_GATE_CTL g2-list-report` stdout only; call `$INDUCTIVE_GATE_CTL gate-reopen --gate G1` and correct the shape with the user (reload `gates/g1-shape.md`).

**Breaking SSOT:** only a **direct contradiction** with G1 `architecture_view` / `shape_constraints` is shape-breaking. **To-Be gaps (not yet implemented) are not breaking** — route those to Gate 3.

**Close criterion (automatic when ok):** `g2-topology-report.json` exists with `verdict=ok`. Mechanical gate-close rejects missing report or `shape_breaking`. No user checkpoint on success.
