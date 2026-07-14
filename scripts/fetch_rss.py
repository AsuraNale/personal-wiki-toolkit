#!/usr/bin/env python3
"""Generic feed fetcher: RSS 2.0 / Atom, plus arXiv API and Hacker News (Algolia) variants.

Part of personal-wiki-toolkit. Pure Python 3.9+ standard library, cross-platform.
Driven entirely by the library's config.json `sources[]` (see templates/config.example.json):

    { "kind": "rss",   "name": "some-blog",  "url": "https://example.com/feed.xml" }
    { "kind": "arxiv", "name": "arxiv-topic", "query": "\\"exact phrase\\"", "max_results": 5 }
    { "kind": "hn",    "name": "hn-topic",    "query": "keyword", "min_points": 50 }

Each source may optionally carry a "topic" label, attached to fetched items as a hint
for the judging agent.

Status discipline (see references/pipeline-discipline.md — a failed fetch is NOT an
empty result):
    ok         fetched and parsed, >=1 item
    empty      fetched and parsed fine, zero items (the source genuinely had nothing)
    gap        permanent-looking problem (HTTP 4xx, unparseable feed) — fix the config;
               retrying without a change won't help
    failed     transient problem (HTTP 5xx, timeout, network) — retry next round

Compliance: stores title + link + summary + date only. Never full article text.

Standalone usage (for testing sources; pipeline.py imports this module for real runs):
    python fetch_rss.py                     # fetch all sources in ./config.json
    python fetch_rss.py --source some-blog  # fetch one source by name
    python fetch_rss.py --config path/to/config.json
Prints fetch results as JSON to stdout; human-readable status lines go to stderr.
Always exits 0 unless the config itself is missing/invalid (exit 2).
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

TOOLKIT_VERSION = "0.1.2"
USER_AGENT = "personal-wiki-toolkit/%s (personal research; polite fetcher)" % TOOLKIT_VERSION
TIMEOUT = 20
SUMMARY_MAX = 300

VALID_KINDS = ("rss", "arxiv", "hn")

_ATOM = "{http://www.w3.org/2005/Atom}"
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


class FetchGap(Exception):
    """Permanent-looking fetch problem (4xx, broken feed). Fix config; do not blind-retry."""


class FetchFailed(Exception):
    """Transient fetch problem (5xx, timeout, network). Retry next round."""


# ---------------------------------------------------------------- HTTP


def _http_get(url):
    """GET url, classifying errors into FetchGap (permanent) vs FetchFailed (transient)."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        if e.code in (408, 429):  # request timeout / rate limit = transient, retry next round
            ra = e.headers.get("Retry-After") if getattr(e, "headers", None) else None
            raise FetchFailed("HTTP %d%s" % (e.code, (" (Retry-After: %s)" % ra) if ra else ""))
        if 400 <= e.code < 500:  # other 4xx = permanent (bad URL/query) — fixing config is required
            raise FetchGap("HTTP %d (check the source URL/query in config.json)" % e.code)
        raise FetchFailed("HTTP %d" % e.code)
    except Exception as e:  # URLError, timeout, ConnectionReset, ...
        raise FetchFailed("%s: %s" % (type(e).__name__, str(e)[:120]))


# ---------------------------------------------------------------- text helpers


def _clean_text(s):
    """Strip tags/CDATA noise and collapse whitespace."""
    s = _TAG_RE.sub(" ", s or "")
    return _WS_RE.sub(" ", s).strip()


def _summary(s):
    s = _clean_text(s)
    return s[:SUMMARY_MAX]


def _iso_date(raw):
    """Best-effort normalize a feed date to YYYY-MM-DD ('' if hopeless)."""
    raw = (raw or "").strip()
    if not raw:
        return ""
    # ISO-ish (Atom, arXiv): 2026-07-03T12:00:00Z
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", raw)
    if m:
        return m.group(1)
    # RFC 822 (RSS): Thu, 02 Jul 2026 08:00:00 GMT
    try:
        return parsedate_to_datetime(raw).strftime("%Y-%m-%d")
    except Exception:
        return ""


