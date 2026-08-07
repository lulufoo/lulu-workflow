> Part of inductive-runner · gate execution entry · loaded from `../SKILL.md`

# Gate 2 — (retired folded grounding)

**Superseded by archive-9.0 Topic Loop.**

Load and follow **`g2-topic-loop.md`** instead.

Legacy topology report / auto-close-without-payload is **retired**. Closing G2 requires:

```bash
$INDUCTIVE_GATE_CTL gate-close --gate G2 --payload '{"topic_loop_done": true}'
```

with a valid `_narrative-arc.draft.json` present under `$INDUCTIVE_OUT_DIR`.
