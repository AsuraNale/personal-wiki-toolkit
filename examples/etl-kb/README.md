# Example: a data/ETL-type library ("Quake Log")

A worked example of a **data/ETL-type library** — structured numbers tracked over
time, not notes. Companion to `references/etl-guide.md` and `references/storage.md`.

**It runs.** Everything below is reproducible from this folder:

```
py -X utf8 fetch_quakes.py fetch          # pull the day feed, upsert, log the round
py -X utf8 fetch_quakes.py backfill       # walk the month feed one day-window at a time
py -X utf8 fetch_quakes.py agg            # recompute the derived table
py -X utf8 fetch_quakes.py qc             # the library audits itself
py -X utf8 fetch_quakes.py stats
```

## ⚠️ Why this example is NOT structured like `intel-kb`

It has no `notes/`, no `briefs/`, no `_pipeline/silver/`, no promote/dismiss.
**That is deliberate, not an omission** — and the difference used to be silent, which
is why this section exists.

Medallion's Bronze→Silver→Gold models *how much human scrutiny a claim survived* — the
right shape when the raw material is text and a person must decide what becomes
knowledge. **This library's raw material is measurements.** A timestamped, sourced
magnitude reading is a fact on arrival; gating it behind human approval would add
ceremony and remove nothing. So raw observations **auto-append every round**, and the
human-gated part is the *interpretation*, which lives wherever the owner writes it —
not in a tier directory.

Same discipline, different shape. **If you are building a data library and the
intel-type scaffold feels like it is fighting you, this is why.**

## The trap this example exists to show

USGS **revises** events. A quake first published at M5.8 is routinely re-graded to M6.1
once more seismograph data arrives; depth and the place string move too.

A naive `INSERT OR IGNORE` pipeline is perfectly idempotent — **and silently keeps the
first value forever.**

```
idempotent  !=  "ignore updates"
```

So this fetcher uses `properties.updated` (USGS's own revision clock) as the signal,
applies the new values to `quakes`, and appends the before/after to `quake_revisions`.
Current truth stays queryable; history stays auditable; **nothing is overwritten
without a trace.**

Verified end-to-end (a record was rolled back to a prior version, then re-fetched):

```
revised=1
  magnitude  4.5     -> 4.8
  depth_km   177.259 -> 172.259
  updated:   2000-01-01Z -> 2026-07-20 13:10:38Z
re-run: revised=0, revisions table unchanged    <- replay is idempotent
revision_count = 1, not 2   <- one re-grade moving two fields is ONE revision moment
```

That last line is the part worth copying: **count revision moments, not field changes**,
or your counter and your history will quietly disagree — and `qc` will tell you so.

## Disciplines demonstrated

| Discipline | Where to look |
|---|---|
| Idempotent PK **+ revision tracking** (not blind IGNORE) | `upsert()` |
| Audit columns (`source`, `first_fetched_at`, `last_fetched_at`, `usgs_updated`) | `SCHEMA` |
| Reliability flag over silent exclusion (`mag_reliable=0` — kept and flagged) | `parse_feature()` |
| Derived values stay recomputable (`daily_agg`) | `cmd_agg()` + the `qc` drift check |
| Windowed, **resumable** backfill (per-day commit + per-day ledger row) | `cmd_backfill()` |
| 5-way fetch status, classified at **both** the HTTP and the proxy layer | `http_get()` |
| The library ships **its own QC** | `cmd_qc()` — 8 checks, each naming its own fix |

## A note on the feed choice

USGS also exposes an FDSN query API taking arbitrary start/end times — the natural
backfill source. **It is not reachable from every environment**: it returned 404 for
every variant from the machine this example was built on, while the summary feeds
worked fine. So backfill walks the month summary feed and accounts for it one day at a
time — same discipline, one less external dependency.

That is itself the lesson: **the environment is part of the design.** Discovering this
after shipping would have looked like a bug in the pipeline rather than a fact about
the world.

---

For an intel-type library instead (text, judged and curated), see `examples/intel-kb/`.
