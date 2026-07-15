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

3. **New feature only — optional topic association** (skip for New topic):
   Run `$CYCLE_CONTROL topic-digest --stage $STAGE` (`$STAGE` = current sub-SKILL `name`).
   - **Case 1** — `applicable:false` or `topics` empty: skip association.
   - **Case 2** — one highly related topic in `topics[]` (user-named topic = strong signal):
     ask to confirm that **one** (yes/no); yes → set `$TOPIC_ID`; no → leave unset.
   - **Case 3** — none highly related: do not ask; leave `$TOPIC_ID` unset.
   **Forbidden:** set `$TOPIC_ID` without a user yes, or to an id not in `topics[]`.

4. If a new name is resolved (not an integer selection), run `$CYCLE_CONTROL start`:
   - topic: `--name "<name>" --type topic`
   - feature: `--name "<name>" --type feature` [`--topic-id "$TOPIC_ID"` when set]
   - stdout last line → `$CYCLE_ID`
   - append footer (`LULU-DEV-WORKFLOW: $CYCLE_ID`)

`$CYCLE_CONTROL` macro: parent `SKILL.md` § Script Macros; macro expansion: `../_runtime.md` § Script Macros → Macro expansion. `start` / `topic-digest` subcommands: `cycle_control.py` `--help`.

Done: `$CYCLE_ID` confirmed · Read workflow docs only from `$CACHE_DIR/$CYCLE_ID/`
