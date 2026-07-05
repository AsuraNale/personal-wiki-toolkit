# Curation: judging, dedup, and echo-chamber defense

Read this before scoring `_pipeline/pending.json`, and whenever you design
or revise search keywords. This file is the distilled judging discipline
from two production judge systems that were both measured against human
verdicts — and both initially failed the same way.

## The judging task

For each pending item (you typically have only title/source/topic — no full
text), output a relevance score 0–1 for the library's angle, plus a one-line
summary that says WHAT THE THING IS and why it does or doesn't matter here.

Output format (`_pipeline/judgments.json`):

```json
[
  {"url": "...", "relevance": 0.85, "one_line": "…", "topic": "…"}
]
```

Items ≥ the config threshold (default 0.7) become Silver; the rest stay
Bronze with their score recorded. `pipeline.py apply` consumes this file —
you never write the database yourself.

## The four judging disciplines

1. **Judge substance, not keywords.** The single most common failure. Both
   production judges initially scored anything containing the magic words
   (a hot product name, "SQLite", "memory", "agent") at 0.8+. Measured
   against human judgment they agreed only ~69% of the time — the misses
   were almost all keyword-baited. Ask: *is this item actually ABOUT the
   library's angle, or does it merely mention its vocabulary?* A post titled
   "Our CRM now has AI memory" is not about agent-memory research.
2. **When unsure, score low (≤0.5).** Asymmetric costs: a false negative
   sits recoverable in Bronze; a false positive becomes a Silver draft the
   user must waste attention dismissing — and if they're not careful, it
   becomes fake knowledge. "Might be interesting" is a 0.4, not a 0.7.
3. **Off-domain is low no matter how hot.** Trending, well-written,
   important-for-someone-else → still ≤0.3 if it's not this library's angle.
   The library serves its owner's angle, not the zeitgeist.
4. **Titles lie; say what it IS.** The one_line must state the item's actual
   nature ("a CLI tool that…", "a paper proposing…", "a rant about…") —
   writing it forces you to notice when you're scoring a guess. If you
   genuinely cannot tell what something is from the metadata, that IS the
   uncertainty case: score ≤0.5.

Calibration exercise (recommended monthly, 10 minutes): user re-judges 10
random machine-judged items blind; agreement below ~80% means the criteria
or this file's application needs tightening. See `qc-rubric.md`.

## Three-layer dedup (each layer catches what the previous can't)

| Layer | Key | Catches |
|---|---|---|
| Bronze | exact URL (primary key) | the same link fetched twice |
| Silver | normalized-title key (lowercase, alphanumerics+CJK only, truncated) | the same event/story from multiple sources or reposts |
| Gold | note path | accidentally re-promoting into an existing note |

The scripts enforce layers 1 and 3 mechanically. Layer 2 produces
*candidate* duplicates — the verdict "same story or genuinely different
angle?" is yours. Two writeups of one announcement = duplicate (keep the
better); two analyses with different conclusions = both can live.

## Echo-chamber defense (for keyword evolution)

Libraries that tune their own search keywords drift toward what they
already contain. Two rules, both learned in production:

1. **Static anchors are the majority.** The user-approved keyword set from
   setup always keeps running, no matter what "smart" keywords get added.
   Adaptive keywords may only EXTEND coverage (≥50% of fetch volume stays
   anchored), never replace the anchors.
2. **New keywords pass human review before use.** When you propose new
   keywords from Gold-coverage analysis ("we keep only X, search more X"),
   write them as a plan for the user to approve — never silently change
   config.json. The plan states, per keyword: intent (fill gap / follow
   frontier / avoid saturation) and one line of why.

## Dismissals train the judge

When the user (or keeper) dismisses with a reason, that reason is signal.
Before each judging round, skim the last ~10 dismissal reasons in the ledger
(`pipeline.py stats` shows them): they are the owner's living definition of
"not relevant here", more current than any config file.
