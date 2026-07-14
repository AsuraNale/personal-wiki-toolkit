# Example: a data/ETL-type library ("Quake Log")

A worked example of a **data/ETL-type library** — structured numbers tracked over
time, not notes. Companion to `references/etl-guide.md`.

It's a minimal, real, end-to-end instance:
**a free public API (USGS earthquakes, no auth) → a small SQLite schema → a
queryable table a keeper can answer from.**

Unlike `intel-kb`, this one is **runnable**:

```
python fetch_quakes.py fetch    # pull recent M4.5+ quakes into quakes.db
python fetch_quakes.py stats    # row counts + last fetch status
```

What to look at:
- `fetch_quakes.py` — the domain fetcher. See the ETL disciplines from
  `etl-guide.md` in ~90 lines of stdlib: **idempotent PK** (USGS event id →
  `INSERT OR IGNORE`), **audit columns** (`source`, `fetched_at`), a **reliability
  flag** (`mag_reliable = 0` when magnitude is missing — the row is kept and
  flagged, not dropped), and the **5-way fetch status** (ok / empty / gap / failed /
  blocked — a failed fetch is never recorded as "empty", and a policy refusal is
  neither "empty" nor "fix your config": allowlist the domain, or fetch locally).
- `keeper.md` — the keeper's role with the **data preset**: answers cite source +
  snapshot + definition, state blind spots, never compute from memory.
- `CLAUDE.md` — the library's agent-memory.

This is a teaching skeleton, not a full library — a real data library adds more
tables, windowed backfill, a schedule, and its own QC (see `references/qc-rubric.md`
Rubric B).
