# Storage: the dual-layer model and its schema

Read this when designing a library's SQLite schema, or when deciding whether a
piece of information belongs in a Markdown file or in the index. The schema
below is what the toolkit's scripts actually create — documented here so a
future agent (or a curious user) can reason about the ledger without reading
the code.

## Two layers, two databases

Markdown is the human-readable truth; SQLite is the machine-queryable
derivative and ledger. A library carries **two** SQLite files with very
different lifecycles — knowing which is which tells you what to back up:

| DB | Owner | Lifecycle | If you lose it |
|---|---|---|---|
| `intel.db` | `pipeline.py` | **Ledger** — append/update only, never rebuilt; it *is* the memory (dedup, audit trail, dismissals) | you lose your dedup memory and audit history — **back this up** |
| `kb.db` | `index_db.py` | **Derived** — a view of the Markdown files; `build` drops and regenerates it any time | you lose nothing but one `index_db.py build` |

Rule of thumb: **back up the ledger, not the index.** The index is
reconstructible from the Markdown; the ledger is not.

**Level-0 libraries** (no Python) have neither file: `intel.db` is replaced by
`_pipeline/seen.md` (a running list so you don't re-process), and `kb.db` by
`index.md` (a Markdown table). The concepts below still apply; only the
storage medium changes.

## intel.db — the pipeline ledger

### `seen` (Bronze)

```sql
CREATE TABLE seen (
    url         TEXT PRIMARY KEY,   -- layer-1 dedup: the same link never re-enters
    title       TEXT,
    source      TEXT,               -- config source name (audit: where did this come from)
    topic       TEXT,               -- source's topic hint (the judge may override)
    summary     TEXT,               -- title + link + summary only; full article text is never stored
    date        TEXT,               -- the item's own published date (YYYY-MM-DD, best effort)
    first_seen  TEXT,               -- when WE first saw it
    relevance   REAL DEFAULT -1,    -- -1 = not judged yet
    status      TEXT DEFAULT 'new'  -- new -> kept | low (by apply) -> dismissed (by human)
);
```

- `status` lifecycle: `new` (awaiting judgment) → `kept` (≥ threshold, entered
  Silver) or `low` (judged below threshold; stays Bronze, recoverable) →
  `dismissed` (a human said no, with a reason recorded in `silver`).
- `pending.json` is regenerated from `WHERE status='new'` on every fetch — so
  candidates from an interrupted round reappear until judged. **Catch-up is a
  property of the schema, not a special code path.**

### `silver` (Silver)

```sql
CREATE TABLE silver (
    url            TEXT PRIMARY KEY,
    title          TEXT,
    topic          TEXT,
    relevance      REAL,            -- a MACHINE fact (the judge's score)
    one_line       TEXT,            -- the judge's "what this actually IS" line
    dedup_key      TEXT,            -- layer-2: normalized title (lowercase, alnum + CJK, truncated)
    judged_at      TEXT,            -- UTC timestamp (YYYY-MM-DD HH:MM:SSZ)
    promoted       INTEGER DEFAULT 0,   -- a HUMAN fact
    promoted_at    TEXT,
    dismissed      INTEGER DEFAULT 0,   -- a HUMAN fact
    dismiss_reason TEXT,            -- required in spirit: a dismissal without a reason is a lost training signal
    dismissed_at   TEXT
);
```

- **The idempotent write pattern is the single most important trick in the
  file:** `INSERT OR IGNORE (url, promoted=0, dismissed=0)` **then** `UPDATE`
  the judgment fields. Re-applying judgments can never wipe a human's
  promote/dismiss flags. "Run apply twice" is always safe.
- `relevance` is a machine fact; `promoted`/`dismissed` are human facts. They
  share a row, but only their own writer touches each side.
- **The daily Silver draft is regenerated from a query, not appended to.**
  `_pipeline/silver/AUTO-<date>.md` is a *view* of this table
  (`judged_at` within the local day's window `AND promoted=0 AND dismissed=0`),
  so multiple apply rounds in one day **union naturally** instead of
  overwriting each other. (A production library once lost its morning items
  when an afternoon round rewrote the file. Rebuild-from-query prevents it
  structurally.)
- **Timezone note:** `judged_at` is stored in UTC, but the daily draft is
  filtered by the *user's local day* mapped to a UTC window — otherwise an
  evening apply run in a UTC-behind zone (e.g. UTC−4 after 20:00) would write
  `judged_at` into the next UTC calendar day and silently vanish from "today's"
  draft. Store UTC; filter by the local day's UTC bounds.

### `fetch_log` (the GAP ≠ FETCH-FAIL ledger)

```sql
CREATE TABLE fetch_log (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ts     TEXT,
    source TEXT,
    kind   TEXT,                    -- rss | arxiv | hn
    status TEXT,                    -- ok | empty | gap | failed | blocked  <- the five-way distinction
    items  INTEGER,
    detail TEXT                     -- e.g. "HTTP 503" / "HTTP 404 (check the URL...)"
);
```

The four statuses are the whole point of this table:

- `ok` — fetched and parsed, ≥1 item.
- `empty` — fetched fine, **zero items** (the source genuinely had nothing). Fine.
- `gap` — **permanent-looking** (HTTP 4xx except 408/429, unparseable feed).
  Fix the config; blind retry won't help.
- `failed` — **transient** (HTTP 5xx, 408/429 rate-limit, timeout, network).
  Retry next round. The items were *not fetched*, which is **not the same as
  "there were no items."**

A production library once reported a whole data series as "empty" for weeks
because one HTTP 504 was misread as emptiness. This table exists so that can't
happen silently — `pipeline.py stats` surfaces the latest round per source, and
a `failed` streak on one source is a health problem to show the user, not to
average away.

## kb.db — the derived index

```sql
CREATE TABLE notes (
    path     TEXT PRIMARY KEY,      -- layer-3 dedup: relative path, forward slashes on ALL platforms
    title    TEXT,                  -- frontmatter title -> first H1 -> filename stem
    category TEXT,                  -- which configured dir it came from: notes | briefs | inbox
    tags     TEXT,                  -- comma-joined frontmatter tags
    created  TEXT,                  -- frontmatter date/created (the author's claim)
    updated  TEXT,                  -- file mtime (the filesystem's fact)
    outlinks TEXT,                  -- comma-joined [[wikilinks]] + relative (*.md) links
    summary  TEXT,                  -- first body paragraph, plain-texted, ~240 chars
    words    INTEGER
);
```

- The pipeline dir (`_pipeline/`) is **deliberately not indexed**: Silver
  drafts are not Gold knowledge and must not surface in library search (see
  `medallion.md`).
- `coverage` derives per-category counts and date ranges, top tags, and
  **orphans** (notes nothing links to) from this table. Orphans aren't wrong,
  but a growing pile means knowledge is being written and never woven in —
  worth surfacing to the user.

## Schema conventions (carried over from three production libraries)

1. **PK = idempotency.** Every table's primary key is chosen so a re-run
   upserts instead of duplicating (`url` / `url` / `path`). "Run it twice" must
   always be safe — this is the property that lets fetch, apply, and index all
   be re-run without fear.
2. **Audit columns beat memory.** `source`, `first_seen`, `judged_at`, `*_at` —
   every state transition records who and when. When a judgment looks wrong
   three weeks later, the row explains itself.
3. **Human flags are sacred.** Machine writes never clear
   `promoted`/`dismissed` (the INSERT-OR-IGNORE-then-UPDATE pattern above).
4. **The empty/failed distinction is schema, not prose.** It has its own status
   column and its own table. Discipline that lives only in documentation gets
   lost; discipline encoded in a column gets enforced.
5. **Reliability flags over silent exclusion** (for ETL-type libraries — see
   `etl-guide.md`): when a derived number can't be trusted, keep the row and
   flag it (`*_reliable=0`) rather than dropping it. Visible doubt beats
   invisible absence.
