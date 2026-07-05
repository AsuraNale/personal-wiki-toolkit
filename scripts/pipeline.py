#!/usr/bin/env python3
"""Collection pipeline skeleton: fetch -> dedup -> Bronze ledger -> pending.json,
then apply the host agent's judgments back (Silver), promote/dismiss (Gold flow).

Part of personal-wiki-toolkit. Pure Python 3.9+ standard library, cross-platform.
Division of labor (non-negotiable, see SKILL.md): THIS SCRIPT never judges relevance.
The host agent reads _pipeline/pending.json, scores it per references/curation.md,
writes _pipeline/judgments.json, and calls `apply`. The agent never writes the
SQLite files directly.

Subcommands:
    fetch               fetch all config sources -> layer-1 dedup (url) -> Bronze
                        ledger -> regenerate _pipeline/pending.json (all unjudged)
    apply               consume _pipeline/judgments.json -> Silver + draft brief
                        (idempotent; same-day reruns UNION into one draft, never overwrite)
    promote <url>       mark a Silver item promoted (after its content reached Gold)
    dismiss <url> [reason...]   dismiss a Silver item with a reason (audited; never resurfaces)
    stats               tier counts, Silver aging, recent dismiss reasons, last fetch round
    selftest            environment + config + schema sanity check (clear exit codes)
    run                 fetch, then print what the agent should do next (judging is NOT automated)

Exit codes: 0 ok · 2 config/input problem · 3 environment problem.
Single-source fetch failures never fail the round (they are logged; exit stays 0).

Typical layout (created by scaffold; see setup/SCAFFOLD.md):
    <library-root>/config.json      <- single source of truth (scripts read ONLY this)
    <library-root>/intel.db         <- Bronze/Silver ledger (this script owns it)
    <library-root>/_pipeline/pending.json / judgments.json / silver/AUTO-*.md / logs/
Run from the library root, or from anywhere with the scripts/ dir in place — the
script locates the root by finding config.json (cwd first, then its parent dir).
"""

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import fetch_rss

