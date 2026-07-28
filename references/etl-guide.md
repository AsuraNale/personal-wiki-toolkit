# ETL-type libraries: building a structured data library

Read this when the user wants a library of **structured facts or numbers** —
prices, stats, game data, metrics tracked over time — rather than a stream of
notes/briefs (intel-type) or a pile of files to organize (import-type). Be honest
with the user up front: for this type the toolkit gives **methodology, discipline,
and a worked example** (`examples/etl-kb/`), not a one-click scaffold. You and the
user design the schema and the fetchers together. This chapter is how to do that
without repeating the mistakes three production data libraries already made.

## Is it really an ETL-type library?

Choose data/ETL type only when all three hold:
- the unit of knowledge is a **row of structured fields** (a price, a stat line, a
  metric), not a document;
- the user wants to **query and compute** over it (compare, aggregate, chart), not
  just read it;
- there's a **repeatable source** (a public API, a downloadable dataset) you can
  fetch on a cadence.

If the user actually wants "research X and give me a report" — that's a one-shot
research task, not a library. If they want "track news/papers about X" — that's
intel-type. Don't force a data library onto a job that isn't one.

## Scope the watchlist before building

A data library tracks a **set of entities** (SKUs, tickers, series). Pin that set
down with the user first — the single most common under-spec is tracking *one*
representative per category when the user wanted the *whole segment*. Ask
explicitly: "the specific items you named, or every option in that class?" (one
RTX 5070, or the entire 50-series lineup?). The watchlist lives in `config.json`
as one entry per entity, so adding more is just more config rows — err toward
asking. A build that silently tracks one-per-category reads as complete when it
isn't. (A real Codex build tracked exactly one SKU per category because the
request said "one row per category"; the scope, not the toolkit, was the gap.)

## The shape of the work

ETL = **E**xtract (fetch from source) → **T**ransform (parse / normalize / derive)
→ **L**oad (into SQLite). The toolkit's scripts (`fetch_rss.py`, `pipeline.py`,
`index_db.py`) are built for the intel-type flow; for a data library you write a
**domain fetcher** in the same spirit. What carries over unchanged is the
*discipline*, not the code.

The agent/scripts split still holds: **scripts do the deterministic fetch + store;
the agent decides what's worth tracking, interprets the numbers, and judges
quality.** The agent never hand-edits the DB.

## Schema design

Read `references/storage.md` first — its five conventions are the foundation. For a
data library specifically:

1. **Pick a primary key that makes re-runs idempotent.** A natural key like
   `(entity, date)` or `(id, snapshot_date)`, so fetching an overlapping window
   upserts instead of duplicating. "Run it twice" must be safe.
2. **Separate raw from derived.** Store the fetched raw values; compute derived
   fields (ratios, aggregates) *from* them — and keep the ability to recompute.
   Never store only a derived number you can't re-derive.
3. **Audit columns, always:** `source`, `fetched_at`, `snapshot_date`. When a
   number looks wrong three weeks later, the row must say where it came from and when.
4. **Trust is a band, not a boolean.** `*_reliable` says whether a value is
   usable; it does not say how much the *source* is worth. If your library mixes
   official filings with aggregators or user reports, record a `source_type` band
   (`references/storage.md`) and **show it wherever you show the number** — two
   figures displayed identically are a claim that they are equally solid. Never
   average across bands.
