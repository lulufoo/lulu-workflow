# Feature Resolution — Slow Path

1. Run `$CYCLE_CONTROL list`; use stdout for the numbered list. If user message has a description, derive `<name>`.

   ```
   Cycles:
   [topic]   1. <name> [guided]
   [feature] 2. <name> [autonomous]
   …
   N. New topic — type a description to create
   M. New feature — type a description to create
   ```

   Ask both in one message:
   > `Cycle: enter number to select, or type a description to create [default: "<name>" — only when derived]`
   > `Execution mode: (1) guided [default]  (2) autonomous`

2. Parse (one reply covers both; unanswered → default):
   - **Feature:** integer → `cycle_id ← cycles.json[n]`; Initial Mode Resolution → DONE; text → `name ← input`; no answer → use derived `<name>`
   - **Mode:** `2` → `autonomous`; else → `guided`

3. If a new name is resolved, run `$CYCLE_CONTROL start --name "<name>" --mode "<mode>"` (see parent `SKILL.md` → Script Macros).
   `$EXECUTION_MODE ← mode`

Done: `$CYCLE_ID` confirmed · Read workflow docs only from `$CACHE_DIR/$CYCLE_ID/`