# ---------------------------------------------------------------- feed parsing


def parse_feed(data):
    """Parse RSS 2.0 or Atom bytes into a list of {title, url, summary, date} dicts.

    Raises FetchGap when the payload is not a parseable feed (permanent: wrong URL
    or a non-feed page — retrying won't fix it).
    """
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        raise FetchGap("not parseable XML (%s) — is this really a feed URL?" % str(e)[:80])

    items = []
    tag = root.tag.lower()
    if tag.endswith("rss") or tag.endswith("rdf"):  # RSS 2.0 (and best-effort RSS 1.0)
        for it in root.iter("item"):
            title = _clean_text(it.findtext("title", default=""))
            link = (it.findtext("link", default="") or "").strip()
            if not link:
                guid = it.find("guid")
                if guid is not None and (guid.get("isPermaLink", "true").lower() != "false"):
                    link = (guid.text or "").strip()
            summary = _summary(it.findtext("description", default=""))
            date = _iso_date(it.findtext("pubDate", default="") or it.findtext(
                "{http://purl.org/dc/elements/1.1/}date", default=""))
            if title and link:
                items.append({"title": title, "url": link, "summary": summary, "date": date})
    elif tag == _ATOM + "feed" or tag.endswith("feed"):  # Atom
        for e in root.iter(_ATOM + "entry"):
            title = _clean_text(e.findtext(_ATOM + "title", default=""))
            link = ""
            for ln in e.findall(_ATOM + "link"):
                if ln.get("rel", "alternate") == "alternate":
                    link = ln.get("href", "")
                    break
            if not link:  # fall back to any link / the id
                ln = e.find(_ATOM + "link")
                link = ln.get("href", "") if ln is not None else (e.findtext(_ATOM + "id", default="") or "")
            summary = _summary(e.findtext(_ATOM + "summary", default="") or
                               e.findtext(_ATOM + "content", default=""))
            date = _iso_date(e.findtext(_ATOM + "published", default="") or
                             e.findtext(_ATOM + "updated", default=""))
            if title and link:
                items.append({"title": title, "url": link.strip(), "summary": summary, "date": date})
    else:
        raise FetchGap("unrecognized feed root <%s> — expected <rss> or <feed>" % root.tag[:40])
    return items


# ---------------------------------------------------------------- source variants


def fetch_rss_source(src):
    url = src.get("url", "")
    if not url:
        raise FetchGap("rss source has no 'url' in config.json")
    return parse_feed(_http_get(url))


def fetch_arxiv(src):
    """arXiv API. Query is used as an exact phrase (quoted) unless the user already
    quoted it — unquoted multi-word all: queries get exploded into OR and drown you
    in off-topic papers sorted by recency (learned in production)."""
    query = (src.get("query") or "").strip()
    if not query:
        raise FetchGap("arxiv source has no 'query' in config.json")
    if not query.startswith('"'):
        query = '"%s"' % query
    n = int(src.get("max_results", 5))
    url = ("http://export.arxiv.org/api/query?search_query=all:%s"
           "&sortBy=submittedDate&sortOrder=descending&max_results=%d"
           % (urllib.parse.quote(query), n))
    items = parse_feed(_http_get(url))
    for it in items:
        it["summary"] = it["summary"][:SUMMARY_MAX]
    return items


