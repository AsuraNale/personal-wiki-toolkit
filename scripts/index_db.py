#!/usr/bin/env python3
"""Markdown -> SQLite indexer for a personal-wiki-toolkit library.

Part of personal-wiki-toolkit. Pure Python 3.9+ standard library, cross-platform.
Scans the library's Markdown content dirs (from config.json `paths`: notes, briefs,
inbox) and builds kb.db - the machine-queryable side of the dual-layer storage
(Markdown stays the human-readable truth; the index is derived and rebuildable).

Subcommands:
    build               scan -> (re)build the kb.db notes table
    coverage [--json]   per-category counts + date ranges, top tags, orphan notes

The index is a VIEW of the files: `build` fully regenerates it, so it is always
safe to re-run (idempotent). Nothing here ever modifies the Markdown files.

Usage:
    python scripts/index_db.py build
    python scripts/index_db.py coverage
    python scripts/index_db.py coverage --json
Run from the library root, or from anywhere with the scripts/ dir in place - the
script locates the root by finding config.json (cwd first, then its parent dir).
"""

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

TOOLKIT_VERSION = "0.1.1"
SKIP_DIRS = {".git", ".obsidian", ".trash", "node_modules", "__pycache__"}

WIKILINK = re.compile(r"\[\[([^\]\|#]+)(?:#[^\]\|]*)?(?:\|[^\]]+)?\]\]")
MDLINK = re.compile(r"\]\(([^)\s]+\.md)\)")
H1 = re.compile(r"^#\s+(.+?)\s*$")
FM_DELIM = "---"

SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    path     TEXT PRIMARY KEY,
    title    TEXT,
    category TEXT,
    tags     TEXT,
    created  TEXT,
    updated  TEXT,
    outlinks TEXT,
    summary  TEXT,
    words    INTEGER
);
"""


# ---------------------------------------------------------------- root / config


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


def content_dirs(root, config):
    """The Markdown dirs to index: paths.notes / paths.briefs / paths.inbox that exist.
    The pipeline dir is deliberately NOT indexed - Silver drafts are not Gold knowledge
    and must not surface in library search (see references/medallion.md)."""
    paths = config.get("paths", {})
    out = []
    for key in ("notes", "briefs", "inbox"):
        d = root / paths.get(key, key)
        if d.is_dir():
            out.append((key, d))
    return out


# ---------------------------------------------------------------- markdown parsing


def parse_frontmatter(text):
    """Minimal YAML-frontmatter reader (title/tags/date/...) - handwritten on purpose,
    no third-party YAML dependency. Supports `key: value`, inline lists [a, b] and
    block lists. Returns (meta dict, body start line index)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != FM_DELIM:
        return {}, 0
    meta, i, cur_key = {}, 1, None
    while i < len(lines):
        line = lines[i]
        if line.strip() == FM_DELIM:
            i += 1
            break
        m_item = re.match(r"^\s*-\s+(.*)$", line)
        if m_item and cur_key:
            meta.setdefault(cur_key, [])
            if isinstance(meta[cur_key], list):
                meta[cur_key].append(m_item.group(1).strip().strip("\"'"))
            i += 1
            continue
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if m:
            key, val = m.group(1).strip().lower(), m.group(2).strip()
            cur_key = key
            if val == "":
                meta[key] = []
            elif val.startswith("[") and val.endswith("]"):
                meta[key] = [x.strip().strip("\"'") for x in val[1:-1].split(",") if x.strip()]
                cur_key = None
            else:
                meta[key] = val.strip().strip("\"'")
                cur_key = None
        i += 1
    return meta, i


def first_paragraph(lines, start, limit=240):
    """First body paragraph as a plain-text summary (markdown markers stripped)."""
    buf = []
    for line in lines[start:]:
        s = line.strip()
        if not s:
            if buf:
                break
            continue
        if s.startswith("#"):
            continue
        s = re.sub(r"^>+\s*", "", s)
        s = re.sub(r"^[-*]\s+", "", s)
        s = re.sub(r"[*_`]", "", s)
        if s:
            buf.append(s)
        if sum(len(x) for x in buf) > limit:
            break
    return " ".join(buf)[:limit]


def derive_title(meta, lines, path):
    t = meta.get("title")
    if isinstance(t, list):
        t = t[0] if t else None
    if t:
        return t
    for line in lines:
        m = H1.match(line)
        if m:
            return m.group(1)
    return path.stem


def derive_tags(meta):
    tags = meta.get("tags")
    if isinstance(tags, str):
        tags = [tags]
    if not isinstance(tags, list):
        return ""
    return ", ".join(str(t).strip() for t in tags if str(t).strip())


def extract_outlinks(text):
    """Wiki-links [[Target]] and relative markdown links (file.md), deduped, sorted."""
    links = set()
    for m in WIKILINK.findall(text):
        links.add(m.strip())
    for m in MDLINK.findall(text):
        if not m.startswith(("http://", "https://")):
            links.add(Path(m).stem)
    return sorted(links)


