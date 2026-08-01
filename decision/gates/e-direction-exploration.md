> Part of decision-workflow · gate contract · via `$SKILL_DIR/runners/e-direction-runner/SKILL.md`

#### E — Direction Exploration

**Prerequisites:** GL closed

**Before entering:**
1. Confirm `$CTX.gates.GL.status` is `closed` and `$CTX.gl` is present (from resolve-context).
2. Read `$CTX.gl.exchanges` in full; prioritize `impact_surface`, `external_dependencies`, and confirmation-related answers; surface conflicts with candidate directions before proposing options.
3. Do not start E dialogue until GL intents have been consulted.

**Execute:**
1. Propose exactly **2–3 directions** — no more, no fewer.
2. Lead with the recommended option and explain why.
3. For each direction: state core approach, pros, cons.
4. List already-excluded directions with reasons — this prevents re-litigating ruled-out paths later.
5. Ask user to choose or propose an alternative.

**Pass criterion:** ≥2 directions evaluated with explicit pros/cons; user has chosen or indicated preference.
