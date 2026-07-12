# lulu-arch local framework templates (K0b)

Local SSOT for fact-first display-layer grayscale (deductive + Pd).
`skill-config/.../lulu-arch.json` points here for **section-registry** and
**outline-registry** (path form `lulu-dev-workflow/lulu-arch/framework/...`).

- `tech-arch-topic-section-registry.json` — remote copy + explicit `presence`
  (`OQ=optional`, others `required`) + local remap
  `FD.relations.SH: attach_to → operationalize` (remote `attach_to` is not in
  `_RELATION_TYPES`). `KD←SH instantiate` retained for Pd.
- `tech-arch-topic-outline-registry.json` — **candidates** shape (1:1 from
  legacy SI/BD/SH/FD/KD/OQ blocks), not `outline_order`/`blocks`.

Other arch templates (form / kw / role / domain / eval) still fetch from
`lulu-workflow-framework` via GitHub URLs.

Pushing these two files upstream is deferred. Until upstream fixes `attach_to`,
do **not** flip the section-registry URL back to remote.
