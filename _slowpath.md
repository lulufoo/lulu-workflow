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
   - **Feature:** integer → `cycle_id ← cycles.json[n]`; `$EXECUTION_MODE ← mode from cycles.json`; **DONE**
   - **Mode:** `2` → `autonomous`; else → `guided`
   - **New topic** (description or N): `name ← input`; `$CYCLE_TYPE ← topic`
   - **New feature** (description or M): `name ← input`; `$CYCLE_TYPE ← feature`

3. If a new name is resolved (not an integer selection), run `$CYCLE_CONTROL start`:
   - topic: `--name "<name>" --type topic --mode "<mode>"`
   - feature: `--name "<name>" --type feature --mode "<mode>"` [`--topic-id <id>` when associating with an existing topic]
   - stdout last line → `$CYCLE_ID`; `$EXECUTION_MODE ← mode`
   - append footer (`LULU-DEV-WORKFLOW: $CYCLE_ID`)

`$CYCLE_CONTROL` macro: parent `SKILL.md` § Script Macros. `start` subcommand: `cycle_control.py` `--help`.

Done: `$CYCLE_ID` confirmed · Read workflow docs only from `$CACHE_DIR/$CYCLE_ID/`
