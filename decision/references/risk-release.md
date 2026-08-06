# Risk release (single open row)

Use when R is in **`handle`** mode and the current assumption has `risk_state=open`.  
One row per invocation; R runner picks order H → M → L.  
Not a spine gate — no `gate-close` here.

## Goals

| ID | Must be clear |
|----|----------------|
| `G-terms-one` | Current row has legal `release_terms` (full Method/Owner/Timing/Release condition string **or** literal `Accepted`). |
| `G-check-one` | User confirmed terms and check result against the Release condition (or accepted M/L as `Accepted`). |
| `G-complete-one` | Row disposition recorded: `completed` via complete subcommand, `ignore` via set-risk-state, or user routed to `present`/`revise` / `rs` / `human_decision`. |

## Steps

1. **Identify** — Current assumption id, `risk_level`, `risk_class`, `risk_consequence`, `risk_state=open`.
2. **Draft terms** — Propose `release_terms`: H (and decision-class M when verifying) use Method / Owner / Timing / Release condition; M/L may use `Accepted`. **Forbidden:** `Handoff:` prefix.
3. **Confirm** — User confirms terms and verification outcome (or accepts `Accepted`).
4. **Persist** — On complete path: `$GATE_CONTROL complete-assumption --id <id> --release-terms '<terms>'` (call = user confirmed). On ignore path: `$GATE_CONTROL set-risk-state --id <id> --risk-state ignore`.
5. **Return** — Next open row in `handle`; or dialogue back to R `present`/`revise`; or user chooses `rs` / `human_decision`.

## Rules

- Non-zero CLI → stop; row stays `open`.
- Do not write `completed` in R `gate-close` payload — only via `complete-assumption`.
- Upstream wrong during check → R `exit=rs`, not a separate gate.
- Cannot finish release → suggest R `human_decision` (HD runner).
