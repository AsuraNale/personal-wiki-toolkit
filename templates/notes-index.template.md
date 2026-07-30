<!--
Notes index template. Instantiate as notes/INDEX.md (or per-topic).
A browsable table of what the library holds — the thing kb.db knows but a human
can't read.

Rules:
- Regenerate rather than hand-maintain where possible: `index_db.py coverage` has
  the counts, and the note frontmatter has the rest.
- One row per note. If that becomes unreadable, the library needs topic
  directories (`setup/SCAFFOLD.md` § *Adjust the tree to the library's shape*), not a shorter index.
- "Last touched" is what makes staleness visible. Keep it accurate or drop the
  column — a wrong date is worse than no date.
- This index is DERIVED: it is rebuildable from the notes. Never let it become
  the only place a fact lives (medallion.md, Shape B rule 2 — the same discipline
  applies here).
-->

# {library name} — notes index

{N} notes · updated {date} · rebuild with `python scripts/index_db.py build`

## {Topic}

| Note | What it says | Source date | Last touched |
|---|---|---|---|
| [{title}]({path}) | {one line — what it actually claims, not what it is "about"} | {date} | {date} |

## {Topic}

| Note | What it says | Source date | Last touched |
|---|---|---|---|
| | | | |

---

## Gaps

{Topics configured in `config.json` with no notes yet — an empty topic is a
coverage gap, not an absence of news. Check the fetch log before assuming there
was nothing to collect.}
