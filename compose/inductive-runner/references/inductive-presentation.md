> Part of inductive-runner · presentation reference · indexed from `../SKILL.md`

# Inductive Presentation

Session-wide contract for **user-facing wording** across the whole inductive run (Seed → Shape-confirm → refine → audit handoff). The capability reference says *what* a capability is; the flow layer says *when* it runs; this file says *how it sounds to the user*.

**Language:** the glosses below are plain-English illustrations — **speak them in the user's language** at runtime. Never surface internal tokens verbatim, in any language.

## Shield rule

Internal vocabulary never reaches the user: any `trigger` (`human`/`ai`/`seed`) or `means` token (`probe`/`direct`/`view`/`ai_scan`/`intent_baseline`/`scope`), `frontier_kw`, `add-open` / `settle-open` / `defer-open`, `open` / `decision` ids, `KW`, raw section keys as jargon, gate ids. The user hears **intent and conclusions**, not mechanism.

## Translation table

| Internal | Say (gloss) |
|----------|-------------|
| `ai_scan` | "I scanned the code" |
| `intent_baseline` | "I checked it against the requirements" |
| AI `probe` | "I stress-tested a few failure / edge spots" |
| detect batch | "I gathered a batch of points that may need deciding" |
| `open` | "an open point" |
| `settle-open` | "lock it in" |
| `defer-open` | "park it for now" |
| `decision` | "a settled point" |
| `View` | "the current picture" |

## Label rule

Follow the collision label contract in `g3-capabilities.md` (✅ Verified / ⚠️ Inferred / unknown) when presenting inference — never present inference as settled fact in wording.

## Output shape

Present **finding + one leaning**, not a verdict menu. Offer the processing choice plainly: "want me to lock it in / talk it through / skip it" (= auto / manual / ignore).

## Per-moment tone

- **Free-dialogue sensing:** discuss / look around plainly; no mechanism talk.
- **View:** present the current picture as a plain snapshot; still no mechanism talk.
- **Docking a user gap:** acknowledge simply — "I'll note that as an open point."
- **AI detect:** report findings, not a scan log.
- **Processing:** on settle, say what got decided and why in one line.
- **Convergence:** "this area looks settled — wrap it up?"

## Hard boundary

Shielding is presentation-only. Under the hood every open still carries its `trigger` × `means` stamp and any required ✅ / ⚠️ labels — they feed G5 provenance and I10 inheritance. **Never drop metadata to make the wording cleaner.**
