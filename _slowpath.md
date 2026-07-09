# Feature Resolution — Slow Path

1. Run `$CYCLE_CONTROL list`; use stdout for the numbered list. If user message has a description, derive `<name>`.

   ```
   Cycles:
   [topic]   1. <name>
   [feature] 2. <name>
   …
   N. New topic — type a description to create
   M. New feature — type a description to create
   ```

   Ask:
   > `Cycle: enter number to select, or type a description to create [default: "<name>" — only when derived]`

2. Parse (unanswered → default when applicable):
   - **Integer:** → `cycle_id ← cycles.json[n]`; **DONE** (existing cycle)
   - **New topic** (description or N): `name ← input`; `$CYCLE_TYPE ← topic`
   - **New feature** (description or M): `name ← input`; `$CYCLE_TYPE ← feature`

3. If a new name is resolved (not an integer selection), run `$CYCLE_CONTROL start`:
   - topic: `--name "<name>" --type topic`
   - feature: `--name "<name>" --type feature` [`--topic-id <id>` when associating with an existing topic]
   - stdout last line → `$CYCLE_ID`
   - append footer (`LULU-DEV-WORKFLOW: $CYCLE_ID`)

`$CYCLE_CONTROL` macro: parent `SKILL.md` § Script Macros; macro expansion: `../_runtime.md` § Script Macros → Macro expansion. `start` subcommand: `cycle_control.py` `--help`.

Done: `$CYCLE_ID` confirmed · Read workflow docs only from `$CACHE_DIR/$CYCLE_ID/`