TOOLKIT_VERSION = "0.1.0"
DEFAULT_THRESHOLD = 0.7
SILVER_STALE_DAYS = 14

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen (
    url         TEXT PRIMARY KEY,
    title       TEXT,
    source      TEXT,
    topic       TEXT,
    summary     TEXT,
    date        TEXT,
    first_seen  TEXT,
    relevance   REAL DEFAULT -1,
    status      TEXT DEFAULT 'new'
);
CREATE TABLE IF NOT EXISTS silver (
    url            TEXT PRIMARY KEY,
    title          TEXT,
    topic          TEXT,
    relevance      REAL,
    one_line       TEXT,
    dedup_key      TEXT,
    judged_at      TEXT,
    promoted       INTEGER DEFAULT 0,
    promoted_at    TEXT,
    dismissed      INTEGER DEFAULT 0,
    dismiss_reason TEXT,
    dismissed_at   TEXT
);
CREATE TABLE IF NOT EXISTS fetch_log (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ts     TEXT,
    source TEXT,
    kind   TEXT,
    status TEXT,
    items  INTEGER,
    detail TEXT
);
"""

# seen.status lifecycle:  new -> kept | low   (by apply);  kept -> dismissed (by human dismiss)


# ---------------------------------------------------------------- library root / config


def find_root():
    """Locate the library root = the directory holding config.json.
    Checks the working directory first, then the scripts/ parent."""
    for cand in (Path.cwd(), Path(__file__).resolve().parent.parent):
        if (cand / "config.json").is_file():
            return cand
    print("cannot find config.json (run from the library root, or keep this script "
          "in <library-root>/scripts/)", file=sys.stderr)
    raise SystemExit(2)


def load_config(root):
    try:
        return json.loads((root / "config.json").read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError) as e:
        print("config.json is not valid JSON: %s" % e, file=sys.stderr)
        raise SystemExit(2)


def pipeline_dir(root, config):
    return root / config.get("paths", {}).get("pipeline", "_pipeline")


def threshold_of(config):
    try:
        return float(config.get("thresholds", {}).get("keep", DEFAULT_THRESHOLD))
    except (TypeError, ValueError):
        return DEFAULT_THRESHOLD


# ---------------------------------------------------------------- infra


def now_ts():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def today():
    return datetime.now().strftime("%Y-%m-%d")


def local_day_utc_bounds():
    """The user's LOCAL 'today' expressed as a [start, end) range of UTC timestamp
    strings, plus the local date label.

    Ledger timestamps (`judged_at`) are stored in UTC. Filtering them by a local
    date prefix (`LIKE '<local-today>%'`) silently drops rows whose UTC timestamp
    has already rolled into the next calendar day — e.g. an apply run at 21:00 in a
    UTC-4 timezone writes `judged_at` at 01:00 UTC the next day, so the evening's
    work vanished from the draft. Aligning the filter to the local day's UTC window
    keeps the draft filename and its contents both on the user's 'today'.
    """
    # Derive each midnight's OWN offset via combine(date, 00:00).astimezone() rather than
    # reusing the current moment's offset — otherwise on a DST-transition day (the day is
    # 23 or 25h long) an evening run stamps midnight with the wrong offset, shifting the
    # window by 1h. Midnight itself is never inside the ambiguous 2am spring/fall hour, so
    # this is unambiguous even on transition days.
    local_today = datetime.now().astimezone().date()
    midnight = datetime.min.time()
    start_local = datetime.combine(local_today, midnight).astimezone()
    end_local = datetime.combine(local_today + timedelta(days=1), midnight).astimezone()
    fmt = "%Y-%m-%d %H:%M:%SZ"  # matches now_ts()
    return (start_local.astimezone(timezone.utc).strftime(fmt),
            end_local.astimezone(timezone.utc).strftime(fmt),
            local_today.strftime("%Y-%m-%d"))


def log(root, config, msg):
    line = "[%s] %s" % (now_ts(), msg)
    print(line)
    logdir = pipeline_dir(root, config) / "logs"
    try:
        logdir.mkdir(parents=True, exist_ok=True)
        with (logdir / "pipeline.log").open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass  # logging must never kill the pipeline


def connect(root):
    conn = sqlite3.connect(str(root / "intel.db"))
    conn.executescript(SCHEMA)
    return conn


def dedup_key(title):
    """Layer-2 dedup key: lowercase, keep alphanumerics + CJK, truncate.
    Layer 1 = url PK (seen), layer 2 = this key (silver candidates for the agent's
    verdict), layer 3 = note path (kb.db). See references/curation.md."""
    t = re.sub(r"[^0-9a-z一-鿿]+", "", (title or "").lower())
    return t[:80]


# ---------------------------------------------------------------- fetch


def write_pending(root, config, conn):
    """Regenerate pending.json from ALL unjudged Bronze rows (status='new').
    Rebuilding from the ledger (not from this round's catch) makes fetch a
    catch-up: candidates from interrupted earlier rounds reappear until judged."""
    rows = conn.execute(
        "SELECT url, title, source, topic, summary, date FROM seen "
        "WHERE status='new' ORDER BY first_seen DESC, url").fetchall()
    items = []
    for url, title, source, topic, summary, date in rows:
        item = {"url": url, "title": title, "source": source, "topic": topic,
                "summary": summary, "date": date}
        dup = conn.execute(
            "SELECT url FROM silver WHERE dedup_key=? AND dismissed=0 AND url<>? LIMIT 1",
            (dedup_key(title), url)).fetchone()
        if dup:  # layer-2 hint; the same-story-or-different-angle verdict is the agent's
            item["possible_duplicate_of"] = dup[0]
        items.append(item)
    pend = pipeline_dir(root, config) / "pending.json"
    pend.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": now_ts(),
        "toolkit_version": TOOLKIT_VERSION,
        "threshold": threshold_of(config),
        "how_to_judge": "Read references/curation.md. Score each item 0-1 on substance "
                        "(not keywords). Write _pipeline/judgments.json as a JSON array of "
                        "{url, relevance, one_line, topic}, then run: pipeline.py apply",
        "items": items,
    }
    pend.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(items)


def cmd_fetch(root, config):
    conn = connect(root)
    results = fetch_rss.fetch_all(config)
    fresh, ok_s, empty_s, gap_s, fail_s = 0, 0, 0, 0, 0
    for r in results:
        conn.execute("INSERT INTO fetch_log (ts, source, kind, status, items, detail) "
                     "VALUES (?,?,?,?,?,?)",
                     (now_ts(), r["name"], r["kind"], r["status"], len(r["items"]), r["detail"]))
        tag = {"ok": "OK", "empty": "EMPTY", "gap": "GAP", "failed": "FETCH-FAIL"}[r["status"]]
        log(root, config, "%-10s source=%s kind=%s items=%d%s"
            % (tag, r["name"], r["kind"], len(r["items"]),
               (" - " + r["detail"]) if r["detail"] else ""))
        if r["status"] == "ok":
            ok_s += 1
        elif r["status"] == "empty":
            empty_s += 1
        elif r["status"] == "gap":
            gap_s += 1
        else:
            fail_s += 1
        for it in r["items"]:
            cur = conn.execute(
                "INSERT OR IGNORE INTO seen (url, title, source, topic, summary, date, first_seen) "
                "VALUES (?,?,?,?,?,?,?)",
                (it["url"], it["title"], it.get("source", r["name"]), it.get("topic"),
                 it.get("summary", ""), it.get("date", ""), today()))
            fresh += cur.rowcount  # layer-1 dedup: url PK; already-seen rows insert nothing
    conn.commit()
    n_pending = write_pending(root, config, conn)
    conn.close()
    log(root, config, "fetch: %d new candidates (deduped); %d awaiting judgment in pending.json "
        "[sources: %d ok / %d empty / %d gap / %d failed]"
        % (fresh, n_pending, ok_s, empty_s, gap_s, fail_s))
    if fail_s:
        log(root, config, "note: %d source(s) FAILED transiently — their items were NOT "
            "fetched; they will be retried next round (a failed fetch is not an empty result)"
            % fail_s)
    return 0


# ---------------------------------------------------------------- apply (judgments -> Silver)


def write_draft_brief(root, config, conn):
    """(Re)generate today's Silver draft brief from the ledger.

    Regenerated from a query — the file is a VIEW of the DB, so multiple apply
    rounds on the same day UNION naturally instead of overwriting each other
    (an earlier per-round implementation lost the morning's items when an
    afternoon round rewrote the file).

    The day window is the user's LOCAL today mapped to a UTC range (see
    local_day_utc_bounds) so evening apply runs in UTC-behind timezones don't lose
    items to a date-prefix mismatch."""
    start_utc, end_utc, day = local_day_utc_bounds()
    rows = conn.execute(
        "SELECT url, title, topic, relevance, one_line FROM silver "
        "WHERE judged_at >= ? AND judged_at < ? AND promoted=0 AND dismissed=0 "
        "ORDER BY relevance DESC, url", (start_utc, end_utc)).fetchall()
    silver_dir = pipeline_dir(root, config) / "silver"
    silver_dir.mkdir(parents=True, exist_ok=True)
    path = silver_dir / ("AUTO-%s.md" % day)
    name = config.get("name", "library")
    lines = [
        "---",
        "title: Auto intel brief %s" % day,
        "date: %s" % day,
        "type: intel-brief-draft",
        "status: machine-filtered Silver draft - needs human curation",
        "---",
        "",
        "# Auto intel brief - %s - %s" % (name, day),
        "",
        "> Silver draft: fetched by pipeline, judged by the host agent, kept at >= %.2f. "
        "Promote items into Gold notes/briefs, or dismiss with a reason "
        "(pipeline.py promote/dismiss <url>)." % threshold_of(config),
        "",
    ]
    if not rows:
        lines.append("(no items passed the threshold today)")
    for i, (url, title, topic, rel, one_line) in enumerate(rows, 1):
        lines += [
            "### %d. %s  [%.2f]%s" % (i, title or url, rel or 0,
                                      ("  (%s)" % topic) if topic else ""),
            "- %s" % (one_line or ""),
            "- source: %s" % url,
            "",
        ]
    lines.append("---")
    lines.append("*generated by pipeline.py apply - regenerated (union) on every apply of the day*")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path, len(rows)


def cmd_apply(root, config):
    jpath = pipeline_dir(root, config) / "judgments.json"
    if not jpath.is_file():
        print("no judgments file at %s\nThe host agent must judge _pipeline/pending.json "
              "first (see references/curation.md), then run apply." % jpath, file=sys.stderr)
        return 2
    try:
        data = json.loads(jpath.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError) as e:
        print("judgments.json is not valid JSON: %s" % e, file=sys.stderr)
        return 2
    judgments = data.get("items") if isinstance(data, dict) else data
    if not isinstance(judgments, list):
        print("judgments.json must be a JSON array (or {\"items\": [...]}) of "
              "{url, relevance, one_line, topic}", file=sys.stderr)
        return 2

    thr = threshold_of(config)
    conn = connect(root)
    ts = now_ts()
    kept, low, skipped = 0, 0, 0
    for j in judgments:
        if not isinstance(j, dict) or not j.get("url"):
            skipped += 1
            continue
        url = j["url"]
        row = conn.execute("SELECT title, topic FROM seen WHERE url=?", (url,)).fetchone()
        if row is None:
            log(root, config, "apply: skipping judgment for unknown url (not in Bronze): %s" % url)
            skipped += 1
            continue
        try:
            rel = float(j.get("relevance", 0))
        except (TypeError, ValueError):
            rel = 0.0
        title = row[0]
        topic = j.get("topic") or row[1]
        # status is one-way once dismissed: a re-judged dismissed url must not flip back
        # to 'kept' in the Bronze ledger (the silver.dismissed flag already protects the
        # pipeline; this keeps the audit column honest too).
        conn.execute("UPDATE seen SET relevance=?, status=? WHERE url=? AND status<>'dismissed'",
                     (rel, "kept" if rel >= thr else "low", url))
        if rel >= thr:
            # INSERT OR IGNORE + UPDATE keeps existing promoted/dismissed flags intact,
            # so re-applying (or re-judging) never wipes a human decision. Idempotent.
            conn.execute("INSERT OR IGNORE INTO silver (url, promoted, dismissed) "
                         "VALUES (?, 0, 0)", (url,))
            conn.execute("UPDATE silver SET title=?, topic=?, relevance=?, one_line=?, "
                         "dedup_key=?, judged_at=? WHERE url=?",
                         (title, topic, rel, j.get("one_line", ""), dedup_key(title), ts, url))
            kept += 1
        else:
            low += 1
    conn.commit()
    path, n_draft = write_draft_brief(root, config, conn)
    n_pending = write_pending(root, config, conn)  # judged items leave pending.json
    conn.close()
    log(root, config, "apply: %d kept (>=%.2f) / %d low / %d skipped; draft brief -> %s "
        "(%d items, union of today); %d still pending"
        % (kept, thr, low, skipped, path.name, n_draft, n_pending))
    return 0


# ---------------------------------------------------------------- promote / dismiss


def cmd_promote(root, config, url):
    conn = connect(root)
    cur = conn.execute("UPDATE silver SET promoted=1, promoted_at=? WHERE url=?",
                       (now_ts(), url))
    conn.commit()
    found = cur.rowcount
    conn.close()
    if found:
        log(root, config, "promote: marked promoted (its content should now live in Gold "
            "notes/briefs, indexed via index_db.py build): %s" % url)
        return 0
    print("promote: url not found in Silver (run `stats`, or check pending.json): %s"
          % url, file=sys.stderr)
    return 2


def cmd_dismiss(root, config, url, reason):
    if not reason:
        # A dismissal without a reason is a lost training signal (references/medallion.md):
        # reasons are the owner's living definition of "not relevant here".
        print("warning: dismissing WITHOUT a reason - the ledger works better with one "
              "(reasons teach future judging rounds)", file=sys.stderr)
    conn = connect(root)
    cur = conn.execute("UPDATE silver SET dismissed=1, dismiss_reason=?, dismissed_at=? "
                       "WHERE url=?", (reason or None, now_ts(), url))
    conn.execute("UPDATE seen SET status='dismissed' WHERE url=?", (url,))
    conn.commit()
    found = cur.rowcount
    conn.close()
    if found:
        log(root, config, "dismiss: %s%s" % (url, (" - reason: " + reason) if reason else ""))
        return 0
    print("dismiss: url not found in Silver (run `stats`): %s" % url, file=sys.stderr)
    return 2


# ---------------------------------------------------------------- stats


def cmd_stats(root, config):
    conn = connect(root)
    print("== pipeline stats ==")
    print("library: %s   toolkit: %s (script) / %s (config)"
          % (config.get("name", "?"), TOOLKIT_VERSION, config.get("toolkit_version", "?")))

    print("\nBronze (seen) by status:")
    total = 0
    for status, c in conn.execute(
            "SELECT status, COUNT(*) FROM seen GROUP BY status ORDER BY COUNT(*) DESC"):
        print("  %6d  %s" % (c, status))
        total += c
    print("  %6d  total" % total)

    pend = conn.execute("SELECT COUNT(*) FROM silver WHERE promoted=0 AND dismissed=0").fetchone()[0]
    prom = conn.execute("SELECT COUNT(*) FROM silver WHERE promoted=1").fetchone()[0]
    dism = conn.execute("SELECT COUNT(*) FROM silver WHERE dismissed=1 AND promoted=0").fetchone()[0]
    print("\nSilver: %d awaiting curation / %d promoted / %d dismissed" % (pend, prom, dism))

    oldest = conn.execute("SELECT MIN(judged_at) FROM silver WHERE promoted=0 AND dismissed=0"
                          ).fetchone()[0]
    if oldest:
        try:
            age = (datetime.now(timezone.utc)
                   - datetime.strptime(oldest[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)).days
            print("Silver aging: oldest pending judged %s (%d days ago)%s"
                  % (oldest[:10], age,
                     "  <- curation is stalling, surface this to the user"
                     if age > SILVER_STALE_DAYS else ""))
        except ValueError:
            pass

    print("\nlast %d dismiss reasons (the owner's living definition of 'not relevant here'):" % 10)
    rows = conn.execute("SELECT dismissed_at, dismiss_reason, title FROM silver "
                        "WHERE dismissed=1 ORDER BY dismissed_at DESC LIMIT 10").fetchall()
    if not rows:
        print("  (none yet)")
    for at, reason, title in rows:
        print("  %s  %s  <- %s" % ((at or "")[:10], (reason or "(no reason)"), (title or "")[:50]))

    print("\nlast fetch round per source:")
    rows = conn.execute(
        "SELECT source, kind, status, items, detail, MAX(ts) FROM fetch_log "
        "GROUP BY source ORDER BY source").fetchall()
    if not rows:
        print("  (never fetched)")
    for source, kind, status, items, detail, ts in rows:
        print("  %-10s %-22s kind=%-6s items=%-4d %s  %s"
              % (status.upper(), source, kind, items, (ts or "")[:16],
                 ("- " + detail[:60]) if detail else ""))
    conn.close()
    return 0


# ---------------------------------------------------------------- selftest


def cmd_selftest(root_hint=None):
    """Environment + config + schema check. Exit 0 = all pass, 2 = config problem,
    3 = environment problem. Never touches existing data."""
    failures_env, failures_cfg = [], []

    def check(name, ok, detail=""):
        print("  %s %s%s" % ("PASS" if ok else "FAIL", name, (" - " + detail) if detail else ""))
        return ok

    print("== selftest ==")
    if not check("python >= 3.9", sys.version_info >= (3, 9),
                 "found %d.%d" % sys.version_info[:2]):
        failures_env.append("python")

    try:
        root = root_hint or find_root()
        check("library root found", True, str(root))
    except SystemExit:
        print("  FAIL library root - no config.json in cwd or script parent")
        print("selftest: FAIL (config)")
        return 2

    config = None
    try:
        config = json.loads((root / "config.json").read_text(encoding="utf-8"))
        check("config.json parses", True)
    except (json.JSONDecodeError, ValueError, OSError) as e:
        check("config.json parses", False, str(e)[:80])
        failures_cfg.append("parse")

    if config is not None:
        for key in ("name", "type", "sources", "paths"):
            if not check("config has %r" % key, key in config):
                failures_cfg.append(key)
        srcs = config.get("sources", [])
        if not check("sources is a non-empty list", isinstance(srcs, list) and len(srcs) > 0,
                     "%d source(s)" % (len(srcs) if isinstance(srcs, list) else 0)):
            failures_cfg.append("sources")
        else:
            for i, s in enumerate(srcs):
                kind = (s.get("kind") or "").lower()
                ok = kind in fetch_rss.VALID_KINDS
                need = {"rss": "url", "arxiv": "query", "hn": "query"}.get(kind)
                if ok and need:
                    ok = bool(s.get(need))
                if not check("source[%d] (%s) valid" % (i, s.get("name", "?")), ok,
                             "kind=%r needs %r" % (kind, need)):
                    failures_cfg.append("source[%d]" % i)
        thr = threshold_of(config)
        if not check("threshold in (0,1]", 0 < thr <= 1, "keep=%s" % thr):
            failures_cfg.append("threshold")

        try:
            pdir = pipeline_dir(root, config)
            (pdir / "logs").mkdir(parents=True, exist_ok=True)
            probe = pdir / ".selftest-probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            check("pipeline dir writable", True, str(pdir))
        except OSError as e:
            check("pipeline dir writable", False, str(e)[:80])
            failures_env.append("pipeline-dir")

        try:
            conn = connect(root)
            for table in ("seen", "silver", "fetch_log"):
                conn.execute("SELECT COUNT(*) FROM %s" % table)
            conn.close()
            check("intel.db schema ok", True)
        except sqlite3.Error as e:
            check("intel.db schema ok", False, str(e)[:80])
            failures_env.append("sqlite")

    if failures_cfg:
        print("selftest: FAIL (config) - fix config.json: %s" % ", ".join(failures_cfg))
        return 2
    if failures_env:
        print("selftest: FAIL (environment): %s" % ", ".join(failures_env))
        return 3
    print("selftest: all checks passed")
    return 0


# ---------------------------------------------------------------- run


def cmd_run(root, config):
    rc = cmd_fetch(root, config)
    pend = pipeline_dir(root, config) / "pending.json"
    print()
    print("Fetch done. Judging is deliberately NOT automated - it is the host agent's job:")
    print("  1. read references/curation.md (judging discipline)")
    print("  2. score the items in %s" % pend)
    print("  3. write _pipeline/judgments.json: [{\"url\",\"relevance\",\"one_line\",\"topic\"}]")
    print("  4. run: python scripts/pipeline.py apply")
    return rc


# ---------------------------------------------------------------- main


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Collection pipeline for a personal-wiki-toolkit library. "
                    "Deterministic steps only; relevance judging belongs to the host agent "
                    "(pending.json -> judgments.json interface).")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("fetch", help="fetch all sources, dedup, update Bronze, write pending.json")
    sub.add_parser("apply", help="apply _pipeline/judgments.json -> Silver + draft brief (idempotent)")
    p = sub.add_parser("promote", help="mark a Silver item promoted to Gold")
    p.add_argument("url")
    p = sub.add_parser("dismiss", help="dismiss a Silver item with a reason (audited)")
    p.add_argument("url")
    p.add_argument("reason", nargs="*", help="why this item is not relevant (recommended)")
    sub.add_parser("stats", help="tier counts, Silver aging, dismiss reasons, fetch health")
    sub.add_parser("selftest", help="check environment, config and db schema")
    sub.add_parser("run", help="fetch, then print the judging handoff instructions")
    args = ap.parse_args(argv)

    if not args.cmd:
        ap.print_help()
        return 0
    if args.cmd == "selftest":
        return cmd_selftest()

    root = find_root()
    config = load_config(root)
    if args.cmd == "fetch":
        return cmd_fetch(root, config)
    if args.cmd == "apply":
        return cmd_apply(root, config)
    if args.cmd == "promote":
        return cmd_promote(root, config, args.url)
    if args.cmd == "dismiss":
        return cmd_dismiss(root, config, args.url, " ".join(args.reason))
    if args.cmd == "stats":
        return cmd_stats(root, config)
    if args.cmd == "run":
        return cmd_run(root, config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