# ---------------------------------------------------------------- build


def scan_note(full, category, root):
    try:
        text = full.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        print("  ! skipping %s: %s" % (full, e), file=sys.stderr)
        return None
    meta, body_start = parse_frontmatter(text)
    lines = text.splitlines()
    created = meta.get("date") or meta.get("created") or ""
    if isinstance(created, list):
        created = created[0] if created else ""
    mtime = datetime.fromtimestamp(full.stat().st_mtime, timezone.utc)
    relpath = full.relative_to(root).as_posix()  # forward slashes on every platform
    return (
        relpath,
        derive_title(meta, lines, full),
        category,
        derive_tags(meta),
        str(created),
        mtime.strftime("%Y-%m-%d"),
        ", ".join(extract_outlinks(text)),
        first_paragraph(lines, body_start),
        len(text),
    )


def cmd_build(root, config):
    dirs = content_dirs(root, config)
    if not dirs:
        print("no content dirs found (config paths: notes/briefs/inbox) - nothing to index",
              file=sys.stderr)
        return 2
    conn = sqlite3.connect(str(root / "kb.db"))
    conn.execute("DROP TABLE IF EXISTS notes")  # full rebuild: the index is derived state
    conn.executescript(SCHEMA)
    n = 0
    for category, d in dirs:
        for full in sorted(d.rglob("*.md")):
            if any(part in SKIP_DIRS for part in full.parts):
                continue
            row = scan_note(full, category, root)
            if row:
                conn.execute("INSERT OR REPLACE INTO notes VALUES (?,?,?,?,?,?,?,?,?)", row)
                n += 1
    conn.commit()
    conn.close()
    print("indexed %d markdown notes -> kb.db  (categories: %s)"
          % (n, ", ".join(k for k, _ in dirs)))
    return 0


# ---------------------------------------------------------------- coverage


def cmd_coverage(root, config, as_json):
    db = root / "kb.db"
    if not db.is_file():
        print("kb.db not found - run `index_db.py build` first", file=sys.stderr)
        return 2
    conn = sqlite3.connect(str(db))

    cats = []
    for category, count, oldest, newest in conn.execute(
            "SELECT category, COUNT(*), MIN(updated), MAX(updated) FROM notes "
            "GROUP BY category ORDER BY COUNT(*) DESC"):
        cats.append({"category": category, "count": count,
                     "oldest_update": oldest, "newest_update": newest})

    tag_counter = {}
    for (tags,) in conn.execute("SELECT tags FROM notes"):
        for t in (tags or "").split(","):
            t = t.strip()
            if t:
                tag_counter[t] = tag_counter.get(t, 0) + 1
    top_tags = sorted(tag_counter.items(), key=lambda x: -x[1])[:20]

    # Orphans: notes nothing links to (matched by filename stem or path). They are not
    # wrong per se, but a growing orphan pile means knowledge is being written and
    # never woven in - worth surfacing to the user.
    linked = set()
    for (outlinks,) in conn.execute("SELECT outlinks FROM notes"):
        for l in (outlinks or "").split(","):
            l = l.strip()
            if l:
                linked.add(l.lower())
    orphans = []
    for path, title in conn.execute("SELECT path, title FROM notes ORDER BY path"):
        stem = Path(path).stem.lower()
        if stem not in linked and (title or "").lower() not in linked:
            orphans.append({"path": path, "title": title})
    conn.close()

    total = sum(c["count"] for c in cats)
    payload = {
        "toolkit_version": TOOLKIT_VERSION,
        "total_notes": total,
        "categories": cats,
        "top_tags": [{"tag": t, "count": c} for t, c in top_tags],
        "orphan_count": len(orphans),
        "orphans": orphans[:50],
    }
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print("== coverage ==  (%d notes)" % total)
    print("\nby category:")
    for c in cats:
        print("  %5d  %-8s updated %s .. %s"
              % (c["count"], c["category"], c["oldest_update"] or "-", c["newest_update"] or "-"))
    print("\ntop tags:")
    if not top_tags:
        print("  (none)")
    for t, c in top_tags:
        print("  %5d  %s" % (c, t))
    print("\norphans (no other note links to them): %d" % len(orphans))
    for o in orphans[:15]:
        print("  %s  [%s]" % (o["title"], o["path"]))
    if len(orphans) > 15:
        print("  ... and %d more (use --json for the full list)" % (len(orphans) - 15))
    return 0


# ---------------------------------------------------------------- main


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Markdown -> SQLite indexer (kb.db). The index is derived state: "
                    "rebuild any time; never edits your Markdown.")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("build", help="scan content dirs and (re)build the kb.db index")
    p = sub.add_parser("coverage", help="per-category counts, date ranges, top tags, orphans")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    if not args.cmd:
        ap.print_help()
        return 0
    root = find_root()
    config = load_config(root)
    if args.cmd == "build":
        return cmd_build(root, config)
    if args.cmd == "coverage":
        return cmd_coverage(root, config, args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
