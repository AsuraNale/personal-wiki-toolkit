#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Example domain fetcher for a data/ETL-type library (personal-wiki-toolkit).

Pulls recent earthquakes from the USGS public feed (free, no auth) into a small
SQLite database. This is the worked example referenced by references/etl-guide.md:
a free public API -> a schema with an idempotent PK + audit columns + the
empty/failed/blocked distinction -> a queryable table.

Pure Python 3.9+ stdlib. Commands:
    python fetch_quakes.py fetch    # fetch the feed, upsert into quakes.db
    python fetch_quakes.py stats    # counts + last fetch status

Disciplines demonstrated (see references/etl-guide.md, pipeline-discipline.md):
- PK = USGS event id -> re-running is idempotent (INSERT OR IGNORE).
- audit columns: source, fetched_at.
- reliability flag: mag_reliable=0 when magnitude is null (keep + flag, don't drop).
- 5-way fetch status (ok/empty/gap/failed/blocked); a failed fetch is NOT an empty result,
  and a policy-blocked one is neither empty nor a config error.
"""
import json
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

FEED = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson"
DB = Path(__file__).resolve().parent / "quakes.db"
TIMEOUT = 20

SCHEMA = """
CREATE TABLE IF NOT EXISTS quakes (
    id           TEXT PRIMARY KEY,   -- USGS event id: idempotent upsert
    time_utc     TEXT,
    place        TEXT,
    magnitude    REAL,
    lon          REAL,
    lat          REAL,
    depth_km     REAL,
    source       TEXT,               -- audit: where it came from
    fetched_at   TEXT,               -- audit: when WE fetched it
    mag_reliable INTEGER DEFAULT 1   -- reliability flag: 0 if magnitude was null
);
CREATE TABLE IF NOT EXISTS fetch_log (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ts     TEXT,
    status TEXT,                     -- ok | empty | gap | failed | blocked
    items  INTEGER,
    detail TEXT
);
"""


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


# A proxy/egress refusal often surfaces BELOW HTTP: an https CONNECT refused by a sandbox
# proxy raises OSError("Tunnel connection failed: 403 Forbidden"), not an HTTPError. Classify
# at both layers, or one identical denial lands in two different states.
BLOCK_SIGNATURES = ("tunnel connection failed", "host_not_allowed", "proxy authentication",
                    "forbidden by proxy", "blocked by policy")


def http_get(url):
    """GET url; classify errors as blocked (policy refusal) vs gap (permanent) vs failed
    (transient). Three states because each needs a DIFFERENT fix: allowlist the domain /
    fix the config / retry next round."""
    req = urllib.request.Request(url, headers={"User-Agent": "pwt-etl-example/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code in (408, 429):
            raise RuntimeError("failed:HTTP %d (rate-limit/timeout, transient)" % e.code)
        if e.code in (403, 407):  # refused - egress policy / anti-bot / auth: ambiguous, so
            raise RuntimeError(   # do not assert a cause; give the troubleshooting priority
                "blocked:HTTP %d refused. In a cloud/sandbox, check the egress allowlist FIRST "
                "(most common); may also be anti-bot or auth. NOT evidence the feed is empty, "
                "and retrying will not help." % e.code)
        if 400 <= e.code < 500:
            raise RuntimeError("gap:HTTP %d (check the feed URL)" % e.code)
        raise RuntimeError("failed:HTTP %d" % e.code)
    except Exception as e:  # URLError, timeout, proxy CONNECT refusal, ...
        if any(s in str(e).lower() for s in BLOCK_SIGNATURES):
            raise RuntimeError("blocked:%s: %s - looks like an egress policy, not the feed; "
                               "check the allowlist. Retrying will not help."
                               % (type(e).__name__, str(e)[:80]))
        raise RuntimeError("failed:%s" % type(e).__name__)


def cmd_fetch():
    conn = sqlite3.connect(str(DB))
    conn.executescript(SCHEMA)
    status, detail, fresh = "ok", "", 0
    try:
        data = json.loads(http_get(FEED))
        feats = data.get("features", [])
        for f in feats:
            p = f.get("properties", {})
            g = (f.get("geometry", {}) or {}).get("coordinates", [None, None, None])
            mag = p.get("mag")
            t = datetime.fromtimestamp((p.get("time") or 0) / 1000, timezone.utc)
            cur = conn.execute(
                "INSERT OR IGNORE INTO quakes (id,time_utc,place,magnitude,lon,lat,depth_km,"
                "source,fetched_at,mag_reliable) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (f.get("id"), t.strftime("%Y-%m-%d %H:%M:%SZ"), p.get("place"), mag,
                 g[0], g[1], g[2], "USGS", now(), 0 if mag is None else 1))
            fresh += cur.rowcount
        if not feats:
            status, detail = "empty", "feed fetched fine, no events in window (genuine empty)"
    except RuntimeError as e:
        kind, _, msg = str(e).partition(":")
        status, detail = kind, msg  # gap / failed / blocked -- never counted as empty
    conn.execute("INSERT INTO fetch_log (ts,status,items,detail) VALUES (?,?,?,?)",
                 (now(), status, fresh, detail))
    conn.commit()
    conn.close()
    print("fetch: status=%s, %d new events%s" % (status, fresh, (" - " + detail) if detail else ""))
    return 0


def cmd_stats():
    if not DB.exists():
        print("no quakes.db yet - run: python fetch_quakes.py fetch")
        return 0
    conn = sqlite3.connect(str(DB))
    n = conn.execute("SELECT COUNT(*) FROM quakes").fetchone()[0]
    unrel = conn.execute("SELECT COUNT(*) FROM quakes WHERE mag_reliable=0").fetchone()[0]
    row = conn.execute("SELECT ts,status,items,detail FROM fetch_log ORDER BY id DESC LIMIT 1").fetchone()
    print("quakes: %d rows (%d with missing magnitude, flagged mag_reliable=0)" % (n, unrel))
    print("last fetch: %s" % ("%s status=%s items=%d %s" % row if row else "(never)"))
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    cmd = argv[0] if argv else "help"
    if cmd == "fetch":
        return cmd_fetch()
    if cmd == "stats":
        return cmd_stats()
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
