# Init display_layer golden fixtures (K3 semi-real e2e)

Committed revision trees that pass `init_compose_validation validate` with
`--project-root` = repo root and the live profile registries.

| Profile | Doc | Source |
|---------|-----|--------|
| lulu-plan | `tech-doc.md` | Init sim (`.cache/plan-init-sim-builders-entry`) |
| lulu-arch | `arch-doc.md` | Init sim (`.cache/arch-init-sim-plan-task`) |
| lulu-design | `design-doc.md` | Minimal generated (validate-green) |
| lulu-spec | `product-doc.md` | Minimal generated |
| lulu-blueprint | `blueprint-doc.md` | Minimal generated |

See `test_init_display_golden_e2e.py` and `MANIFEST.json`.
