# Interview: building an intel-type library from scratch

You are running a guided setup. The user wants a library that **tracks a
domain over time**. Your job across four phases: understand → generate →
prove it works → hand over. Conduct everything in the user's language.

**Style rules for the whole interview:**
- Propose, don't interrogate: draft something concrete from what the user
  said, show it, let them react. One batched follow-up beats five questions.
- Every phase ends with a visible artifact the user can inspect.
- Don't over-promise: this library will be as good as its sources and its
  curation habit. Say so once, plainly.

---

## Phase 1 — Understand the need (aim: ≤3 exchanges)

Collect, in whatever order the conversation allows:

1. **Domain and angle.** Not just "AI" but *what about it* — "agent tooling
   for practitioners" reads very differently from "AI policy for a lawyer".
   Ask what decisions or output this library should feed (research? writing?
   investing? hobby depth?). The angle drives topic design and judging.
2. **Topics** (3–6). Draft them yourself from the domain + angle, each with
   2–4 search keywords. Keywords must be *searchable strings that would
   actually appear in titles*, not abstract category names. Show the draft
   table; let the user edit.
3. **Sources.** Recommend by domain:
   - academic-flavored → arXiv queries (exact-phrase keywords);
   - tech/startup-flavored → Hacker News (Algolia search, min-points filter);
   - any domain → RSS/Atom feeds of the blogs/newsletters/news sites the user
     already reads (ask them for 2–5; these are usually the best signal);
   - avoid: anything paywalled or ToS-hostile (SKILL.md rule 5).
   Aim for 3–8 sources total. More sources ≠ better — every source adds noise
   to judge.
4. **Cadence & threshold.** Defaults: daily collection, keep-threshold 0.7
   (items you judge below it stay in Bronze, invisible). Only surface these
   if the user seems opinionated; otherwise state the defaults and move on.
5. **Keeper?** Default yes: a named librarian role with written duties
   (`references/keeper.md`). If the user will only ever chat casually with
   the library, they can skip it.

**Artifact:** a filled `config.json` draft (schema:
`templates/config.example.json`), shown to the user for one confirmation
pass. Do not proceed to Phase 2 without an explicit "looks good".

---

## Phase 2 — Scaffold

Read `setup/SCAFFOLD.md` and execute it with the confirmed config. Summary of
what it produces (details there): library directory tree, `config.json`, the
library's own `CLAUDE.md`/`AGENTS.md` memory file, SQLite databases (or
Level-0 index), instantiated scripts, and — if the user wants automation —
platform-specific schedule registration instructions (the user runs those
themselves; scheduled-task registration is often privileged).

**Artifact:** the tree, printed, with one line per item explaining what it is.

---

## Phase 3 — First run (never skip; never "set up now, run later")

An unproven pipeline is a broken pipeline. Walk it end to end NOW:

1. Run the fetch: `python scripts/pipeline.py fetch` (from the library root).
   It writes `_pipeline/pending.json` — the judgment queue. If zero items
   arrive, treat it as a problem to diagnose (source config? network? — see
   `references/pipeline-discipline.md`), not something to shrug at.
2. **You are the judge now.** Read `references/curation.md` (judging criteria
   + output format), score every pending item, write
   `_pipeline/judgments.json`.
3. Apply: `python scripts/pipeline.py apply`. This moves keepers into Silver
   and writes the draft brief (`_pipeline/silver/AUTO-<date>.md`).
4. Show the user the brief. Then the **teaching moment** — do these two
   actions *with* them, not for them:
   - pick the best item together → `python scripts/pipeline.py promote <url>`
     → show them where it landed (Gold) and how the index reflects it;
   - pick the weakest item → `python scripts/pipeline.py dismiss <url>
     "<reason>"` → explain that dismissed items never resurface, and the
     reason is kept for audit.
   These two verbs are 90% of the curation the user will ever do by hand.

**Artifact:** first brief + one promoted note + one dismissal, all real.

**Level-0 variant:** same loop, but you fetch with your own web tools, keep
`_pipeline/seen.md` as memory, and append to `index.md` instead of applying
to SQLite.

---

## Phase 4 — Handover

1. If keeper enabled: instantiate `templates/keeper-instructions.template.md`
   into the library as `keeper.md` (fill domain, duties, red lines — see
   `references/keeper.md` for the role definition).
2. Give the user the **one-page care guide** (write it into the library as
   `CARE.md`, in their language):
   - daily/whenever: skim the new brief (2 min);
   - promote what deserves permanence, dismiss what doesn't — with reasons;
   - weekly: ask the library agent "what's new and what's stale?" (coverage);
   - monthly: skim `references/qc-rubric.md` checks — or just ask the agent
     to run a self-audit and show evidence.
3. Remind them: the toolkit repo can be deleted; the library is
   self-describing via its own memory file. Updates to the toolkit can be
   re-applied by re-reading it against an existing library (idempotent
   scaffold).
4. State honestly what was NOT set up (e.g. schedule not registered yet, or
   Level-0 mode) and what the user must do for it.

Done means: the user watched the loop run once, touched promote/dismiss with
their own hands, and knows the three care actions. Anything less is not done.
