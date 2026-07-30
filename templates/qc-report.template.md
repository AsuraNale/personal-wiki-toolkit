<!--
QC report template. Use when running references/qc-rubric.md.
Save as _pipeline/logs/qc-<date>.md (or wherever the library keeps its logs).

The point of this file is that a QC round leaves EVIDENCE. "All good" with no
numbers attached did not happen — see qc-rubric.md § Reporting QC results.

Rules:
- Every row needs the actual number or the actual quote. Not "pass".
- A check you skipped is written down as skipped, with why. Silently dropping a
  row turns a partial audit into a clean bill of health.
- If a parameter changed during the round (threshold, keywords), it goes in the
  "What changed" section — never fold it silently into the score.
-->

# QC — {library name} — {date}

**Rubric:** {A (adjudication) | B (data)} · **Ran by:** {who} · **Scope:** {what period / how many items}

## Results

| # | Check | Evidence (the actual number / quote) | Verdict |
|---|---|---|---|
| {A1} | {name} | {e.g. "8/10 agreed; both misses were keyword-bait on 'agent'"} | pass / fail / skipped |
| | | | |

> Verdicts are `pass` / `fail` / **`skipped` (say why)**. Anything without evidence
> in the middle column counts as not run.

## Findings

{What the pattern is — not the individual misses. One bad judgment is noise; "every
miss came from one source" is a finding.}

## What changed as a result

{Concrete edits: keywords sharpened, curation.md re-read, keeper.md amended,
threshold moved (with the before/after and the reason). "Nothing" is a valid answer
if the round genuinely passed — say it explicitly.}

⚠️ If a threshold moved: the scores above were measured **before** the change. Never
re-run with a new parameter and present the second number as the first
(`qc-rubric.md` § Never tune the threshold to make a score go up).

## Still open

{Anything found but not fixed, so it isn't quietly forgotten.}
