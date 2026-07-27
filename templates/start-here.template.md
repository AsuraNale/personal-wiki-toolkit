<!--
START-HERE template (NEW-6). Instantiate as START-HERE.md in the library root at
handover. This is the owner's front door: the file they open when they've
forgotten how any of this works.

Rules for filling it in:
- Fill EVERY {placeholder}. An unfilled one is worse than a missing section.
- Write in the owner's language.
- Keep it to one screen. The care guide (CARE.md) holds the routine; this holds
  the map and the first move.
- The "what to ask" lines must be REAL questions this library can answer today —
  test each one before writing it down. A suggested question that returns nothing
  teaches the owner the library is useless.
- Regenerate the counts and the most-linked list whenever the library changes
  shape. Stale numbers here are worse than none.
-->

# {library name}

{One sentence: what this library is for, in the owner's words from Intake.}

**Ask me anything about it** — open this folder with your AI assistant and just
talk. You don't need commands for questions.

---

## Start with one of these

{3–5 questions this library can genuinely answer TODAY. Test each one first.}

- "{a question about the most recent material}"
- "{a question that spans several notes}"
- "{a 'what changed lately' question}"
- "{a question about the busiest topic below}"

## What's in here

| | |
|---|---|
| **Topics tracked** | {topic list} |
| **Notes** | {N} in `notes/` |
| **Briefs** | {N} in `briefs/`, latest {date} |
| **Awaiting your verdict** | {N} in `_pipeline/silver/` |
| **Sources** | {N} configured — see `config.json` |

## Most connected notes

{The 3–5 notes other notes link to most — this is the library's spine, and it is
usually not what the owner expects.}

1. `{path}` — {one line}
2. `{path}` — {one line}
3. `{path}` — {one line}

## The two things you actually do

1. **Skim the new brief** (2 minutes). Keep what deserves keeping, dismiss the
   rest **with a reason** — the reason is what stops it coming back.
2. **Ask it things.** What you ask but the library can't answer is tracked, and
   when a gap keeps recurring it will *propose* a new topic. You approve it; it
   never grows on its own.

Full routine: `CARE.md` · Who tends this library: `{keeper.md or "no keeper"}`

## When something looks wrong

- **A brief looks empty** → check the source-health line at its top. "Nothing new"
  and "the fetch failed" are different, and the brief says which.
- **A number looks off** → every note carries its source and date. Follow the link
  before trusting the note.
- **It feels stale** → ask "what's stale, and what has been waiting for my verdict
  longest?"
