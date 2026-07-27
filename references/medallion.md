# Tiers: how knowledge earns its place

Read this before writing anything into a library. Tiering is what keeps a
self-feeding library from silting up with noise: **an item's tier states how much
scrutiny it survived**, not how interesting it looked.

## ⚠️ First: which shape is this library?

There are **two** shapes, and applying the wrong one does real damage. Decide
before you build.

| | **Shape A — adjudication** | **Shape B — accumulation** |
|---|---|---|
| Library types | intel, import | data / ETL |
| Chain | **Bronze → Silver → Gold** | **Fact → Derived → Conclusion** |
| What a human judges | **every item** | **the conclusion only** |
| Raw rows | wait in Silver for a verdict | **land final on write — they never wait** |
| Named | **Medallion** (`active`) | **Shape B** (`proposed` — see `glossary.md`) |

**Getting this wrong is not theoretical.** A production recall library was built
on Shape A and its Silver sat at 21 rows, 0 promoted / 0 dismissed, while the real
data accumulated in a separate table around it; the entire scaffold was deleted in
the rewrite. In the other direction, a build that gated raw price snapshots behind
human promotion — *proposing* weekly `INSERT`s instead of appending — left a time
series that **never grew a second data point**.

> Everything from "The three tiers" to "Silver is a queue" below is **Shape A**.
> Shape B has its own section, and its rules are not the same.

---

# Shape A — adjudication (Medallion)

## The three tiers

| Tier | What it is | Where it lives | Who put it there |
|---|---|---|---|
| **Bronze** | Everything the pipeline SAW. Raw candidates: url, title, source, first-seen date, judgment score & status | `intel.db` ledger (`seen` table) | fetch scripts |
| **Silver** | Items that passed machine judgment (score ≥ threshold). Structured metadata + a drafted brief entry | `intel.db` (`silver` table) + `_pipeline/silver/AUTO-*.md` drafts | the judging agent |
| **Gold** | Knowledge a human (or their trusted keeper) decided to keep. Curated notes and finalized briefs, indexed | `notes/`, `briefs/`, indexed in `kb.db` | promote — an explicit act |

## Rules

1. **Nothing skips a tier.** A hot-looking item still enters as Bronze and
   gets judged like everything else. Urgency is a reason to judge sooner,
   not to skip judgment.
   > ⚠️ **Shape A only.** In Shape B, raw facts are *supposed* to go straight
   > into the table — see below. Applying this rule there stalls the library.
   > **This includes things you looked up yourself.** An answer you researched
   > outside the library is not Gold because you wrote it well — its sources
   > enter as Bronze and get judged like any others (`keeper.md` § Answering
   > from outside the library).
2. **Promotion is explicit and attributed.** Bronze→Silver happens by
   scored judgment (see `curation.md`); Silver→Gold happens by a promote
   action with a human in the loop (the user, or the keeper if the user has
   delegated it in `keeper.md`). Both leave a record (score / date / actor).
3. **Demotion exists and has a memory.** A Silver item judged unworthy is
   **dismissed with a reason**, and the ledger remembers — so the same item
   (or its re-fetched twin) never resurfaces as "new". A dismissal without a
   recorded reason is a bug: the reason is what makes the decision auditable
   and teaches the judging criteria over time.
4. **Gold is small on purpose.** A library where everything is Gold has no
   Gold. If briefs are being promoted wholesale, the keep-threshold is too
   low or the judging has gone soft — check against `qc-rubric.md`.
5. **Tiers are per-item, never per-source.** A great source still emits
   noise; a mediocre source occasionally emits gold. Judge items.
