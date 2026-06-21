> Part of diagnostic-workflow · Global gate (parallel) · loaded via Gate Routing in `$SKILL_DIR/SKILL.md`

#### G0 — Parallel Registers

**Global · parallel** — runs alongside any active spine gate (O → DC). Does not change `active_gate`. No `gate-close`.

**Prerequisites:** Session InProgress · identification hit this turn

**Logs:**

- **User Prior** (`prior`) — kinds: `judgment`, `preference`, `concern`, `excluded`
- **Assumption** (`assumptions`) — premises treated as true but not yet verified

**Identify:**

| Signal in dialogue | Log | Also log |
|--------------------|-----|----------|
| Judgment about the problem or solution | Prior · `judgment` | — |
| Preference between options or approaches | Prior · `preference` | — |
| Worry, risk, or blocker | Prior · `concern` | — |
| Ruled-out option | Prior · `excluded` | — |
| Explicit or implicit unverified premise | Assumption | — |
| Prior resting on an unverified premise | Prior (matching kind) | Assumption for the premise |

Do **not** defer assumption identification to R — recognize as soon as it surfaces.

**Execute:**

1. Brief confirm with user
2. `$REGISTER_COMMIT` with one or more append/update operations (non-zero → stop, report error)
3. Pin `$CTX` from stdout

**Pass criterion:** `$REGISTER_COMMIT` succeeded · `$CTX` pinned · resume active spine gate dialogue

**Prohibited:** deferring capture because R is coming; hand-editing register state; reading or writing register data files directly; chaining `register-append` / `register-update` / `sync-registers-to-doc` / `resolve-context` separately

**Not in scope:** read or organize priors (D / R gates) · bulk assumption field updates (R / V / RR `gate-close` payload) · RS register batch (`$RS_COMMIT`)
