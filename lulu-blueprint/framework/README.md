# lulu-blueprint local framework templates (K0b)

Local SSOT for fact-first display-layer grayscale (deductive + Pd).
`skill-config/.../lulu-blueprint.json` points here for **section-registry** and
**outline-registry** (path form `lulu-dev-workflow/lulu-blueprint/framework/...`).

- `product-blueprint-topic-section-registry.json` — remote copy + explicit
  `presence` (`OQ=optional`, others `required`). `PR←PS instantiate` retained
  for Pd.
- `product-blueprint-topic-outline-registry.json` — **candidates** shape (1:1
  from legacy SI/BD/PS/PR/OQ blocks), not `outline_order`/`blocks`.

Other blueprint templates (form / kw / role / domain / eval) still fetch from
`lulu-workflow-framework` via GitHub URLs.

Pushing these two files upstream to `lulu-workflow-framework` is deferred
(GitHub submit later). Until then, do not flip remote URLs back for these two.
