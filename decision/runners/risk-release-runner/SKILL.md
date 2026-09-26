---
name: decision/risk-release-runner
description: Internal runner that releases one open RK# on check evidence.
meta-skill-version: 1.1.0
---

# risk-release-runner

The goal is one named `risk_state=open` `RK#` (or leftover Assumption risk
row) released on evidence — legal terms, a check result the AI and the user
both acknowledge, recorded `completed` — or left `open` pending evidence,
recorded `ignore`, or the user routed away.

## Prerequisites

Caller names the current `open` id. One call per that row.

## Must hold

| ID | Must hold |
|----|-----------|
| `G-terms-one` | Current row has legal `release_terms` (Method / Owner / Timing / Release condition; or literal `Accepted`, M/L only). |
| `G-evidence-one` | For terms rows: the Method has been carried out — by the AI in this session or by the user elsewhere — and its outcome compared against the Release condition. Drafted terms, an offered check, or a described procedure are not evidence. `Accepted` rows need no check. |
| `G-acknowledge-one` | AI states the outcome (pass / fail) and the evidence in one line; the user confirms. The `complete-assumption` call is that confirmation. |
| `G-complete-one` | Row recorded: `completed` via complete-assumption (with check fields), `ignore` via set-risk-state, left `open` with `RELEASE_PENDING`, or user routed out. |

## Act

1. Identify the current id, `risk_level`, `risk_class`, `risk_consequence`,
   `risk_state=open`.
2. Draft terms: H (and decision-class M when verifying) use Method / Owner /
   Timing / Release condition; M/L may use `Accepted`. Forbidden: `Handoff:`
   prefix. Present terms as the check plan, not as the release.
3. Obtain evidence. Carry out the Method yourself when it is within reach
   (probe, read, run, inspect); otherwise ask the user to run it, or take the
   evidence the user brings from elsewhere. Evidence from either side counts
   equally.
4. Compare the outcome to the Release condition; state pass / fail plus the
   evidence in one line; confirm with the user (or confirm `Accepted`).
5. Persist.
   - pass: `$GATE_CONTROL complete-assumption --id <id> --release-terms
     '<terms>' --check-result pass --check-evidence '<what was checked and
     observed>'`.
   - `Accepted` (M/L): `$GATE_CONTROL complete-assumption --id <id>
     --release-terms 'Accepted'`.
   - fail: row stays `open`; revise terms and re-run, or route RS /
     human_decision.
   - no evidence yet: row stays `open`; return `RELEASE_PENDING`. Nothing is
     written.
   - ignore: `$GATE_CONTROL set-risk-state --id <id> --risk-state ignore`.
   `<id>` is `RK#`, or leftover `A#` if that row still holds risk fields.
6. Return. Caller owns the next step.

`completed` is written only by `complete-assumption`, never by `gate-close` or
`apply-r-assumptions`. The tool rejects terms rows without `--check-result
pass` and `--check-evidence`, and rejects `Accepted` on H.

## Exit

`RELEASE_COMPLETE` · `RELEASE_PENDING reason=...` · `RELEASE_FAILED reason=...`
