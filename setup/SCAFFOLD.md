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
│   ├── answers/         answers given from OUTSIDE the library, pending verification
│   └── logs/            fetch/run logs
├── kb.db                index: notes, tags, links, coverage   (SQLite)
├── intel.db             ledger: seen, silver, fetch_log, demand (SQLite)
├── scripts/             instantiated from toolkit templates (see step 4)
└── keeper.md            librarian instructions (if keeper enabled)
```

### Adjust the tree to the library's shape

The layout above is **Shape A** (adjudication: intel / import). Check
`config.type` and `references/medallion.md` before generating:

**Shape A · intel** — organize `notes/` by topic count:
- **≤2 topics** → keep `notes/` flat. Sub-directories for two topics are pure
  overhead, and a nearly-empty folder reads as "nothing here".
- **≥3 topics** → one directory per topic, named from the topic's `key`
  (`notes/agent-tooling/`). Agree the directory name **while drafting the topics
  table** — retro-filing is how notes end up in two places at once.

**Shape A · import** — `notes/` is replaced by the approved category tree
(index-in-place mode leaves user files where they are; the tree then only holds
NEW notes).

**Shape B · data/ETL** — a different tree, because the pipeline is yours to write:
```
├── <domain>.db          the facts + a fetch_log (you design the schema)
├── fetch_<domain>.py    your domain fetcher — the toolkit has no scaffold for it
├── tables/              DERIVED: recomputable rollups. Never hand-edited
├── notes/              CONCLUSIONS = Gold: human-written analysis
├── briefs/              periodic drafts for the human to react to (the cadence)
└── _pipeline/logs/
```
⚠️ **Do not create `_pipeline/silver/` or the `seen`/`silver` tables for Shape B.**
There is no per-row adjudication queue here; facts land final on write. A recall
library built with the Shape A scaffold left its Silver at 21 rows, 0 promoted /
0 dismissed, while the real data accumulated in a table beside it.

⚠️ **Keep Derived out of `notes/`.** `tables/` and generated `briefs/` are
recomputable; `notes/` is what a human decided. Mixing them makes the library's
health unreadable in both directions — see `medallion.md` Shape B rule 3.

**Level-0 mode** (either shape): `index.md` + `_pipeline/seen.md` replace the
two .db files.

### Naming: the user doesn't have to choose between readable and robust

This used to be posed as a trade-off — readable names in the user's language, or
ASCII names that survive every shell and sync tool. **It isn't one.** The two names
live at different layers:

| Layer | Name | Rule |
|---|---|---|
| **On disk** (paths, directories, filenames) | **ASCII**, lowercase, hyphenated | never negotiable — non-ASCII paths break on some shells, sync tools, and CI, and the breakage is intermittent, which is worse |
| **On screen** (what the user reads) | **the user's own language** | always — in the note's frontmatter `title`, in `START-HERE.md`, in the index tables |

So a topic the user calls 「加拿大房产」 becomes `notes/canada-property/`, and every
note in it carries `title: 加拿大房产 — …`. The user reads their language everywhere
it is displayed; the filesystem only ever sees ASCII.

Why this is the right split: the index resolves a display name from
`frontmatter title -> first H1 -> filename stem` (`references/storage.md`), so a
title in the user's language is picked up automatically — the ASCII filename is
only ever the last-resort fallback. **Give every note a real `title` and the
question disappears.**

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
selftest`**; on macOS/Linux use `python3`. A single failed `python` call is NOT
proof of no runtime — bare `python` may be a Microsoft Store alias, and in a
sandbox even `py` can be alias-blocked while a real `python.exe` runs. Before
declaring Level-0, run the **full detection sequence in SKILL.md § Level-0**
(`py`/`python3` → `where`/`which` → the full `python.exe` path). Only if Python genuinely can't run or is too
old (needs 3.9+), switch the plan to **Level-0 mode** (SKILL.md) and say so
plainly — do not scaffold broken automation, and do not false-negative into
Level-0 when a runtime is right there.

### Scripts you write yourself

You may add scripts of your own — a fetcher for a source the toolkit doesn't
cover, a one-off importer, an export helper. Two rules, and they exist because
two real builds went to opposite extremes and the spec said nothing either time:

1. **Leave them in the library.** One build wrote its collection scripts, used
   them, and deleted them; the run could not be reproduced afterwards and the
   scores it produced could not be explained. A script that ran is part of how
   the library got its contents. Deleting it discards the provenance of every
   row it wrote.
2. **Mark them as not shipped with the toolkit** — one comment line at the top
   (`# not part of personal-wiki-toolkit — written for this library`). Without
   it, the next person cannot tell which files a toolkit update will overwrite
   and which are theirs.

Do not modify the four toolkit scripts to add your behaviour; put it in a new
file. `pipeline.py stats` reports staleness by comparing version strings, and a
locally edited copy will silently claim to be current.

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

1. **Leave the name for handover.** The keeper introduces itself and asks the owner
   to name it at handover (`setup/INTERVIEW.md` Phase 4) — a name the owner chose is
   theirs; a name you chose and they approved is still yours. Use a placeholder here
   and fill it in then. (A *named* role gets treated as staff; an unnamed one gets
   ignored — which is why the naming happens, just not by you.)
2. **Pick the duty preset.** `INTEL` (for `config.type` intel) / `DATA` (for
   `config.type` data) — plus `FULL-RUN`, which is **not a type** but an autonomy
   level (end-to-end operation incl. proactive alerts) layered on either. This
   selects the duties + red-line flavor in the template. **No IMPORT preset exists
   yet** — for an import-type library, start from INTEL and cut the collection
   duties. (Library shapes themselves: `references/medallion.md`.)
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
- [ ] `START-HERE.md` written from `templates/start-here.template.md`, and every
      suggested question in it was **actually tried** against this library
- [ ] the library's own memory file tells a future session **how** to use
      `_pipeline/answers/` — an empty directory nobody is instructed to use is the
      same defect in another shape (see `references/keeper.md` § *Answering from
      outside the library*)
- [ ] **Handover states the library's real state**, with an `evidence` block pasted
      (`python scripts/pipeline.py evidence`) — how many items await a verdict, and
      that leaving them costs nothing but keeps them out of sight. **Numbers must be
      pasted, not retyped**: a real QC report got three of them wrong by hand.
      ⚠️ This proves the counts are genuine; it does **not** prove the owner read or
      understood them. Don't record it as if it did.
- [ ] **Intake recorded**: `config.json` carries `$intake`, and nothing in it is
      `agent-inferred` (see `setup/INTERVIEW.md` § Intake)
- [ ] **Shape B only — the human loop is actually wired**, both halves:
      - [ ] ① a draft is produced on a stated cadence (EOD / weekly), not "when
            someone remembers" — without something to react to, nobody starts
      - [ ] ② a verdict, once made, **lands back in the library** as a file citing
            what it came from (`> **Promoted from**: <item/URL>`). Four highly
            active libraries with no ① produced zero human Gold; one with ① but
            no ② also shows zero, because its verdicts were only ever made
            outside the library
- [ ] → return to your setup flow; the first-run phase (INTERVIEW Phase 3)
      is NOT optional
