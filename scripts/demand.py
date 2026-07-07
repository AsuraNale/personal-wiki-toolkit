#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Demand tracking: log out-of-library queries, surface a demand board.

Part of personal-wiki-toolkit. Pure Python 3.9+ standard library, cross-platform.
Standalone — does NOT modify pipeline.py. Implements the "demand-driven growth"
mechanism (see references/keeper.md): the keeper LABELS questions that needed
information the library doesn't hold; a daily self-check surfaces a quiet BOARD of
what the library keeps being blind on; the keeper PROPOSES adding a topic once
demand is clear, and the owner approves before anything is collected. Growth is
never silent.

Division of labor: this script TALLIES (counts, recency); the keeper JUDGES
(frequency + is-it-heating-up + how badly it missed) and proposes; the owner
approves. Raw count is only a soft prior, not the decision.

Subcommands:
    log "<category>" "<question>" [--source "<where the answer came from>"]
                        record one out-of-library query
    board [--json]      show the demand board: categories by count + recency,
                        flagging those past the propose threshold (config
                        demand_tracking.propose_threshold, default 3)

Writes a `demand` table into intel.db (alongside the collection ledger; a separate
table, so it never touches pipeline.py's tables). Run from the library root, or with
this script in <library-root>/scripts/. Exit codes: 0 ok · 2 config/input problem.
"""
import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_THRESHOLD = 3

SCHEMA = """
CREATE TABLE IF NOT EXISTS demand (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT,
    category    TEXT,
    query       TEXT,
    source_hint TEXT
);
"""


def find_root():
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


def now_ts():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def norm(cat):
    return " ".join((cat or "").lower().split())


def connect(root):
    conn = sqlite3.connect(str(root / "intel.db"))
    conn.executescript(SCHEMA)
    return conn


def threshold_of(config):
    try:
        return int(config.get("demand_tracking", {}).get("propose_threshold", DEFAULT_THRESHOLD))
    except (TypeError, ValueError):
        return DEFAULT_THRESHOLD


def cmd_log(root, config, category, query, source):
    if not (category or "").strip() or not (query or "").strip():
        print('usage: demand.py log "<category>" "<question>" [--source "..."]', file=sys.stderr)
        return 2
    conn = connect(root)
    conn.execute("INSERT INTO demand (ts, category, query, source_hint) VALUES (?,?,?,?)",
                 (now_ts(), norm(category), query.strip(), (source or "").strip() or None))
    conn.commit()
    conn.close()
    print("demand logged: [%s] %s" % (norm(category), query.strip()))
    return 0


def cmd_board(root, config, as_json):
    thr = threshold_of(config)
    conn = connect(root)
    rows = conn.execute(
        "SELECT category, COUNT(*), MIN(ts), MAX(ts) FROM demand GROUP BY category "
        "ORDER BY COUNT(*) DESC, MAX(ts) DESC").fetchall()
    now = datetime.now(timezone.utc)
    board = []
    for cat, cnt, first, last in rows:
        try:
            days = (now - datetime.strptime(last[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)).days
        except (TypeError, ValueError):
            days = None
        examples = [q for (q,) in conn.execute(
            "SELECT query FROM demand WHERE category=? ORDER BY ts DESC LIMIT 3", (cat,))]
        board.append({"category": cat, "count": cnt, "first_seen": first, "last_seen": last,
                      "days_since_last": days, "over_threshold": cnt > thr, "examples": examples})
    conn.close()

    if as_json:
        print(json.dumps({"propose_threshold": thr, "board": board}, ensure_ascii=False, indent=2))
        return 0

    print("== demand board ==  (soft propose threshold: > %d occurrences)" % thr)
    if not board:
        print("  (nothing logged yet)")
        return 0
    for b in board:
        age = ("%dd ago" % b["days_since_last"]) if b["days_since_last"] is not None else "?"
        flag = "  <- PROPOSE? (past threshold — you judge heat + how badly it missed)" if b["over_threshold"] else ""
        print("  %3d  %-24s  last %s%s" % (b["count"], b["category"][:24], age, flag))
        if b["examples"]:
            print("       e.g. %s" % " | ".join(b["examples"][:2]))
    print("\nThis board TALLIES demand; YOU (the keeper) judge whether to propose — weigh "
          "frequency + is-it-heating-up + how badly it missed, not raw count alone. Growth "
          "needs the owner's approval (add the topic to config.json, then start collecting).")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Demand tracking for a personal-wiki-toolkit library: log "
                    "out-of-library queries, surface a demand board. Tallies only — "
                    "the keeper judges and proposes; the owner approves growth.")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("log", help="record one out-of-library query")
    p.add_argument("category")
    p.add_argument("query")
    p.add_argument("--source", default="", help="where the answer came from / a suggested source")
    p = sub.add_parser("board", help="show the demand board (counts + recency, past-threshold flags)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    if not args.cmd:
        ap.print_help()
        return 0
    root = find_root()
    config = load_config(root)
    if args.cmd == "log":
        return cmd_log(root, config, args.category, args.query, args.source)
    if args.cmd == "board":
        return cmd_board(root, config, args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
