# lulu-blueprint templates — staging area

Compose and eval templates for `lulu-blueprint` — **topic-level product architecture shaping** for a
multi-feature topic, reviewable before opening a feature cycle. Not enterprise portfolio planning, not
feature PRD (`lulu-spec`), not technical architecture (`lulu-arch`).

Staged in this repo under `lulu-dev-workflow/lulu-blueprint/templates/` until synced to
`lulufoo/lulu-workflow-framework` at `lulu-dev-workflow/template/blueprint/` (same filenames;
framework may add numeric prefixes on sync).

Filenames omit numeric prefixes; assign numbering when syncing to the framework repo.
`skill-config/lulu-dev-workflow/stages/lulu-blueprint.json` references the target framework URLs.

| File | Compose scheme role |
|------|---------------------|
| `product-blueprint-topic-section-registry.json` | section-registry |
| `product-blueprint-topic-section-form-registry.json` | section-form-registry |
| `product-blueprint-topic-section-kw-criteria.md` | section-kw-criteria |
| `product-blueprint-topic-outline-registry.json` | outline-registry |
| `product-blueprint-topic-role-instance.json` | role-instance |
| `product-blueprint-topic-domain-instance.json` | domain-instance |
| `product-blueprint-topic-quality-framework.md` | eval SoT (`blueprint-quality`) |

`inductive-scan-criteria` is not used (`drafting.inductive: false`).
