> Part of diagnostic-workflow · gate contract · via `$SKILL_DIR/runners/o-open-channel-runner/SKILL.md`

#### O — Open Channel

**Prerequisites:** `$DX_START` complete · `active_gate` is `O`

**Execute:**
1. If `$CTX.context_loading.status` is `loaded`: load `$CTX.context_loading.resolved_doc_path` read-only; tell the user `$CTX.context_loading.loaded_message`. If `not_found` and not optional, proceed without upstream doc.
2. Invite the user to share existing knowledge:

   > "Before we begin — share what you'd like me to know: direction preferences, concerns, or options you've already ruled out. It doesn't need to be complete; you can add more at any point."

3. During dialogue: on identification hit → G0 runner → `G0_COMPLETE` → continue

**Pass criterion:** User confirms they are ready to proceed to Q (G8). Prior dump is optional — empty registers are allowed.

**Does not count toward Q's question quota.**