def fetch_hn(src):
    """Hacker News via the public Algolia API; min_points filters noise (default 50).

    Points filtering is done CLIENT-SIDE (fetch, then drop hits below min_points).
    Algolia's server-side `numericFilters=points>=N` is fragile — a malformed value or
    encoding issue makes the endpoint 400 and the whole source silently returns nothing;
    client-side keeps a transient hiccup from masquerading as 'no stories'."""
    query = (src.get("query") or "").strip()
    if not query:
        raise FetchGap("hn source has no 'query' in config.json")
    pts = int(src.get("min_points", 50))
    # over-fetch a bit so the client-side points filter still yields ~max_results
    want = int(src.get("max_results", 10))
    url = ("https://hn.algolia.com/api/v1/search_by_date?query=%s&tags=story&hitsPerPage=%d"
           % (urllib.parse.quote(query), max(want * 4, 20)))
    try:
        data = json.loads(_http_get(url))
    except (json.JSONDecodeError, ValueError):
        raise FetchGap("HN Algolia returned non-JSON")
    items = []
    for h in data.get("hits", []):
        if (h.get("points") or 0) < pts:                 # client-side points filter
            continue
        title = (h.get("title") or "").strip()
        link = h.get("url") or ("https://news.ycombinator.com/item?id=%s" % h.get("objectID"))
        if not title:
            continue
        items.append({
            "title": title,
            "url": link,
            "summary": "HN story, %s points" % h.get("points", "?"),
            "date": (h.get("created_at") or "")[:10],
        })
        if len(items) >= want:
            break
    return items


_DISPATCH = {"rss": fetch_rss_source, "arxiv": fetch_arxiv, "hn": fetch_hn}


def fetch_source(src):
    """Fetch one config source. Never raises; returns a result dict:

        {"name", "kind", "status": ok|empty|gap|failed, "detail", "items": [...]}

    Items carry the source's optional "topic" label as a judging hint.
    """
    name = src.get("name") or src.get("url") or src.get("query") or "?"
    kind = (src.get("kind") or "").lower()
    result = {"name": name, "kind": kind, "status": "ok", "detail": "", "items": []}
    if kind not in _DISPATCH:
        result["status"] = "gap"
        result["detail"] = "unknown kind %r (valid: %s)" % (kind, "/".join(VALID_KINDS))
        return result
    try:
        items = _DISPATCH[kind](src)
    except FetchGap as e:
        result["status"], result["detail"] = "gap", str(e)
        return result
    except FetchFailed as e:
        result["status"], result["detail"] = "failed", str(e)
        return result
    except Exception as e:  # belt and braces: a bug in a parser must not kill the round
        result["status"], result["detail"] = "failed", "unexpected %s: %s" % (type(e).__name__, str(e)[:120])
        return result
    topic = src.get("topic")
    for it in items:
        it["source"] = name
        if topic:
            it["topic"] = topic
    result["items"] = items
    if not items:
        result["status"] = "empty"
        result["detail"] = "fetched fine; source had nothing (genuine empty, not a failure)"
    return result


def fetch_all(config):
    """Fetch every source in the config. One bad source never blocks the others."""
    return [fetch_source(src) for src in config.get("sources", [])]


# ---------------------------------------------------------------- CLI (testing aid)


def _load_config(path):
    p = Path(path)
    if not p.is_file():
        print("config not found: %s" % p, file=sys.stderr)
        raise SystemExit(2)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError) as e:
        print("config is not valid JSON: %s" % e, file=sys.stderr)
        raise SystemExit(2)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Fetch the library's configured sources (RSS/Atom, arXiv, HN) and "
                    "print results as JSON. Testing aid; real runs go through pipeline.py fetch.")
    ap.add_argument("--config", default="config.json", help="path to the library config.json")
    ap.add_argument("--source", help="fetch only the source with this name")
    args = ap.parse_args(argv)

    config = _load_config(args.config)
    sources = config.get("sources", [])
    if args.source:
        sources = [s for s in sources if s.get("name") == args.source]
        if not sources:
            print("no source named %r in config" % args.source, file=sys.stderr)
            raise SystemExit(2)

    results = [fetch_source(s) for s in sources]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    for r in results:
        print("[%s] %-10s source=%s kind=%s items=%d %s"
              % (now, r["status"].upper(), r["name"], r["kind"], len(r["items"]),
                 ("- " + r["detail"]) if r["detail"] else ""), file=sys.stderr)
    json.dump(results, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
