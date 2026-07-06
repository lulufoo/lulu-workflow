# lulu-arch templates — staging area

Compose and eval templates for `lulu-arch` — **topic-level technical architecture shaping** for a
multi-feature topic, reviewable before opening a feature cycle. Not enterprise architecture, not
feature solution design (`lulu-design`), not execution specs (`lulu-plan`).

Staged in this repo under `lulu-dev-workflow/lulu-arch/templates/` until synced to
`lulufoo/lulu-workflow-framework` at `lulu-dev-workflow/template/arch/` (same filenames;
framework may add numeric prefixes on sync).

Filenames omit numeric prefixes; assign numbering when syncing to the framework repo.
`skill-config/lulu-dev-workflow/stages/lulu-arch.json` references the target framework URLs.

| File | Compose scheme role |
|------|---------------------|
| `tech-arch-topic-section-registry.json` | section-registry |
| `tech-arch-topic-section-form-registry.json` | section-form-registry |
| `tech-arch-topic-section-kw-criteria.md` | section-kw-criteria |
| `tech-arch-topic-outline-registry.json` | outline-registry |
| `tech-arch-topic-role-instance.json` | role-instance |
| `tech-arch-topic-domain-instance.json` | domain-instance |
| `tech-arch-topic-quality-framework.md` | eval SoT (`arch-quality`) |

`inductive-scan-criteria` is not used (`drafting.inductive: false`).
