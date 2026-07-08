# Scaffold: generating the library

Input: a confirmed `config.json` (schema: `templates/config.example.json`).
Output: a self-describing library. Everything here is idempotent — running
scaffold again over an existing library must never destroy content (create
missing pieces, leave existing ones alone, and say what you skipped).

## 1. Directory tree

```
<library-root>/
├── CLAUDE.md            agent memory (see step 3) — duplicate as AGENTS.md
├── AGENTS.md            (same content; covers Codex-family agents)
├── config.json          the confirmed configuration
├── CARE.md              one-page care guide (written at handover)
├── inbox/               things the user drops in for the library to process
├── notes/               GOLD tier: curated, permanent, human-owned notes
├── briefs/              GOLD tier: finalized briefs
├── _pipeline/
│   ├── silver/          machine-drafted briefs awaiting curation (AUTO-*.md)
│   ├── pending.json     ← fetch output: items awaiting YOUR judgment
│   ├── judgments.json   → your scores; consumed by `pipeline.py apply`
│   └── logs/            fetch/run logs
├── kb.db                index: notes, tags, links, coverage   (SQLite)
├── intel.db             ledger: seen, silver, fetch_log, demand (SQLite)
├── scripts/             instantiated from toolkit templates (see step 4)
└── keeper.md            librarian instructions (if keeper enabled)
```

Import-type libraries: `notes/` is replaced by the approved category tree
(index-in-place mode leaves user files where they are; the tree then only
holds NEW notes). Level-0 mode: `index.md` + `_pipeline/seen.md` replace the
two .db files.

Naming: keep the user's language for directory display names ONLY if the
user asks; default to the ASCII names above (they survive every platform,
shell, and sync tool — a lesson paid for in encoding bugs).

## 2. config.json

Copy the confirmed draft. It is the single source of truth for topics,
sources, thresholds, cadence, and paths. Scripts read ONLY this file for
configuration — if a user wants to change a keyword later, they edit
config.json, never the scripts.

## 3. The library's own memory file (CLAUDE.md + AGENTS.md)

This is what makes the toolkit disposable. Instantiate
`templates/kb-agent-memory.template.md` with:

- library identity: name, domain, angle, owner, creation date;
- the tree map above with one-line explanations;
- the three curation verbs and when to use them
  (promote / dismiss <reason> / leave in silver);
- the red lines, copied verbatim from SKILL.md "Non-negotiable rules"
  (they must live IN the library — future sessions won't have the toolkit);
- command quick reference (fetch / apply / promote / dismiss / stats /
  index build);
- pointer to keeper.md if enabled.

Write it in the user's language. Both filenames get identical content.

## 4. Scripts

Copy from toolkit `scripts/` into library `scripts/`: `pipeline.py`,
`fetch_rss.py`, `index_db.py`, and (if demand-tracking is on) `demand.py`. Do not
modify them during scaffold; they are config-driven. (Toolkit updates → user re-copies; scripts carry a version
string so `pipeline.py stats` can report staleness.)

Then verify the runtime. **On Windows run `py -X utf8 scripts/pipeline.py
selftest`** — bare `python` is often a Microsoft Store alias that falsely reports
"not installed", so a `python` failure is NOT proof of no runtime; test `py`
first. On macOS/Linux use `python3`. Only if Python genuinely can't run or is too
old (needs 3.9+), switch the plan to **Level-0 mode** (SKILL.md) and say so
plainly — do not scaffold broken automation, and do not false-negative into
Level-0 when a runtime is right there.

## 5. Databases

Created by the scripts on first run — do NOT hand-craft SQLite files.
`pipeline.py selftest` initializes both DBs empty with the right schema.
(Schema documentation: `references/storage.md`.)

## 6. Schedule (optional; user-executed)

If cadence ≠ manual, generate the registration command for the user's OS and
**have the user run it** — task-scheduler registration is often blocked for
agents, and the user should know what runs on their machine:

- Windows: a `schtasks /create` one-liner (or Task Scheduler XML) invoking
  `python <library>\scripts\pipeline.py run` at the chosen time. Note for
  Chinese-locale systems: keep the command ASCII-only.
- macOS: a `launchd` plist dropped into `~/Library/LaunchAgents/` + `launchctl load`.
- Linux: a crontab line.

Always also mention the no-schedule option: "open your agent in the library
and say *run a collection round*" works forever, no registration needed.

Design rationale and failure discipline for anything scheduled:
`references/pipeline-discipline.md` (read before generating the commands).

## 7. The keeper (if `config.keeper.enabled`)

A keeper is a standing role definition (`keeper.md`) that any future agent session
in this library assumes — see `references/keeper.md` for the full role. Set it up:

1. **Name it.** Ask the owner to pick the keeper's name — a *named* role gets
   treated as staff; an unnamed one gets ignored.
2. **Pick the type preset:** intel (tracks a domain) / data (structured numbers) /
   full-run (operates the library end to end, incl. proactive alerts). This selects
   the duties + red-line flavor in the template.
3. **Ask the one question that writes the top red line:** *"What is the worst
   mistake this keeper could make?"* The answer becomes the ⛔ first red line — and
   capture it as *the actual phrasing to use*, not just a principle (principles get
   interpreted away; a script of what to say does not).
4. **Instantiate** `templates/keeper-instructions.template.md` → `keeper.md`: fill
   every {placeholder}, keep ONE type preset, write in the owner's language, keep it
   under ~2 pages. Point the library's CLAUDE.md/AGENTS.md at it.
5. **First-run rite — do it now, then it's done** (this is NOT a permanent section
   of keeper.md; it's a one-time hazing). On the keeper's first session, have it:
   - walk the actual library and report back what it understands the library to be;
   - **VERIFY section 3 (the library map) against the REAL library** — open the DBs
     / list the files, confirm table names, columns, row counts. This is where
     paper-vs-reality gaps surface (a real setup caught two: a column named other
     than assumed, and a status kept in note-text instead of a column). Fix the map
     to match reality;
   - run one real task end to end (a query, or a collection round) and confirm it works.
6. **Hand off.** Tell the owner how to activate the keeper (open a session in the
   library dir → it reads `keeper.md` and becomes the keeper) and the daily care habit.

If demand-tracking is on, the keeper logs out-of-library queries with
`demand.py log "<category>" "<question>"` and surfaces a demand board with
`demand.py board` (propose-not-auto; owner approves growth) — see `references/keeper.md`.

## 8. Exit checklist

- [ ] tree exists, nothing user-owned was moved without a confirmed plan
- [ ] config.json valid (pipeline.py selftest validates it)
- [ ] CLAUDE.md/AGENTS.md written, in the user's language, red lines included
- [ ] selftest passed (or Level-0 declared)
- [ ] schedule registered by user, or manual mode acknowledged
- [ ] if keeper enabled: `keeper.md` instantiated, type preset chosen, top red line
      captured as phrasing, first-run rite done (map verified against the real library)
- [ ] → return to your setup flow; the first-run phase (INTERVIEW Phase 3)
      is NOT optional
