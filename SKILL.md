---
name: personal-wiki-toolkit
description: >-
  Interviews the user (or ingests their existing folders) to build a personal
  knowledge base from scratch — Markdown + SQLite dual-layer storage, automated
  intelligence-collection pipeline, Medallion-tier curation, a librarian agent
  role, and QC rubrics. Use when the user wants to set up, organize, or grow a
  personal wiki / knowledge base / second brain / note system, or says things
  like "帮我建资料库 / 整理这些文件 / 搭个知识库 / organize my notes /
  build me a knowledge base", even without naming this skill.
license: MIT
metadata:
  author: personal-wiki-toolkit
  version: "0.1.0"
---

# Personal Wiki Toolkit

You are about to help the user build a **living personal knowledge base**: one
that is structured, indexed, honestly curated, and — if they want — feeds
itself with fresh intelligence on a schedule. This toolkit distills the
methodology from three real production libraries (an AI-industry intel base, a
game-data warehouse, and a stock research library) that ran for months with
daily automation and independent quality control.

**Speak the user's language.** All conversation, generated notes, briefs, and
library documentation should be in whatever language the user talks to you in.
These instruction files are in English; that is irrelevant to the user.

## What you will produce

A library directory owned by the user, containing:
- human-readable **Markdown** notes/briefs (the knowledge itself),
- a **SQLite index** (or a Markdown index table in Level-0 mode — see below),
- optionally a **collection pipeline** (scripts + schedule) that pulls new
  material from free public sources,
- a **curation workflow** (Bronze → Silver → Gold) so noise never becomes
  "knowledge",
- optionally a **librarian agent role** ("keeper") with written duties and
  red lines, so any future agent session knows how to tend this library,
- the library's own agent-memory file (`CLAUDE.md` / `AGENTS.md`), so the
  toolkit is disposable after setup — the library explains itself.

## Start here: route the request

Ask at most THREE questions to classify the job, then follow exactly one path:

1. **"I want to track/follow a topic over time"** (news, papers, an industry,
   a hobby scene) → **intel-type library**. Read `setup/INTERVIEW.md` and run
   the interview.
2. **"I have a pile of existing files/notes to organize"** → **import-type**.
   Read `setup/IMPORT.md`. (You can bolt a collection pipeline on afterwards —
   the import flow tells you when to offer that.)
3. **"I want a database of structured facts/numbers"** (prices, stats, game
   data) → **data/ETL-type**. Read `references/etl-guide.md` and be honest with
   the user up front: for this type the toolkit provides methodology, worked
   examples, and discipline checklists — you will design the schema and
   fetchers together with the user; there is no one-click scaffold.
4. Mixed? Import first, then add collection (path 2 → path 1's source steps).

## File map (read on demand — conditions matter)

| File | Read it when |
|---|---|
| `setup/INTERVIEW.md` | Building an intel-type library from scratch (path 1) |
| `setup/IMPORT.md` | Organizing existing files (path 2) |
| `setup/SCAFFOLD.md` | Any path, when you are ready to generate the library (both setup flows send you here) |
| `references/medallion.md` | Before you first write anything into a library: the Bronze/Silver/Gold tiers and promotion rules |
| `references/curation.md` | Before you judge/filter collected items, and whenever you design search keywords or dedup |
| `references/keeper.md` | When the user wants a librarian role, and at handoff time |
| `references/qc-rubric.md` | When you or the user wants to verify library quality; also read before claiming any setup step "done" |
| `references/pipeline-discipline.md` | Before you write or schedule any fetch automation |
| `references/storage.md` | When designing the SQLite schema or deciding what goes in Markdown vs the index |
| `references/etl-guide.md` | Data/ETL-type libraries (path 3) |
| `templates/config.example.json` | When generating the library's `config.json` (schema reference) |
| `scripts/` | Deterministic operations — fetching, dedup, indexing. See "Division of labor" below |
| `docs/compatibility.md` | Only if the user asks about installing this skill on a specific agent platform |

Do not read files speculatively; each row above states its trigger.

## Non-negotiable rules

These apply to every path and are the soul of this toolkit. They stay here in
SKILL.md because they must never be skipped:

1. **You judge; scripts write.** Relevance scoring, classification, naming,
   and dedup verdicts are YOUR job (you are the judge — no external API
   needed). Database writes, fetching, and indexing are the scripts' job. You
   exchange data via JSON files (`_pipeline/pending.json` in,
   `_pipeline/judgments.json` out). **Never write to the SQLite files
   directly** — always go through `scripts/pipeline.py apply` or
   `scripts/index_db.py`. This keeps the schema safe on every platform.
2. **Never fabricate.** Every note and brief entry carries its source (URL or
   file path) and date. If the library doesn't contain something, say "the
   library doesn't have this" — never improvise an answer and present it as
   library content.
3. **Judge substance, not keywords.** An item mentioning the user's keywords
   is not therefore relevant. Score what the item actually IS. When unsure,
   score LOW (the user can always rescue a false negative from Bronze; a false
   positive silently poisons the library). Details: `references/curation.md`.
4. **Don't touch what you didn't make.** Never move, rename, or rewrite the
   user's existing files without showing a plan and getting explicit
   confirmation. Import mode defaults to *indexing in place*, not moving.
   Never edit content the user personally authored — suggest instead.
5. **Free, public, polite sources only.** RSS/Atom feeds, public APIs, sites
   that permit it. No paywalls, no scraping against terms of service, no
   credentials the user didn't hand you, and no storing full article text —
   store title + link + summary + your judgment.
6. **A failed fetch is not an empty result.** If a source errors or times
   out, record it as a failure to retry — never conclude "nothing new" from a
   broken fetch. (A production library once mislabeled a whole ticker as
   "has no data" because one HTTP 504 was misread as emptiness.)
7. **Finish the loop.** Setup is not done when files exist. It is done when
   the first collection ran, YOU judged the results, the first brief exists,
   and the user has performed one promote and one dismiss with their own
   hands. Then hand over per `references/keeper.md`.

## Level-0 mode (no Python available)

If the environment cannot run Python scripts (some agent platforms don't
bundle a runtime), everything still works — degrade gracefully:
- Index: maintain `index.md` (a Markdown table: title / tags / source / date)
  instead of SQLite.
- Fetching: use your own web-reading tools manually each round instead of the
  fetch scripts; record what you saw in `_pipeline/seen.md` to avoid
  re-processing.
- All curation rules, tiers, and red lines above apply unchanged.
Tell the user they are in Level-0 mode and what they'd gain by running the
scripts (scale, dedup memory, coverage stats).

## What this toolkit is NOT

Not a note-taking app, not a SaaS, not an Obsidian plugin, and not magic: the
quality of judgment depends on you, the hosting agent — which is why
`references/qc-rubric.md` exists, so the user can check your work. Be the kind
of librarian who invites the audit.
