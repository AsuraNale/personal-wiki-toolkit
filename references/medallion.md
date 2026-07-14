# Medallion tiers: Bronze / Silver / Gold

Read this before writing anything into a library. The tier system is the
single mechanism that keeps a self-feeding library from silting up with
noise. It borrows the "medallion architecture" idea from data engineering,
adapted for knowledge work.

## The three tiers

| Tier | What it is | Where it lives | Who put it there |
|---|---|---|---|
| **Bronze** | Everything the pipeline SAW. Raw candidates: url, title, source, first-seen date, judgment score & status | `intel.db` ledger (`seen` table) | fetch scripts |
| **Silver** | Items that passed machine judgment (score ≥ threshold). Structured metadata + a drafted brief entry | `intel.db` (`silver` table) + `_pipeline/silver/AUTO-*.md` drafts | the judging agent |
| **Gold** | Knowledge a human (or their trusted keeper) decided to keep. Curated notes and finalized briefs, indexed | `notes/`, `briefs/`, indexed in `kb.db` | promote — an explicit act |

The tier of an item is a statement about **how much scrutiny it survived**,
not about how interesting it looked.

## Rules

1. **Nothing skips a tier.** A hot-looking item still enters as Bronze and
   gets judged like everything else. Urgency is a reason to judge sooner,
   not to skip judgment.
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
6. **The empty/failed/blocked distinction.** An item can be absent from Bronze
   for very different reasons: the source genuinely had nothing (fine), the
   fetch failed (retry it), the config points somewhere wrong (`gap` — fix it),
   or an egress policy refused the request (`blocked` — allow the domain, or
   collect locally; retrying is useless). The ledger and logs must distinguish
   these states, because each implies a different fix. Conflating them once made
   a production library confidently report a data series as "empty" for weeks
   when the fetch was just erroring — and made a cloud round file 7 of 8
   policy-denied sources as "gap", advice that could never work.
   Details: `pipeline-discipline.md`.

## Silver is a queue, not a resting place

Silver exists so a human never has to look at raw noise, and so machine
enthusiasm never directly becomes "knowledge". But Silver items must FLOW:
either promoted or dismissed within a reasonable cadence. A growing Silver
backlog means curation has stalled — surface it to the user ("N items have
waited >2 weeks") rather than letting the library quietly die. The care
guide gives users a 2-minute daily habit precisely to keep this moving.

## What each tier is FOR when answering questions

When the library is asked a question:
- Answer from **Gold** by default, citing notes.
- You may mention relevant **Silver** items as "uncurated leads, not yet
  vetted" — clearly labeled.
- **Bronze** is not answer material; it exists for dedup and audit.