6. **The empty/failed/blocked distinction.** *(Applies to both shapes.)* An item
   can be absent from Bronze for very different reasons: the source genuinely had
   nothing (fine), the fetch failed (retry it), the config points somewhere wrong
   (`gap` — fix it), or an egress policy refused the request (`blocked` — allow the
   domain, or collect locally; retrying is useless). The ledger and logs must
   distinguish these states, because each implies a different fix. Conflating them
   once made a production library confidently report a data series as "empty" for
   weeks when the fetch was just erroring — and made a cloud round file 7 of 8
   policy-denied sources as "gap", advice that could never work.
   Details: `pipeline-discipline.md`.

## Silver is a queue, not a resting place

Silver exists so a human never has to look at raw noise, and so machine
enthusiasm never directly becomes "knowledge". But Silver items must FLOW:
either promoted or dismissed within a reasonable cadence. A growing Silver
backlog means curation has stalled — surface it to the user ("N items have
waited >2 weeks") rather than letting the library quietly die. The care
guide gives users a 2-minute daily habit precisely to keep this moving.

---

# Shape B — accumulation (data / ETL libraries)

For libraries of structured facts — prices, measurements, filings, match records —
**the human gate moves off the rows and onto the conclusions.** Same discipline,
different shape.

## The three layers

| Layer | What it is | Human involvement |
|---|---|---|
| **Fact** | A timestamped, sourced observation. Appended automatically **every round**, final on write | **none** — never gate these |
| **Derived** | Aggregates, rollups, revision histories — anything **recomputable** from Fact | **none, and never by hand** |
| **Conclusion** | "This is a good buying window", a written analysis, a chosen watch item | ⭐ **this is what a human judges — this is the Gold** |

## Rules

1. **Append the facts every round; curate the conclusions.** A price snapshot is a
   timestamped, sourced *fact*, not a claim — it goes straight into the table.
   **Do NOT gate raw snapshots behind human promotion.** (A real build did, by
   proposing weekly `INSERT`s for the user to run; the table never grew a second
   data point.)
2. **Derived is never a source of truth, and never hand-edited.** If a derived
   table disagrees with the facts, recompute it — do not patch it. Anything you
   can rebuild from Fact must be rebuildable, in one command.
3. **Derived must not be filed as Gold.** They look alike — both are Markdown in
   `briefs/` — and mistaking one for the other **mis-states the library's health**
   in both directions. Tell them apart by what the file says about itself:
   - **Human Gold**: `status: gold` in frontmatter; the body is analysis or judgment
   - **Auto Derived**: `author: <system name>`, or a generated timestamp in the body;
     the body is rendered statistics
4. **The Conclusion layer will not happen by itself — it has to be scheduled and
   it has to be recorded.** Both halves are load-bearing:
   - **① Produce a draft on a cadence** (end-of-day, weekly — whatever fits the
     data). Without something concrete to react to, a human never starts.
   - **② Write the verdict back into the library.** A decision made in someone's
     head, or in a chat window, leaves the library unable to show it was ever read.

   > **Evidence (11 real libraries):** four highly active libraries with **no draft
   > step** produced **zero** human Gold — 420 rounds/1,109 rows · 165/89,136 ·
   > 127/297 · 44/9,533, across three unrelated domains, so "the library was idle"
   > does not explain it. And a library **with** 21 drafts and 3,000 rounds *still*
   > shows zero, because its verdicts were only ever made outside the library.
   >
   > **The cheapest thing that works costs one line.** A tracker with **zero**
   > collection rounds has 6 Gold notes, each opening with
   > `> **Promoted from**: <original item / URL>`. No table, no promote command —
   > just a verdict that left a traceable artifact. That is the whole requirement.

## What Shape B does NOT do

No relevance scoring (validation happens on write instead: schema, primary key,
range). **No per-row human promotion** — that is the failure mode above, not a
missing feature.

---

# What each tier is FOR when answering questions

When the library is asked a question:
- Answer from **Gold** (Shape A) / **Conclusions and Facts** (Shape B), citing sources.
- You may mention relevant **Silver** items as "uncurated leads, not yet
  vetted" — clearly labeled.
- **Bronze** is not answer material; it exists for dedup and audit.
