# Feature Resolution — Slow Path

1. **Menu** — `$CYCLE_CONTROL menu`; present stdout verbatim. If the user message has a description, derive `<name>`.

   Ask:
   > `Cycle: enter T#/F# to select, or N/M to create [default name: "<name>" — only when derived]`

2. **Select existing** (`T#` / `F#`)
   - `$CYCLE_CONTROL resolve-token --token <input>` → stdout → `$CYCLE_ID`
   - `$CYCLE_TYPE ←` topic (T) | feature (F)
   - Own-line footer, no other text: `LULU-DEV-WORKFLOW: $CYCLE_ID`

3. **Create** (`N` / `M`) — `$CYCLE_TYPE ←` topic (N) | feature (M). `name ←` input, else derived default; if still empty → ask for name.

4. **Associate topic** (create feature only) — Ask once for optional topic (`T#` or topic `cycle_id`). `T#` → `$CYCLE_CONTROL resolve-token --token <T#>` → `$TOPIC_ID`; topic `cycle_id` → `$TOPIC_ID ←` that id; otherwise leave `$TOPIC_ID` unset.

5. **Start** — `$CYCLE_CONTROL start`:
   - topic: `--name "<name>" --type topic`
   - feature: `--name "<name>" --type feature` [`--topic-id "$TOPIC_ID"` when set]
   - stdout → `$CYCLE_ID`
   - Own-line footer, no other text: `LULU-DEV-WORKFLOW: $CYCLE_ID`

Done: `$CYCLE_ID` confirmed · Read workflow docs only from `$CACHE_DIR/$CYCLE_ID/`
