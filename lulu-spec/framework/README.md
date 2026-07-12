# lulu-spec local framework templates (K0b)

Local SSOT for fact-first display-layer grayscale (inductive + K2 handshake).
`skill-config/.../lulu-spec.json` points here for **section-registry** and
**outline-registry** (path form `lulu-dev-workflow/lulu-spec/framework/...`).

- `20-product-spec-section-registry.json` — remote copy + explicit `presence`
  on every section (`required`). Derivation edges retained (`IO`/`AC`
  `instantiate`/`decompose`).
- `22-product-spec-feature-outline-registry.json` — **candidates** shape
  (mapped from legacy BG/US/SC/FL/NG/AC), not `outline_order`/`blocks`.

Other spec templates (form / kw / role / domain / inductive-scan / eval)
still fetch from `lulu-workflow-framework` via GitHub URLs.

Pushing these two files upstream to `lulu-workflow-framework` is deferred
(GitHub submit later). Until then, do not flip remote URLs back.