5. **Reliability flags over silent exclusion.** When a value can't be trusted
   (missing input, a source returned a placeholder, an identity that didn't hold),
   keep the row and flag it (`*_reliable = 0`) rather than dropping it — visible
   doubt beats invisible absence. (A production library learned this when a balance
   sheet's assets = liabilities + equity didn't hold for a few entities: flagging
   beat hiding.)
6. **The empty/failed distinction is schema, not prose** (see
   `pipeline-discipline.md`): a fetch log with a `status` column
   (ok / empty / gap / failed / blocked) so "this series has no data" can never be
   confused with "the fetch failed" — or with "our egress policy refused to go there."

## Raw observations auto-append; only analysis is curated

A data library is **Shape B — accumulation**, not the Bronze/Silver/Gold tiers.
Its chain is **Fact → Derived → Conclusion**, and the full rules live in
`references/medallion.md` § *Shape B — accumulation*. The short version:

Each collection round **appends raw observation rows automatically**. A price
snapshot is a timestamped, sourced **Fact** — it goes straight into the table on
every run, final on write. **Do NOT gate raw snapshots behind human promotion**:
there is no queue for them to wait in, and putting one there stops the library.
What IS human-gated is the **Conclusion** — "this is a good buy window", a chosen
long-term watch item, an analysis note. *That* is what a human decides to keep.

A real build stalled its own price time-series by *proposing* snapshot `INSERT`s
for the user to run each week instead of appending them; **the table never grew a
second data point.** **Append the facts every round; curate the conclusions.**

> ⚠️ **Don't reach for Bronze/Silver/Gold here.** Those tiers are Shape A
> (adjudication: intel / import), where every item waits for a human verdict —
> `references/medallion.md` scopes them explicitly. A data library that gets the
> Shape A scaffold ends up with an empty Silver queue beside the table where its
> real data actually accumulates.

## Fetching structured data

- **Free, public, polite sources only** — public APIs, downloadable datasets,
  endpoints that permit it. No paywalled data, no ToS-hostile scraping, no
  credentials the user didn't provide. (If a source needs an API key, the **user**
  pastes it into a local secrets file — you never handle keys.)
- **Window your backfill** — page or date-window the initial load (month by month,
  say) so one request can't time out on a huge response, and a failure costs one
  window, not the whole history. Each window is idempotent, so a failed one retries.
- **Classify every fetch five ways** (ok / empty / gap / failed / blocked) and
  remember: **429 and 5xx are transient (retry next round); 4xx-except-403/407/408/429
  is permanent (fix the config); 403/407 and proxy tunnel refusals are `blocked`
  (allowlist the domain, or collect locally — retrying never helps); and a failed
  fetch is NOT an empty result.** A production library once reported a whole series
  as "empty" for weeks because one HTTP 504 was misread as emptiness; a cloud round
  lost 7 of 8 sources to policy denials it had labelled "gap".
- **Idempotent catch-up** — rebuild the work list from *state* (what's still
  missing), not from this run's catch, so an interrupted backfill resumes cleanly.

## Numeric QC — where data libraries live or die

A data library that's confidently wrong is worse than no library. Run
`references/qc-rubric.md` Rubric B, and **never verify from the builder's own
summary** (`references/qc-rubric.md` — the prime principle):

- **Source-of-truth sampling** — pick random stored values, re-fetch from the
  origin, compare. Exact match, or a documented transform.
- **Recompute derived values by hand** — take a few ratios/aggregates, recompute
  from the stored raw. They must match the stored derivation.
- **Empty vs failed** — for every empty table/series, check the fetch log:
  emptiness needs a positive explanation (source confirmed empty), never inferred
  from an error.
- **No silent truncation** — anywhere the system caps / paginates / samples, the
  cap is stated in output ("showing 50 of 740"), never implied completeness.
- **Idempotency** — run the fetch twice; the second run changes nothing.

## What to hand the user

A data library's "brief" is different from an intel library's: it's a **snapshot
view or a health card**, not a curated reading list. The keeper (data preset — see
`references/keeper.md`) answers with **numbers that cite their source table +
snapshot date + definition**, never computed from memory, and states known blind
spots up front (e.g. "field X is blocked by the source, industry-wide"). See
`examples/etl-kb/` for a runnable end-to-end instance: a free public API → a schema
that keeps revision history → windowed, resumable backfill → a recomputable
aggregate → the library's own QC. It also demonstrates the trap this chapter warns
about, with a verified before/after: **idempotent does not mean "ignore updates".**
