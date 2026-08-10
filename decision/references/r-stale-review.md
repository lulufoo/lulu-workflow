# R stale review

Use only after R becomes `stale` following RS recovery, including when a Batch
leaves R stale. Confirm the complete risk pack's impact and dispositions once;
the R runner owns persistence, close, and handoff.

## Review

1. Compare the stale payload returned by `$GET_PAYLOAD --stale-only` with the
   complete risk pack in `$CTX.registers`.
2. For any classification change, load `r-risk-classification.md`.
3. Show affected rows, incremental differences, and proposed dispositions.
4. Obtain one explicit confirmation before any close.

## Reopen

If confirmed changes invalidate completed evidence, R reopens that row with
`set-risk-state --risk-state open`; the prior release terms are cleared. R then
handles each remaining open row before a `dc` exit.

## Confirmed outcome

| Outcome | R runner action |
|---------|-----------------|
| Upstream conclusion is wrong | Close with `exit=rs`. |
| User suspends | Close with `exit=human_decision`. |
| Decision remains deliverable | Close with `exit=dc`, `assumptions: []`, and the confirmed `stale_review` receipt. |
