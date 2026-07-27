#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quake Log - a data/ETL-type library (personal-wiki-toolkit worked example).

Pulls earthquakes from the USGS public feeds (free, no auth) into SQLite.
Companion to references/etl-guide.md and references/storage.md.

    python fetch_quakes.py fetch [--window day|week|month]
    python fetch_quakes.py backfill [--window month]   # windowed, resumable
    python fetch_quakes.py agg [--rebuild]             # recompute derived table
    python fetch_quakes.py stats
    python fetch_quakes.py qc                          # the library audits itself
    python fetch_quakes.py schedule                    # print the registration command

Pure Python 3.9+ stdlib, no dependencies.

WHY THIS EXAMPLE TRACKS REVISIONS
---------------------------------
USGS *revises* events. A quake first published at M5.8 is routinely re-graded to
M6.1 once more seismograph data arrives; depth and the place string move too.
A naive `INSERT OR IGNORE` pipeline is perfectly idempotent -- and silently keeps
the FIRST value forever. That is the trap this example exists to show:

    idempotent  !=  "ignore updates"

So we use `properties.updated` (USGS's own revision clock) as the signal, apply
the new values to the main table, and append the before/after to
`quake_revisions`. Current truth stays queryable; history stays auditable.
Nothing is overwritten without a trace.

DISCIPLINES DEMONSTRATED
------------------------
- Idempotent PK (USGS event id) PLUS revision tracking, not blind IGNORE.
- Audit columns: source, first_fetched_at, last_fetched_at, usgs_updated.
- Reliability flag: mag_reliable=0 when magnitude is null -- kept and flagged,
  never dropped.
- Derived values stay recomputable: daily_agg can always be rebuilt from quakes,
  and `qc` proves it still matches.
- Windowed, resumable backfill: each day-window commits and logs on its own.
- 5-way fetch status (ok/empty/gap/failed/blocked), classified at BOTH the HTTP
  layer and the proxy layer -- a failed fetch is never recorded as "empty", and a
  policy refusal is neither "empty" nor "your config is wrong".
- The library ships its own QC instead of hoping someone remembers to check.

A NOTE ON THE FEED CHOICE
-------------------------
USGS also exposes an FDSN query API (fdsnws/event/1.0/query) that takes an
arbitrary start/end time. It is the natural backfill source -- but it is not
reachable from every environment (it returned 404 for every variant from the
machine this example was built on, while the summary feeds worked fine). So
backfill here walks the month summary feed and accounts for it one day at a
time. Same discipline, one less external dependency.
"""
import argparse
import json
import sqlite3
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary"
FEEDS = {
    "day": BASE + "/4.5_day.geojson",
    "week": BASE + "/4.5_week.geojson",
    "month": BASE + "/4.5_month.geojson",
}
DB = Path(__file__).resolve().parent / "quakes.db"
TIMEOUT = 25
SOURCE = "USGS"

# Fields that are part of the scientific record: a change in any of them is a
# revision worth keeping. Deliberately NOT every field -- USGS also churns
# felt-report counts and tsunami flags, and logging those would bury real re-grades.
TRACKED = ("magnitude", "depth_km", "place", "time_utc")

SCHEMA = """
CREATE TABLE IF NOT EXISTS quakes (
    id               TEXT PRIMARY KEY,  -- USGS event id: the idempotency key
    time_utc         TEXT,
    place            TEXT,
    magnitude        REAL,
    lon              REAL,
    lat              REAL,
    depth_km         REAL,
    usgs_updated     TEXT,              -- USGS's own revision clock
    source           TEXT,              -- audit: where it came from
    first_fetched_at TEXT,              -- audit: when WE first saw it
    last_fetched_at  TEXT,              -- audit: when WE last confirmed it
    mag_reliable     INTEGER DEFAULT 1, -- 0 = magnitude was null upstream
    revision_count   INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS quake_revisions (
    rev_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    quake_id       TEXT NOT NULL,
    field          TEXT NOT NULL,
    old_value      TEXT,
    new_value      TEXT,
    updated_before TEXT,
    updated_after  TEXT,
    observed_at    TEXT,
    -- Replaying the same feed must not duplicate history:
    UNIQUE (quake_id, field, old_value, new_value, updated_after)
);
CREATE TABLE IF NOT EXISTS fetch_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT,
    status        TEXT,   -- ok | empty | gap | failed | blocked
    window        TEXT,   -- which feed / day-window this row accounts for
    items_seen    INTEGER,
    items_new     INTEGER,
    items_revised INTEGER,
    detail        TEXT
);
CREATE TABLE IF NOT EXISTS daily_agg (
    day           TEXT PRIMARY KEY,
    n_events      INTEGER,
    max_mag       REAL,
    mean_mag      REAL,
    mean_depth_km REAL,
    computed_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_quakes_time ON quakes (time_utc);
CREATE INDEX IF NOT EXISTS idx_rev_quake   ON quake_revisions (quake_id);
"""


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def ms_to_utc(ms):
    if not ms:
        return None
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


# A proxy/egress refusal often surfaces BELOW HTTP: an https CONNECT refused by a
# sandbox proxy raises OSError("Tunnel connection failed: 403 Forbidden"), not an
# HTTPError. Classify at both layers, or one identical denial lands in two states.
BLOCK_SIGNATURES = ("tunnel connection failed", "host_not_allowed", "proxy authentication",
                    "forbidden by proxy", "blocked by policy")


def http_get(url):
    """GET url; classify failures as blocked / gap / failed.

    Three states because each needs a DIFFERENT fix:
    allowlist the domain / fix the config / retry next round.
    """
    req = urllib.request.Request(url, headers={"User-Agent": "pwt-etl-example/0.2"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code in (408, 429):
            raise RuntimeError("failed:HTTP %d (rate-limit/timeout, transient)" % e.code)
        if e.code in (403, 407):
            raise RuntimeError(
                "blocked:HTTP %d refused. In a cloud/sandbox, check the egress allowlist "
                "FIRST (most common); may also be anti-bot or auth. NOT evidence the feed "
                "is empty, and retrying will not help." % e.code)
        if 400 <= e.code < 500:
            raise RuntimeError("gap:HTTP %d (check the feed URL)" % e.code)
        raise RuntimeError("failed:HTTP %d" % e.code)
    except Exception as e:
        if any(s in str(e).lower() for s in BLOCK_SIGNATURES):
            raise RuntimeError("blocked:%s: %s - looks like an egress policy, not the feed; "
                               "check the allowlist. Retrying will not help."
                               % (type(e).__name__, str(e)[:80]))
        raise RuntimeError("failed:%s" % type(e).__name__)


def connect():
    conn = sqlite3.connect(str(DB))
    conn.executescript(SCHEMA)
    return conn


def parse_feature(f):
    p = f.get("properties", {}) or {}
    g = (f.get("geometry", {}) or {}).get("coordinates", [None, None, None]) or []
    mag = p.get("mag")
    return {
        "id": f.get("id"),
        "time_utc": ms_to_utc(p.get("time")),
        "place": p.get("place"),
        "magnitude": mag,
        "lon": g[0] if len(g) > 0 else None,
        "lat": g[1] if len(g) > 1 else None,
        "depth_km": g[2] if len(g) > 2 else None,
        "usgs_updated": ms_to_utc(p.get("updated")),
        "mag_reliable": 0 if mag is None else 1,
    }


def upsert(conn, rec):
    """Insert a new event, or apply a revision and record its history.

    Returns "new" | "revised" | "unchanged".
    """
    row = conn.execute(
        "SELECT time_utc, place, magnitude, depth_km, usgs_updated "
        "FROM quakes WHERE id=?", (rec["id"],)).fetchone()

    if row is None:
        conn.execute(
            "INSERT INTO quakes (id,time_utc,place,magnitude,lon,lat,depth_km,usgs_updated,"
            "source,first_fetched_at,last_fetched_at,mag_reliable,revision_count) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0)",
            (rec["id"], rec["time_utc"], rec["place"], rec["magnitude"], rec["lon"],
             rec["lat"], rec["depth_km"], rec["usgs_updated"], SOURCE, now(), now(),
             rec["mag_reliable"]))
        return "new"

    old = {"time_utc": row[0], "place": row[1], "magnitude": row[2], "depth_km": row[3]}
    updated_before = row[4]

    # Only inspect fields when USGS says the event changed. Diffing on every fetch
    # would churn on float formatting; the upstream clock is the authority on
    # "was this re-graded?".
    changed = {}
    if rec["usgs_updated"] and rec["usgs_updated"] != updated_before:
        for field in TRACKED:
            if old.get(field) != rec[field]:
                changed[field] = (old.get(field), rec[field])

    if not changed:
        conn.execute("UPDATE quakes SET last_fetched_at=? WHERE id=?", (now(), rec["id"]))
        return "unchanged"

    for field, (was, becomes) in changed.items():
        # UNIQUE(...) makes replaying the same feed a no-op instead of duplicate history.
        conn.execute(
            "INSERT OR IGNORE INTO quake_revisions (quake_id,field,old_value,new_value,"
            "updated_before,updated_after,observed_at) VALUES (?,?,?,?,?,?,?)",
            (rec["id"], field, None if was is None else str(was),
             None if becomes is None else str(becomes),
             updated_before, rec["usgs_updated"], now()))
    conn.execute(
        "UPDATE quakes SET time_utc=?, place=?, magnitude=?, depth_km=?, usgs_updated=?, "
        "last_fetched_at=?, mag_reliable=?, revision_count=revision_count+1 WHERE id=?",
        (rec["time_utc"], rec["place"], rec["magnitude"], rec["depth_km"],
         rec["usgs_updated"], now(), rec["mag_reliable"], rec["id"]))
    return "revised"


def log_fetch(conn, status, window, seen, new, revised, detail=""):
    conn.execute(
        "INSERT INTO fetch_log (ts,status,window,items_seen,items_new,items_revised,detail) "
        "VALUES (?,?,?,?,?,?,?)", (now(), status, window, seen, new, revised, detail))


def cmd_fetch(window="day"):
    conn = connect()
    status, detail, seen, new, revised = "ok", "", 0, 0, 0
    try:
        data = json.loads(http_get(FEEDS[window]))
        feats = data.get("features", [])
        seen = len(feats)
        for f in feats:
            rec = parse_feature(f)
            if not rec["id"]:
                continue
            outcome = upsert(conn, rec)
            new += outcome == "new"
            revised += outcome == "revised"
        if not feats:
            status, detail = "empty", "feed parsed fine, zero events in window (genuine empty)"
    except RuntimeError as e:
        kind, _, msg = str(e).partition(":")
        status, detail = kind, msg   # gap / failed / blocked -- never silently "empty"
    log_fetch(conn, status, window, seen, new, revised, detail)
    conn.commit()
    conn.close()
    print("fetch[%s]: status=%s seen=%d new=%d revised=%d%s"
          % (window, status, seen, new, revised, (" - " + detail) if detail else ""))
    return 0 if status in ("ok", "empty") else 1


def cmd_backfill(window="month"):
    """Windowed, resumable backfill.

    The month feed arrives as one blob, but we account for it ONE DAY AT A TIME:
    each day-window commits separately and writes its own fetch_log row. If the
    process dies halfway, the ledger says exactly which days landed -- and
    re-running is a no-op for those (idempotent upsert), so you just run it again.
    """
    conn = connect()
    try:
        data = json.loads(http_get(FEEDS[window]))
    except RuntimeError as e:
        kind, _, msg = str(e).partition(":")
        log_fetch(conn, kind, "backfill:" + window, 0, 0, 0, msg)
        conn.commit()
        conn.close()
        print("backfill: status=%s - %s" % (kind, msg))
        return 1

    by_day = defaultdict(list)
    for f in data.get("features", []):
        rec = parse_feature(f)
        if rec["id"] and rec["time_utc"]:
            by_day[rec["time_utc"][:10]].append(rec)

    if not by_day:
        log_fetch(conn, "empty", "backfill:" + window, 0, 0, 0, "no events in feed")
        conn.commit()
        conn.close()
        print("backfill: empty feed (genuine empty, not a failure)")
        return 0

    tot_new = tot_rev = 0
    for day in sorted(by_day):
        recs = by_day[day]
        new = rev = 0
        for rec in recs:
            outcome = upsert(conn, rec)
            new += outcome == "new"
            rev += outcome == "revised"
        log_fetch(conn, "ok", "day:" + day, len(recs), new, rev, "backfill window")
        conn.commit()          # per-window commit = resumable
        tot_new += new
        tot_rev += rev
    conn.close()
    print("backfill[%s]: %d day-windows, %d new, %d revised"
          % (window, len(by_day), tot_new, tot_rev))
    return 0


def cmd_agg(rebuild=False):
    """Recompute the derived table.

    daily_agg holds nothing that cannot be re-derived from `quakes`. That is the
    whole point: never store a number you cannot regenerate. `--rebuild` wipes and
    recomputes; `qc` then proves the table still matches its source.
    """
    conn = connect()
    if rebuild:
        conn.execute("DELETE FROM daily_agg")
    rows = conn.execute(
        "SELECT substr(time_utc,1,10) AS day, COUNT(*), MAX(magnitude), "
        "AVG(magnitude), AVG(depth_km) FROM quakes WHERE time_utc IS NOT NULL "
        "GROUP BY day").fetchall()
    for day, n, mx, avg, avgd in rows:
        conn.execute(
            "INSERT INTO daily_agg (day,n_events,max_mag,mean_mag,mean_depth_km,computed_at) "
            "VALUES (?,?,?,?,?,?) ON CONFLICT(day) DO UPDATE SET n_events=excluded.n_events, "
            "max_mag=excluded.max_mag, mean_mag=excluded.mean_mag, "
            "mean_depth_km=excluded.mean_depth_km, computed_at=excluded.computed_at",
            (day, n, mx, avg, avgd, now()))
    conn.commit()
    conn.close()
    print("agg: %d day(s) computed%s" % (len(rows), " (rebuilt from source)" if rebuild else ""))
    return 0


def cmd_stats():
    if not DB.exists():
        print("no quakes.db yet - run: python fetch_quakes.py fetch")
        return 0
    conn = connect()
    one = lambda s: conn.execute(s).fetchone()
    n = one("SELECT COUNT(*) FROM quakes")[0]
    unrel = one("SELECT COUNT(*) FROM quakes WHERE mag_reliable=0")[0]
    revs = one("SELECT COUNT(*) FROM quake_revisions")[0]
    revq = one("SELECT COUNT(*) FROM quakes WHERE revision_count>0")[0]
    span = one("SELECT MIN(time_utc), MAX(time_utc) FROM quakes")
    print("quakes    : %d rows (%d flagged mag_reliable=0)" % (n, unrel))
    print("time span : %s .. %s" % (span[0] or "-", span[1] or "-"))
    print("revisions : %d field-change(s) across %d event(s)" % (revs, revq))
    print("daily_agg : %d day(s)" % one("SELECT COUNT(*) FROM daily_agg")[0])

    print("\nfetch_log (last 6):")
    for r in conn.execute("SELECT ts,status,window,items_seen,items_new,items_revised,detail "
                          "FROM fetch_log ORDER BY id DESC LIMIT 6"):
        print("  %s %-7s %-14s seen=%-4d new=%-4d rev=%-3d %s"
              % (r[0], r[1], r[2], r[3], r[4], r[5], (r[6] or "")[:38]))

    rows = conn.execute("SELECT id,place,magnitude,revision_count FROM quakes "
                        "WHERE revision_count>0 ORDER BY revision_count DESC LIMIT 5").fetchall()
    print("\nmost-revised events:" if rows else "\nmost-revised events: (none yet)")
    for r in rows:
        print("  %-18s M%-5s rev=%d  %s" % (r[0], r[2], r[3], (r[1] or "")[:38]))

    ex = conn.execute("SELECT quake_id,field,old_value,new_value,observed_at "
                      "FROM quake_revisions ORDER BY rev_id DESC LIMIT 5").fetchall()
    if ex:
        print("\nrecent revisions (what changed, and when we saw it):")
        for q, f, o, nv, ts in ex:
            print("  %-18s %-9s %s -> %s   (%s)" % (q, f, o, nv, ts))
    conn.close()
    return 0


def cmd_qc():
    """The library audits itself. Every failing check names its own fix."""
    if not DB.exists():
        print("no quakes.db yet - run a fetch first")
        return 1
    conn = connect()
    failures = []

    def check(name, ok, detail=""):
        print("  %-4s %s%s" % ("PASS" if ok else "FAIL", name,
                               ("  - " + detail) if detail else ""))
        if not ok:
            failures.append(name)

    print("== QC: quake-log ==")

    bad = conn.execute("SELECT COUNT(*) FROM quakes WHERE source IS NULL OR "
                       "first_fetched_at IS NULL OR last_fetched_at IS NULL").fetchone()[0]
    check("audit columns complete", bad == 0,
          "" if bad == 0 else "%d row(s) missing source/fetched_at - the fetcher is not "
                              "filling audit columns" % bad)

    mism = conn.execute("SELECT COUNT(*) FROM quakes "
                        "WHERE (magnitude IS NULL) != (mag_reliable=0)").fetchone()[0]
    check("reliability flag consistent", mism == 0,
          "" if mism == 0 else "%d row(s) where mag_reliable disagrees with magnitude IS NULL"
                               % mism)

    orphan = conn.execute("SELECT COUNT(*) FROM quake_revisions r LEFT JOIN quakes q "
                          "ON q.id=r.quake_id WHERE q.id IS NULL").fetchone()[0]
    check("no orphan revisions", orphan == 0,
          "" if orphan == 0 else "%d revision row(s) point at a missing event" % orphan)

    # revision_count counts revision MOMENTS, not rows: one re-grade can move
    # several fields at once, so compare against DISTINCT updated_after.
    bad_cnt = conn.execute(
        "SELECT COUNT(*) FROM (SELECT q.id, q.revision_count AS c, "
        "(SELECT COUNT(DISTINCT updated_after) FROM quake_revisions r WHERE r.quake_id=q.id) "
        "AS m FROM quakes q WHERE q.revision_count > 0) WHERE c != m").fetchone()[0]
    check("revision_count matches history", bad_cnt == 0,
          "" if bad_cnt == 0 else "%d event(s) whose counter disagrees with quake_revisions"
                                  % bad_cnt)

    live = conn.execute("SELECT substr(time_utc,1,10), COUNT(*), MAX(magnitude) FROM quakes "
                        "WHERE time_utc IS NOT NULL GROUP BY 1").fetchall()
    stored = {r[0]: (r[1], r[2]) for r in
              conn.execute("SELECT day,n_events,max_mag FROM daily_agg")}
    drift = [d for d, n_, mx in live if d in stored and stored[d] != (n_, mx)]
    missing = [d for d, _, _ in live if d not in stored]
    check("daily_agg matches source", not drift,
          "" if not drift else "%d day(s) drifted from quakes - run: agg --rebuild" % len(drift))
    check("daily_agg covers every day", not missing,
          "" if not missing else "%d day(s) never aggregated - run: agg" % len(missing))

    recent = [r[0] for r in conn.execute("SELECT status FROM fetch_log "
                                         "ORDER BY id DESC LIMIT 5")]
    bad_states = [s for s in recent if s in ("failed", "gap", "blocked")]
    check("recent fetches healthy", len(bad_states) < 3,
          "" if len(bad_states) < 3 else
          "%d of the last 5 fetches were %s - blocked=allowlist the domain, gap=fix the "
          "config, failed=retry next round" % (len(bad_states), "/".join(sorted(set(bad_states)))))

    total_log = conn.execute("SELECT COUNT(*) FROM fetch_log").fetchone()[0]
    check("ledger non-empty", total_log > 0,
          "" if total_log else "no fetch has ever been recorded - an unrecorded run cannot be "
                               "audited")

    conn.close()
    print("\nqc: %s" % ("all checks passed" if not failures
                        else "%d FAILED -> %s" % (len(failures), ", ".join(failures))))
    return 1 if failures else 0


def cmd_schedule():
    here = Path(__file__).resolve()
    print("Register a daily collection round (the USER runs this, not the agent):\n")
    print("Windows (keep the command ASCII-only on Chinese-locale systems):")
    print('  schtasks /create /tn "QuakeLog-Daily" /tr "py -X utf8 \\"%s\\" fetch" '
          "/sc daily /st 09:00" % here)
    print("\nmacOS / Linux (crontab -e):")
    print("  0 9 * * *  cd %s && python3 %s fetch" % (here.parent, here.name))
    print("\nNo-schedule option, always available:")
    print('  open your agent in this folder and say: "run a collection round"')
    print("\nBefore trusting any schedule, read references/pipeline-discipline.md:")
    print("  a scheduled job with no miss-and-catch-up will lose data the first time")
    print("  the machine sleeps through its window - and the ledger is how you notice.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Quake Log - ETL example library")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("fetch")
    p.add_argument("--window", choices=list(FEEDS), default="day")
    p = sub.add_parser("backfill")
    p.add_argument("--window", choices=list(FEEDS), default="month")
    p = sub.add_parser("agg")
    p.add_argument("--rebuild", action="store_true")
    sub.add_parser("stats")
    sub.add_parser("qc")
    sub.add_parser("schedule")
    args = ap.parse_args(argv)
    if args.cmd == "fetch":
        return cmd_fetch(args.window)
    if args.cmd == "backfill":
        return cmd_backfill(args.window)
    if args.cmd == "agg":
        return cmd_agg(args.rebuild)
    if args.cmd == "stats":
        return cmd_stats()
    if args.cmd == "qc":
        return cmd_qc()
    if args.cmd == "schedule":
        return cmd_schedule()
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
