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
├── intel.db             collection ledger: seen, silver, dismissed (SQLite)
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
`fetch_rss.py`, `index_db.py`. Do not modify them during scaffold; they are
config-driven. (Toolkit updates → user re-copies; scripts carry a version
string so `pipeline.py stats` can report staleness.)

Then verify the runtime: run `python scripts/pipeline.py selftest`. If
Python is missing or too old (needs 3.9+), switch the plan to **Level-0
mode** (SKILL.md) and say so plainly — do not scaffold broken automation.

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

## 7. Exit checklist

- [ ] tree exists, nothing user-owned was moved without a confirmed plan
- [ ] config.json valid (pipeline.py selftest validates it)
- [ ] CLAUDE.md/AGENTS.md written, in the user's language, red lines included
- [ ] selftest passed (or Level-0 declared)
- [ ] schedule registered by user, or manual mode acknowledged
- [ ] → return to your setup flow; the first-run phase (INTERVIEW Phase 3)
      is NOT optional
