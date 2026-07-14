#!/usr/bin/env python3
"""Behavioral tests for personal-wiki-toolkit scripts.

Pure standard library, cross-platform (Linux/macOS/Windows), no network:
external fetches are monkeypatched, and each test runs in a throwaway temp
library. Run:  python tests/test_pipeline.py   (exit 0 = all pass)

Covers the load-bearing invariants a self-feeding library depends on:
feed parsing, GAP-vs-FETCH-FAIL classification, HN client-side points filter,
source-health banner, url dedup + idempotency, same-day draft UNION,
dismissed-never-resurfaces, timezone/DST-correct draft window, and indexing.
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import fetch_rss  # noqa: E402
import pipeline  # noqa: E402
import index_db  # noqa: E402

PASS = [0]
FAIL = [0]
_TMP = Path(tempfile.mkdtemp(prefix="pwt-tests-"))
SANDBOX = _TMP / "kb"


def check(name, cond, detail=""):
    (PASS if cond else FAIL)[0] += 1
    print(("  PASS " if cond else "  FAIL ") + name + ((" - " + str(detail)) if detail and not cond else ""))


def fresh_sandbox():
    os.chdir(REPO)  # never rmtree the dir we are cwd'd into (Windows lock)
    if SANDBOX.exists():
        shutil.rmtree(SANDBOX, ignore_errors=True)
    for d in ("notes", "briefs", "inbox"):
        (SANDBOX / d).mkdir(parents=True, exist_ok=True)
    cfg = {
        "name": "sandbox-kb", "type": "intel", "language": "en",
        "topics": [{"key": "t1", "label": "Topic One", "keywords": ["kw"]}],
        "sources": [
            {"kind": "rss", "name": "feed-a", "url": "https://example.com/a.xml", "topic": "Topic One"},
            {"kind": "hn", "name": "hn-b", "query": "kw", "min_points": 50},
        ],
        "thresholds": {"keep": 0.7}, "cadence": "daily",
        "paths": {"notes": "notes", "briefs": "briefs", "inbox": "inbox", "pipeline": "_pipeline"},
        "toolkit_version": pipeline.TOOLKIT_VERSION,
    }
    (SANDBOX / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return cfg


def mock_results(*results):
    fetch_rss.fetch_all = lambda config: list(results)
    pipeline.fetch_rss = fetch_rss


def R(name, status, items=(), detail=""):
    return {"name": name, "kind": "rss", "status": status, "detail": detail, "items": list(items)}


def I(url, title, topic=None):
    d = {"url": url, "title": title, "summary": "s", "date": "2026-07-13", "source": "feed-a"}
    if topic:
        d["topic"] = topic
    return d


# ---------------------------------------------------------------- feed parsing


def test_feed_parsing():
    print("== feed parsing (RSS2 + Atom + garbage) ==")
    rss = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>c</title>
      <item><title>Hello  World</title><link>https://x.com/1</link>
        <description>&lt;p&gt;Some &lt;b&gt;html&lt;/b&gt; text&lt;/p&gt;</description>
        <pubDate>Thu, 02 Jul 2026 08:00:00 GMT</pubDate></item></channel></rss>"""
    items = fetch_rss.parse_feed(rss)
    check("RSS2: 1 item, title cleaned", len(items) == 1 and items[0]["title"] == "Hello World")
    check("RSS2: html stripped from summary", "html" in items[0]["summary"] and "<" not in items[0]["summary"])
    check("RSS2: RFC822 date -> ISO", items[0]["date"] == "2026-07-02")
    atom = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>f</title>
      <entry><title>Atom Entry</title><link rel="alternate" href="https://x.com/2"/>
        <summary>sum</summary><published>2026-07-01T10:00:00Z</published></entry></feed>"""
    items = fetch_rss.parse_feed(atom)
    check("Atom: alternate link + ISO date", len(items) == 1 and items[0]["url"] == "https://x.com/2" and items[0]["date"] == "2026-07-01")
    try:
        fetch_rss.parse_feed(b"<html><body>not a feed</body></html>")
        check("garbage -> FetchGap", False)
    except fetch_rss.FetchGap:
        check("garbage -> FetchGap (permanent, not a crash)", True)


# ---------------------------------------------------------------- status classification


def test_status_classification():
    print("== GAP vs FETCH-FAIL vs BLOCKED classification ==")
    real = urllib.request.urlopen

    def make(code):
        def _uo(req, timeout=None):
            raise urllib.error.HTTPError("http://x", code, "x", {}, None)
        return _uo
    try:
        # 403/407 = refused by policy/proxy/anti-bot -> blocked. NOT gap: a refusal is no
        # evidence the source is empty, and "fix your config URL" is the wrong advice.
        for code, want in ((404, "gap"), (403, "blocked"), (407, "blocked"),
                           (503, "failed"), (429, "failed"), (408, "failed")):
            urllib.request.urlopen = make(code)
            r = fetch_rss.fetch_source({"kind": "rss", "name": "s", "url": "http://x/%d" % code})
            check("HTTP %d -> status=%s" % (code, want), r["status"] == want, r)

        urllib.request.urlopen = make(403)
        d = fetch_rss.fetch_source({"kind": "rss", "name": "s", "url": "http://x/403"})["detail"]
        check("403 detail does not assert a cause + points at the allowlist first",
              "allowlist" in d.lower() and "not help" in d.lower(), d)
        check("403 detail denies it is evidence of emptiness", "NOT evidence" in d, d)

        # The key inconsistency: an https CONNECT refused by a sandbox proxy surfaces as an
        # OSError, not an HTTPError. Production saw one identical policy denial land in two
        # states (arxiv -> gap, Hacker News -> failed). Both must now be blocked.
        def _tunnel(req, timeout=None):
            raise OSError("Tunnel connection failed: 403 Forbidden")
        urllib.request.urlopen = _tunnel
        r = fetch_rss.fetch_source({"kind": "rss", "name": "s", "url": "https://x/t"})
        check("proxy CONNECT refusal (connection layer) -> blocked, not failed",
              r["status"] == "blocked", r)

        def _deny(req, timeout=None):
            raise OSError("host_not_allowed")
        urllib.request.urlopen = _deny
        check("egress deny-reason (host_not_allowed) -> blocked",
              fetch_rss.fetch_source({"kind": "rss", "name": "s", "url": "https://x/d"})["status"] == "blocked")

        def _to(req, timeout=None):
            raise TimeoutError("timed out")
        urllib.request.urlopen = _to
        check("timeout -> failed", fetch_rss.fetch_source({"kind": "rss", "name": "s", "url": "http://x/t"})["status"] == "failed")
    finally:
        urllib.request.urlopen = real
    real_get = fetch_rss._http_get
    fetch_rss._http_get = lambda url: b"""<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>"""
    check("parsed fine + 0 items -> empty (genuine)", fetch_rss.fetch_source({"kind": "rss", "name": "s", "url": "http://x/e"})["status"] == "empty")
    fetch_rss._http_get = real_get
    check("unknown kind -> gap (config problem)", fetch_rss.fetch_source({"kind": "bogus", "name": "s"})["status"] == "gap")


def test_hn_client_side_filter():
    print("== HN client-side points filter (no fragile server numericFilters) ==")
    real = fetch_rss._http_get
    cap = {}

    def fake(url):
        cap["url"] = url
        return json.dumps({"hits": [
            {"title": "high", "url": "https://h/1", "points": 120, "objectID": "1", "created_at": "2026-07-13T00:00:00Z"},
            {"title": "low", "url": "https://h/2", "points": 10, "objectID": "2", "created_at": "2026-07-13T00:00:00Z"},
        ]}).encode()
    fetch_rss._http_get = fake
    try:
        items = fetch_rss.fetch_hn({"kind": "hn", "name": "h", "query": "x", "min_points": 50})
    finally:
        fetch_rss._http_get = real
    check("no server-side numericFilters in HN URL (that write 400s and loses all)", "numericFilters" not in cap["url"])
    check("client-side filter keeps >=50, drops <50", len(items) == 1 and items[0]["title"] == "high")


# ---------------------------------------------------------------- source-health banner


def test_source_health_banner():
    print("== source-health banner: fetch failure != quiet day ==")
    cfg = fresh_sandbox()
    root = SANDBOX
    os.chdir(root)
    mock_results(R("a", "ok", [I("https://u/1", "T")]), R("b", "failed", detail="HTTP 503"))
    pipeline.cmd_fetch(root, cfg)
    conn = sqlite3.connect(str(root / "intel.db"))
    check("failed source -> WARNING banner names it", "WARNING" in pipeline.source_health(conn) and "b=failed" in pipeline.source_health(conn))
    (root / "_pipeline/judgments.json").write_text(json.dumps([{"url": "https://u/1", "relevance": 0.9, "one_line": "x"}]), encoding="utf-8")
    pipeline.cmd_apply(root, cfg)
    draft = next((root / "_pipeline/silver").glob("AUTO-*.md")).read_text(encoding="utf-8")
    check("brief header carries the health warning", "WARNING source health" in draft)
    mock_results(R("a", "ok", [I("https://u/2", "T2")]), R("b", "gap", detail="HTTP 400"))
    pipeline.cmd_fetch(root, cfg)
    check("gap!=0 also warns (HN 400 lands in gap bucket)", "WARNING" in pipeline.source_health(conn))

    # blocked must be called out SEPARATELY from failed: the fixes differ (allowlist vs retry).
    mock_results(R("a", "ok", [I("https://u/9", "T9")]), R("b", "blocked", detail="HTTP 403 refused"))
    check("fetch survives a blocked source (no KeyError on the status tag)",
          pipeline.cmd_fetch(root, cfg) == 0)
    ban = pipeline.source_health(conn)
    check("blocked source -> banner says BLOCKED and names it", "BLOCKED by policy" in ban and "b" in ban, ban)
    check("blocked banner gives the right action (allowlist), not 'retry'",
          "allowlist" in ban and "NOT help" in ban, ban)
    check("blocked is not lumped into the failed sentence",
          "b=failed" not in ban and "b=blocked" not in ban, ban)
    check("fetch_log records status=blocked", conn.execute(
        "SELECT COUNT(*) FROM fetch_log WHERE source='b' AND status='blocked'").fetchone()[0] == 1)
    mock_results(R("a", "ok", [I("https://u/3", "T3")]), R("b", "empty"))
    pipeline.cmd_fetch(root, cfg)
    check("all ok/empty -> quiet-day banner (no warning)", "all 2 sources ok" in pipeline.source_health(conn))
    conn.close()


# ---------------------------------------------------------------- pipeline flow


def test_pipeline_flow():
    print("== fetch/dedup/pending -> apply -> union -> promote/dismiss ==")
    cfg = fresh_sandbox()
    root = SANDBOX
    os.chdir(root)
    mock_results(R("feed-a", "ok", [I("https://u/1", "Alpha story"), I("https://u/2", "Beta story")]),
                 R("hn-b", "failed", detail="HTTP 503"))
    check("fetch exit 0 despite one FAILED source", pipeline.cmd_fetch(root, cfg) == 0)
    pend = json.loads((root / "_pipeline/pending.json").read_text(encoding="utf-8"))
    check("pending has 2 items", len(pend["items"]) == 2)
    conn = sqlite3.connect(str(root / "intel.db"))
    check("fetch_log has FAILED row for hn-b", conn.execute(
        "SELECT COUNT(*) FROM fetch_log WHERE source='hn-b' AND status='failed'").fetchone()[0] == 1)
    pipeline.cmd_fetch(root, cfg)
    check("re-fetch: seen still 2 (url dedup)", conn.execute("SELECT COUNT(*) FROM seen").fetchone()[0] == 2)

    (root / "_pipeline/judgments.json").write_text(json.dumps([
        {"url": "https://u/1", "relevance": 0.9, "one_line": "core", "topic": "Topic One"},
        {"url": "https://u/2", "relevance": 0.3, "one_line": "off"},
    ]), encoding="utf-8")
    check("apply exit 0", pipeline.cmd_apply(root, cfg) == 0)
    check("silver has 1 kept", conn.execute("SELECT COUNT(*) FROM silver").fetchone()[0] == 1)
    check("judged items left pending.json", len(json.loads((root / "_pipeline/pending.json").read_text(encoding="utf-8"))["items"]) == 0)
    drafts = list((root / "_pipeline/silver").glob("AUTO-*.md"))
    d1 = drafts[0].read_text(encoding="utf-8")
    check("draft contains kept item only", "Alpha story" in d1 and "Beta story" not in d1)
    pipeline.cmd_apply(root, cfg)
    check("re-apply idempotent: silver still 1", conn.execute("SELECT COUNT(*) FROM silver").fetchone()[0] == 1)

    mock_results(R("feed-a", "ok", [I("https://u/3", "Gamma story")]))
    pipeline.cmd_fetch(root, cfg)
    (root / "_pipeline/judgments.json").write_text(json.dumps([{"url": "https://u/3", "relevance": 0.8, "one_line": "r2", "topic": "Topic One"}]), encoding="utf-8")
    pipeline.cmd_apply(root, cfg)
    check("same-day round 2: draft is UNION (Alpha AND Gamma)",
          "Alpha story" in drafts[0].read_text(encoding="utf-8") and "Gamma story" in drafts[0].read_text(encoding="utf-8"))

    check("promote known url -> 0", pipeline.cmd_promote(root, cfg, "https://u/1") == 0)
    check("promote unknown url -> 2", pipeline.cmd_promote(root, cfg, "https://u/nope") == 2)
    check("dismiss with reason -> 0", pipeline.cmd_dismiss(root, cfg, "https://u/3", "too shallow") == 0)
    check("dismiss recorded reason", conn.execute("SELECT dismiss_reason FROM silver WHERE url='https://u/3'").fetchone()[0] == "too shallow")

    mock_results(R("feed-a", "ok", [I("https://u/3", "Gamma story")]))
    pipeline.cmd_fetch(root, cfg)
    pend = json.loads((root / "_pipeline/pending.json").read_text(encoding="utf-8"))
    check("dismissed item never re-enters pending", all(x["url"] != "https://u/3" for x in pend["items"]))

    mock_results(R("feed-a", "ok", [I("https://mirror/1", "Alpha  STORY")]))
    pipeline.cmd_fetch(root, cfg)
    hint = [x for x in json.loads((root / "_pipeline/pending.json").read_text(encoding="utf-8"))["items"] if x["url"] == "https://mirror/1"]
    check("layer-2 dedup hint on near-duplicate title", bool(hint) and hint[0].get("possible_duplicate_of") == "https://u/1")
    conn.close()


def test_dismissed_status_one_way():
    print("== seen.status one-way after dismiss ==")
    cfg = fresh_sandbox()
    root = SANDBOX
    os.chdir(root)
    mock_results(R("feed-a", "ok", [I("https://d/1", "Rejected")]))
    pipeline.cmd_fetch(root, cfg)
    (root / "_pipeline/judgments.json").write_text(json.dumps([{"url": "https://d/1", "relevance": 0.9, "one_line": "x"}]), encoding="utf-8")
    pipeline.cmd_apply(root, cfg)
    pipeline.cmd_dismiss(root, cfg, "https://d/1", "nope")
    conn = sqlite3.connect(str(root / "intel.db"))
    check("after dismiss seen.status='dismissed'", conn.execute("SELECT status FROM seen WHERE url='https://d/1'").fetchone()[0] == "dismissed")
    (root / "_pipeline/judgments.json").write_text(json.dumps([{"url": "https://d/1", "relevance": 0.95, "one_line": "y"}]), encoding="utf-8")
    pipeline.cmd_apply(root, cfg)
    check("re-judged high: status STAYS dismissed", conn.execute("SELECT status FROM seen WHERE url='https://d/1'").fetchone()[0] == "dismissed")
    conn.close()


# ---------------------------------------------------------------- draft day window (tz/DST)


def test_draft_day_window():
    print("== draft day window: local day mapped to UTC range ==")
    cfg = fresh_sandbox()
    root = SANDBOX
    os.chdir(root)
    conn = sqlite3.connect(str(root / "intel.db"))
    conn.executescript(pipeline.SCHEMA)
    conn.execute("INSERT INTO seen (url,title,status) VALUES ('https://z/1','Evening Item','kept')")
    conn.execute("INSERT INTO silver (url,title,topic,relevance,one_line,dedup_key,judged_at,promoted,dismissed) "
                 "VALUES ('https://z/1','Evening Item','T',0.9,'x','eveningitem','2026-07-03 01:00:00Z',0,0)")
    conn.commit()
    real = pipeline.local_day_utc_bounds
    pipeline.local_day_utc_bounds = lambda: ("2026-07-02 04:00:00Z", "2026-07-03 04:00:00Z", "2026-07-02")
    try:
        path, n = pipeline.write_draft_brief(root, cfg, conn)
    finally:
        pipeline.local_day_utc_bounds = real
    check("evening-UTC-next-day item in local-today draft", n == 1 and "Evening Item" in path.read_text(encoding="utf-8"))
    check("draft filename uses LOCAL today", path.name == "AUTO-2026-07-02.md")
    conn.close()
    # DST technique: midnight's own offset (combine) vs stale evening offset (replace)
    try:
        from zoneinfo import ZoneInfo
        ny = ZoneInfo("America/New_York")
        buggy = datetime(2026, 11, 1, 22, 48, tzinfo=timezone(timedelta(hours=-5))).replace(
            hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
        correct = datetime.combine(date(2026, 11, 1), datetime.min.time(), tzinfo=ny).astimezone(timezone.utc)
        check("DST fall-back: combine=04:00Z (right), fixed-offset replace=05:00Z (wrong)",
              correct.strftime("%H:%MZ") == "04:00Z" and buggy.strftime("%H:%MZ") == "05:00Z")
    except ImportError:
        check("zoneinfo available", False)


# ---------------------------------------------------------------- selftest + index


def test_selftest():
    print("== selftest exit codes ==")
    fresh_sandbox()
    os.chdir(SANDBOX)
    check("selftest on valid library -> 0", pipeline.cmd_selftest() == 0)
    bad = SANDBOX / "bad"
    bad.mkdir(exist_ok=True)
    (bad / "config.json").write_text('{"name":"x"}', encoding="utf-8")
    os.chdir(bad)
    check("selftest on incomplete config -> 2", pipeline.cmd_selftest() == 2)
    os.chdir(REPO)


def test_index():
    print("== index_db build + coverage ==")
    cfg = fresh_sandbox()
    root = SANDBOX
    os.chdir(root)
    (root / "notes/alpha.md").write_text(
        "---\ntitle: Alpha Note\ntags: [topic/one]\ndate: 2026-07-01\n---\n\nAbout alpha.\n\nLinks [[beta]].\n", encoding="utf-8")
    (root / "notes/beta.md").write_text("# Beta\n\nBody, links [alpha](alpha.md).\n", encoding="utf-8")
    (root / "notes/orphan.md").write_text("# Lonely\n\nNobody links here.\n", encoding="utf-8")
    (root / "briefs/brief1.md").write_text("---\ntitle: Brief 1\n---\n\nA brief.\n", encoding="utf-8")
    check("build -> 0", index_db.cmd_build(root, cfg) == 0)
    conn = sqlite3.connect(str(root / "kb.db"))
    check("4 notes indexed", conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 4)
    row = conn.execute("SELECT title, tags, outlinks, category FROM notes WHERE path LIKE '%alpha.md'").fetchone()
    check("frontmatter title+tags, wikilink outlink, category", row[0] == "Alpha Note" and "topic/one" in row[1] and "beta" in row[2] and row[3] == "notes")
    check("relative mdlink outlink", "alpha" in conn.execute("SELECT outlinks FROM notes WHERE path LIKE '%beta.md'").fetchone()[0])
    conn.close()
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        index_db.cmd_coverage(root, cfg, as_json=True)
    cov = json.loads(buf.getvalue())
    check("coverage --json + orphan detected", cov["total_notes"] == 4 and any("orphan.md" in o["path"] for o in cov["orphans"]) and not any("alpha.md" in o["path"] for o in cov["orphans"]))


# ---------------------------------------------------------------- manual add (provenance)


def test_manual_add():
    print("== pipeline.py add: manual Bronze entry, provenance kept ==")
    cfg = fresh_sandbox()
    root = SANDBOX
    os.chdir(root)

    class A:  # stand-in for the argparse namespace
        url = "https://example.com/found-by-hand"
        title = "Found by hand"
        source = "techcrunch"
        topic = "t"
        summary = "gist"
        date = "2026-07-14"

    check("add exit 0", pipeline.cmd_add(root, cfg, A) == 0)
    conn = sqlite3.connect(str(root / "intel.db"))
    row = conn.execute("SELECT source, status FROM seen WHERE url=?", (A.url,)).fetchone()
    check("lands in Bronze tagged manual:<source> (never masquerades as an auto fetch)",
          row is not None and row[0] == "manual:techcrunch", row)
    check("manual row is ordinary unjudged Bronze (status=new)", row[1] == "new")
    pend = json.loads((root / "_pipeline/pending.json").read_text(encoding="utf-8"))
    check("manual item surfaces in pending.json for judging",
          any(i["url"] == A.url for i in pend["items"]))
    check("re-add exit 0", pipeline.cmd_add(root, cfg, A) == 0)
    check("re-adding the same url is deduped by the ledger", conn.execute(
        "SELECT COUNT(*) FROM seen WHERE url=?", (A.url,)).fetchone()[0] == 1)

    class B:
        url = "notaurl"
        title, source, topic, summary, date = "x", "y", None, "", ""

    check("non-http url refused (exit 2)", pipeline.cmd_add(root, cfg, B) == 2)

    class C:
        url = "https://example.com/no-source-given"
        title, source, topic, summary, date = "t", "", None, "", ""

    pipeline.cmd_add(root, cfg, C)
    check("missing source still records provenance as manual:unspecified", conn.execute(
        "SELECT source FROM seen WHERE url=?", (C.url,)).fetchone()[0] == "manual:unspecified")
    conn.close()


def main():
    try:
        test_feed_parsing()
        test_status_classification()
        test_hn_client_side_filter()
        test_source_health_banner()
        test_manual_add()
        test_pipeline_flow()
        test_dismissed_status_one_way()
        test_draft_day_window()
        test_selftest()
        test_index()
    finally:
        os.chdir(REPO)
        shutil.rmtree(_TMP, ignore_errors=True)
    print("\n=== toolkit tests: %d pass / %d fail ===" % (PASS[0], FAIL[0]))
    return FAIL[0]


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
