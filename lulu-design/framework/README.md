# lulu-design local framework templates (K0b)

Local SSOT for fact-first display-layer grayscale (inductive + K2 handshake).
`skill-config/.../lulu-design.json` points here for **section-registry** and
**outline-registry** (path form `lulu-dev-workflow/lulu-design/framework/...`).

- `42-tech-design-section-registry.json` — remote copy + explicit `presence`
  on every section (`required`). Derivation edges retained (`KD`/`IF`/`OD`
  `instantiate` ← `ST`/`KD`).
- `45-tech-design-feature-outline-registry.json` — **candidates** shape
  (mapped from legacy SI/BD/SH/RS/CT/RD), not `outline_order`/`blocks`.

Other design templates (form / kw / role / domain / inductive-scan / eval)
still fetch from `lulu-workflow-framework` via GitHub URLs.

Pushing these two files upstream to `lulu-workflow-framework` is deferred
(GitHub submit later). Until then, do not flip remote URLs back.
