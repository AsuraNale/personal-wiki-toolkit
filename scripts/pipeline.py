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
    evidence            read-only evidence block to PASTE into a QC report or handover
                        (retyping these numbers is how a real report got three wrong)
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

TOOLKIT_VERSION = "0.1.5"
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


VALID_TYPES = ("intel", "import", "data")


def library_shapes(config):
    """Return (shapes, problem, inferred_from) for config['type'].

    `type` names the library's SHAPE, which decides which tier model applies
    (see references/medallion.md). Accepts a string, or a list for a composite
    library — the format allows arrays now, before any library exists that needs
    one, because there is no config-migration mechanism: a format widened later
    cannot reach libraries already on disk.

    Two failure kinds, kept apart on purpose:
      problem       -> the value is WRONG (a typo silently mis-shapes the library)
      inferred_from -> the key is ABSENT (older libraries predate it); we infer
                       and say so, rather than breaking them
    Exactly one of the two is ever non-empty.
    """
    if "type" not in config:
        # Absent. Presence of toolkit-managed sources is the signal: data libraries
        # write their own fetchers and do not use config sources at all.
        srcs = config.get("sources")
        if isinstance(srcs, list) and srcs:
            return ["intel"], "", "it has config sources"
        return ["data"], "", "it has no config sources"
    raw = config["type"]
    if raw is None:
        # Present but null — that is a written value, not an omission, so it is
        # reported rather than inferred around.
        return ["intel"], "type is null; expected one of %s" % "/".join(VALID_TYPES), ""
    vals = raw if isinstance(raw, list) else [raw]
    if not vals:
        return ["intel"], "type is an empty list; expected one of %s" % "/".join(VALID_TYPES), ""
    bad = [v for v in vals if not isinstance(v, str) or v.lower() not in VALID_TYPES]
    if bad:
        return ([v for v in vals if isinstance(v, str)] or ["intel"],
                "type %r is not one of %s (a typo here silently mis-shapes the whole library)"
                % (bad[0], "/".join(VALID_TYPES)), "")
    return [v.lower() for v in vals], "", ""


# ---------------------------------------------------------------- the intake record

# R1/R2 — until now the Intake gate was held up by prose alone. SCAFFOLD.md's exit
# checklist asks that "nothing in $intake is agent-inferred", and that sentence stays
# true when the whole field is missing: a real library shipped with `keeper` never
# recorded and never discussed, and the check passed on the way out.
INTAKE_KEY = "$intake"
UNRECORDED_KEY = "$unrecorded"
VALID_DECIDED_BY = ("user-typed", "user-selected", "default-accepted")
FORBIDDEN_DECIDED_BY = "agent-inferred"
# These three have no sensible default, so `default-accepted` on them means it was
# really inferred and nobody was told (setup/INTERVIEW.md § Intake).
NO_DEFAULT_KEYS = ("domain", "topics", "sources")

# Which decisions each shape has to have on record. Kept HERE, in the one file that
# travels with a library, and kept honest by a toolkit-side test that asserts this
# constant, templates/config.example.json and setup/INTERVIEW.md's json block all
# agree — when you cannot have a single source, make the duplication checkable.
REQUIRED_INTAKE = {
    "intel":  ("shape", "domain", "topics", "sources", "cadence", "threshold", "keeper"),
    "import": ("shape", "domain", "categories", "mode", "keeper"),
    "data":   ("shape", "domain", "sources", "cadence", "keeper"),
}


def required_intake_keys(shapes):
    """The union of the required decisions across every shape this library declares.

    Union rather than primary-only: a composite library really did make both sets of
    decisions. It also fails in the safe direction — naming an extra shape can only
    ADD requirements, so the list can never be shortened by editing `type`.
    """
    keys = []
    for s in shapes:
        for k in REQUIRED_INTAKE.get(s, ()):
            if k not in keys:
                keys.append(k)
    return keys


def intake_state(config, shapes):
    """(state, problems, note) for config['$intake'].

    state: "ok" | "unrecorded" | "absent" | "bad"

    ⛔ **This reads the VALUE of each `decided_by` field. It must never text-match the
    config as a whole.** templates/config.example.json explains the rule in a
    `$comment` that contains the string "agent-inferred" verbatim, and scaffold copies
    that template into every library — so a substring check over the file would fail
    every correctly-built library there is. That is the same mistake in a new costume:
    a check that catches the sentence forbidding the thing. Ask it out loud before
    writing any check here: *would this flag the words that state the rule?*

    Grading note: "absent" is a FAILURE, not a lenient legacy pass. Warning on absence
    and failing on a partial record would mean writing nothing was safer than writing
    six fields of seven — and an old library is indistinguishable on disk from a new
    one whose agent skipped the gate, which is the case this check exists for.
    """
    intake = config.get(INTAKE_KEY)
    if intake is None:
        return "absent", [], ""
    if not isinstance(intake, dict):
        return "bad", ["%s is not an object" % INTAKE_KEY], ""

    problems = []
    # Validate every record that IS present, legacy or not: an invented provenance is
    # a false claim whether or not the library predates the record-keeping.
    for key, rec in sorted(intake.items()):
        if key.startswith("$"):
            continue
        if not isinstance(rec, dict) or "value" not in rec or "decided_by" not in rec:
            problems.append("%s is not a {value, decided_by} record" % key)
            continue
        by = rec.get("decided_by")
        if by == FORBIDDEN_DECIDED_BY:
            problems.append("%s is %r — decided quietly, so they never knew it was a "
                            "question. Go back and ask." % (key, FORBIDDEN_DECIDED_BY))
        elif by not in VALID_DECIDED_BY:
            problems.append("%s has decided_by=%r; expected one of %s"
                            % (key, by, " / ".join(VALID_DECIDED_BY)))
        elif by == "default-accepted" and key in NO_DEFAULT_KEYS:
            problems.append("%s is 'default-accepted', but it has no sensible default — "
                            "a default there means it was really inferred" % key)

    unrecorded = intake.get(UNRECORDED_KEY)
    if unrecorded is not None:
        if not (isinstance(unrecorded, str) and unrecorded.strip()):
            problems.append("%s must carry a one-line reason — an empty acknowledgement "
                            "says nothing" % UNRECORDED_KEY)
        return ("bad" if problems else "unrecorded"), problems, (unrecorded or "").strip()

    missing = [k for k in required_intake_keys(shapes) if k not in intake]
    if missing:
        problems.append("no record of %s (required for shape %s)"
                        % (", ".join(missing), "+".join(shapes)))
    return ("bad" if problems else "ok"), problems, ""


def unrecorded_hint():
    """The repair path, printed with the failure so it can be pasted rather than invented.

    A guardrail whose only route back to green is fabricating a `decided_by` would be
    demanding the exact dishonesty the record exists to prevent. So the escape is an
    admission, not a claim — and it stays visible on every later run.
    """
    return ('record the decisions in config.json, or — if this library was built before '
            'the intake record existed — say so on the record:\n'
            '           "%s": { "%s": "built before the intake record; provenance unknown" }\n'
            '         Never invent a decided_by you cannot stand behind.' % (INTAKE_KEY, UNRECORDED_KEY))


# ---------------------------------------------------------------- build provenance

BUILT_WITH_KEY = "built_with"


def built_with_state(config):
    """(state, problems) for config['built_with'].  state: "ok" | "absent" | "bad"

    `toolkit_version` records the version of the TEMPLATE this config was copied from.
    That is not the version of the spec the building agent actually followed: one real
    library carries 0.1.4 in its config while the session that built it was running a
    locally cached 0.1.3 skill — and nothing on disk showed the difference, so every
    case analysis done by version files that library under the wrong release.

    The load-bearing field here is therefore not a version but `skill_source`. Two
    version numbers look identical whether or not they are true; a source does not.
    "a local cached copy" is self-incriminating in exactly the case that matters, and
    "I no longer know which version that was" is a more useful record than a confident
    wrong number.

    So only `scripts_version` is checked, because it is the only one a machine can
    check: it must match the constant in the pipeline.py that is actually running.
    `skill_version` is kept as a declared value and never treated as evidence.
    """
    bw = config.get(BUILT_WITH_KEY)
    if bw is None:
        return "absent", []
    if not isinstance(bw, dict):
        return "bad", ["%s is not an object" % BUILT_WITH_KEY]
    problems = []
    src = bw.get("skill_source")
    if not (isinstance(src, str) and src.strip()):
        problems.append("%s.skill_source is missing — where the skill was READ from "
                        "(a repo URL, or a local cache path) is the one part of this "
                        "record that shows when it is wrong" % BUILT_WITH_KEY)
    sv = bw.get("scripts_version")
    if not (isinstance(sv, str) and sv.strip()):
        problems.append("%s.scripts_version is missing — paste the version these scripts "
                        "report, do not type it from memory" % BUILT_WITH_KEY)
    elif sv.strip() != TOOLKIT_VERSION:
        problems.append("%s.scripts_version is %r but the scripts in this library are %r "
                        "— either they were re-copied without updating config, or the "
                        "value was typed rather than pasted"
                        % (BUILT_WITH_KEY, sv.strip(), TOOLKIT_VERSION))
    return ("bad" if problems else "ok"), problems


# The injection red line is mandatory in every library's own memory file (SKILL.md
# rule 8). Libraries are written in the OWNER's language, so this cannot be checked by
# matching English prose — a Chinese library writes "不是指令" and would fail a literal
# match. New libraries carry a language-independent marker; older ones are matched on a
# small multilingual signal set so they are not broken by a check added after the fact.
INJECTION_MARK = "pwt:injection-rule"
INJECTION_HINTS = (
    "not the owner's instructions", "are not instructions", "not your instructions",
    "data, not instructions", "not instructions",
    "不是指令", "不是给你的指令", "非指令",
)
MEMORY_FILES = ("CLAUDE.md", "AGENTS.md")


def memory_files(root):
    """The library's own agent-memory files that actually exist."""
    return [root / n for n in MEMORY_FILES if (root / n).is_file()]


def injection_rule_state(root):
    """(state, detail) for the injection red line in this library's memory files.

    state: "marked" | "unmarked" | "missing" | "no-memory-file"
    """
    files = memory_files(root)
    if not files:
        return "no-memory-file", "no CLAUDE.md / AGENTS.md in the library root"
    marked, hinted, bare = [], [], []
    for f in files:
        try:
            body = f.read_text(encoding="utf-8", errors="replace").lower()
        except OSError as e:
            return "missing", "%s unreadable (%s)" % (f.name, e)
        if INJECTION_MARK in body:
            marked.append(f.name)
        elif any(h in body for h in INJECTION_HINTS):
            hinted.append(f.name)
        else:
            bare.append(f.name)
    if bare:
        return "missing", "%s carries no injection red line" % ", ".join(bare)
    if hinted:
        return "unmarked", "found in %s by wording; add <!-- %s --> so it stays checkable" % (
            ", ".join(hinted), INJECTION_MARK)
    return "marked", ", ".join(marked)


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
    fresh, ok_s, empty_s, gap_s, fail_s, blocked_s = 0, 0, 0, 0, 0, 0
    for r in results:
        conn.execute("INSERT INTO fetch_log (ts, source, kind, status, items, detail) "
                     "VALUES (?,?,?,?,?,?)",
                     (now_ts(), r["name"], r["kind"], r["status"], len(r["items"]), r["detail"]))
        tag = {"ok": "OK", "empty": "EMPTY", "gap": "GAP", "failed": "FETCH-FAIL",
               "blocked": "BLOCKED"}.get(r["status"], r["status"].upper())
        log(root, config, "%-10s source=%s kind=%s items=%d%s"
            % (tag, r["name"], r["kind"], len(r["items"]),
               (" - " + r["detail"]) if r["detail"] else ""))
        if r["status"] == "ok":
            ok_s += 1
        elif r["status"] == "empty":
            empty_s += 1
        elif r["status"] == "gap":
            gap_s += 1
        elif r["status"] == "blocked":
            blocked_s += 1
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
    # The version belongs on this line because pipeline.log is append-only, timestamped
    # and machine-written: with it, every library's history carries its own version
    # coordinates, and "which release was this round run under?" stops being a guess.
    log(root, config, "fetch: %d new candidates (deduped); %d awaiting judgment in pending.json "
        "[sources: %d ok / %d empty / %d gap / %d failed / %d blocked] [toolkit %s]"
        % (fresh, n_pending, ok_s, empty_s, gap_s, fail_s, blocked_s, TOOLKIT_VERSION))
    if fail_s:
        log(root, config, "note: %d source(s) FAILED transiently — their items were NOT "
            "fetched; they will be retried next round (a failed fetch is not an empty result)"
            % fail_s)
    if blocked_s:
        log(root, config, "note: %d source(s) BLOCKED by policy — retrying will NOT help. Allow "
            "their domains in the egress allowlist, or run collection locally. (A blocked fetch "
            "is not an empty result — see references/cloud.md)" % blocked_s)
    return 0


# ---------------------------------------------------------------- evidence (read-only)


def cmd_evidence(root, config):
    """Print a paste-able evidence block for a QC report or a handover message.

    Why this exists: a real QC report carried three wrong numbers — not because they
    were computed too early (the report was written last), but because they were
    RETYPED by hand. Two of the three could already have been copied from `stats`
    and `coverage`; the third (a file-identity hash) had no command at all.

    So this is not a new rule telling anyone to be careful. It makes the correct
    path the lazy one: run one command, paste one block. Read-only — it writes
    nothing and changes nothing.
    """
    import hashlib
    conn = connect(root)
    stamp = now_ts()
    name = config.get("name", "?")
    lines = ["```", "evidence · %s · generated_at %s" % (name, stamp),
             "  (produced by: python scripts/pipeline.py evidence — paste, do not retype)", ""]

    rows = dict(conn.execute("SELECT status, COUNT(*) FROM seen GROUP BY status").fetchall())
    total = sum(rows.values())
    lines.append("Bronze (seen): %s  = %d total"
                 % (" / ".join("%s %d" % (k, rows[k]) for k in sorted(rows)) or "empty", total))

    pend = conn.execute("SELECT COUNT(*) FROM silver WHERE promoted=0 AND dismissed=0").fetchone()[0]
    prom = conn.execute("SELECT COUNT(*) FROM silver WHERE promoted=1").fetchone()[0]
    dism = conn.execute("SELECT COUNT(*) FROM silver WHERE dismissed=1 AND promoted=0").fetchone()[0]
    oldest = conn.execute("SELECT MIN(judged_at) FROM silver WHERE promoted=0 AND dismissed=0").fetchone()[0]
    lines.append("Silver: %d awaiting / %d promoted / %d dismissed%s"
                 % (pend, prom, dism, ("   oldest pending %s" % oldest[:10]) if oldest else ""))

    bad = conn.execute("SELECT COUNT(*) FROM fetch_log f WHERE ts = "
                       "(SELECT MAX(ts) FROM fetch_log WHERE source = f.source) "
                       "AND status IN ('gap','failed','blocked')").fetchone()[0]
    srcs = conn.execute("SELECT COUNT(DISTINCT source) FROM fetch_log").fetchone()[0]
    lines.append("Sources: %d known, %d unhealthy on their latest round" % (srcs, bad))

    # File identity — the one value with no existing command, and the one that was wrong.
    mem = memory_files(root)
    if len(mem) >= 2:
        digests = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in mem}
        same = len(set(digests.values())) == 1
        lines.append("Memory files: %s %s (sha256 %s)"
                     % (" == ".join(digests), "identical" if same else "DIFFER",
                        list(digests.values())[0][:12]))
    elif mem:
        lines.append("Memory files: only %s present" % mem[0].name)
    else:
        lines.append("Memory files: none found")

    inj_state, inj_detail = injection_rule_state(root)
    lines.append("Injection red line: %s (%s)" % (inj_state, inj_detail))

    shapes, _problem, _inferred = library_shapes(config)
    i_state, _i_problems, i_note = intake_state(config, shapes)
    lines.append("Intake record: %s%s" % (i_state, (" — " + i_note) if i_note else ""))

    # Retraction alerts belong in evidence for the same reason the Silver counts do:
    # a QC round can ask whether the owner was told, instead of taking it on trust.
    retr = pipeline_dir(root, config) / "retractions.jsonl"
    n_retr = 0
    if retr.is_file():
        try:
            n_retr = len([l for l in retr.read_text(encoding="utf-8").splitlines() if l.strip()])
        except OSError:
            n_retr = -1
    lines.append("Retraction alerts: %s (dismissals that hit a cited source; each one owed "
                 "the owner a word)" % ("unreadable" if n_retr < 0 else n_retr))
    lines += ["```"]
    conn.close()
    print("\n".join(lines))
    return 0


# ---------------------------------------------------------------- add (manual Bronze entry)


def cmd_add(root, config, args):
    """Register a manually-found item into Bronze.

    The collection flow tells you to fill gaps by hand (web search) when the pipeline
    cannot reach a source — but without this command your only options were to hand-write
    SQLite (violating rule 1) or leave the find dangling, unrecorded and undeduped. A
    production cloud round kept the red line and lost three good items proving it.

    Provenance is explicit and permanent: the row's source is stored as 'manual:<source>',
    so a hand-registered item can never masquerade as an automatic fetch in the ledger.
    Once added it is ordinary Bronze: it appears in pending.json and you judge it as usual.
    """
    url = (args.url or "").strip()
    if not url.startswith(("http://", "https://")):
        print("add: url must be http(s) - got %r" % url)
        return 2
    prov = "manual:%s" % ((args.source or "").strip() or "unspecified")
    conn = connect(root)
    cur = conn.execute(
        "INSERT OR IGNORE INTO seen (url, title, source, topic, summary, date, first_seen) "
        "VALUES (?,?,?,?,?,?,?)",
        (url, (args.title or "").strip(), prov, args.topic,
         (args.summary or "").strip(), (args.date or "").strip(), today()))
    added = cur.rowcount  # 0 => url already in the ledger (layer-1 dedup)
    conn.commit()
    n_pending = write_pending(root, config, conn)
    conn.close()
    if added:
        log(root, config, "MANUAL-ADD url=%s source=%s topic=%s" % (url, prov, args.topic or "-"))
        print("added to Bronze as '%s' (provenance recorded); %d item(s) awaiting judgment in "
              "pending.json - judge them, then run: pipeline.py apply" % (prov, n_pending))
    else:
        print("already in the ledger (deduped) - nothing added; %d awaiting judgment" % n_pending)
    return 0


# ---------------------------------------------------------------- apply (judgments -> Silver)


# G2 — Cadence artefacts need one naming convention before anything can count them.
# Four real libraries used four different schemes (`2026-07-22-gold.md`,
# `qc-2026-07-28.md`, `2026-07-21.md`, `2026-07-10.md`), so "how many rounds since
# the last QC" was not merely unanswered — it was uncomputable.
CADENCE_KINDS = ("qc", "run", "calibration", "review")
CADENCE_RE = re.compile(r"^(%s)-(\d{4}-\d{2}-\d{2})" % "|".join(CADENCE_KINDS))


def last_cadence_run(root, config, kind):
    """Date string of the most recent `<kind>-<date>.md` under the pipeline logs dir."""
    logs = pipeline_dir(root, config) / "logs"
    if not logs.is_dir():
        return None
    dates = []
    for f in logs.iterdir():
        m = CADENCE_RE.match(f.name)
        if m and m.group(1) == kind:
            dates.append(m.group(2))
    return max(dates) if dates else None


def cadence_debt(root, config, conn, kind="qc"):
    """One line on how overdue a Cadence is, or '' when there is nothing to say.

    G3 — this rides on the source-health banner rather than inventing a new channel:
    that banner is the one mechanism with evidence of actually working (it reported
    5-of-5 sources down, honestly, in production). It already prints every round and
    users already read it.

    ⚠️ Deliberately NOT a Gate. A Cadence that is overdue means catch up, not stop —
    blocking here would stall the library over a missed report.
    """
    last = last_cadence_run(root, config, kind)
    rounds = conn.execute("SELECT COUNT(*) FROM fetch_log WHERE ts > ?",
                          (last or "",)).fetchone()[0] if last else None
    if last is None:
        total = conn.execute("SELECT COUNT(*) FROM fetch_log").fetchone()[0]
        if total < 5:
            return ""   # too early to nag
        return ("cadence: no %s report found in %s (expected %s-<date>.md) after %d collection rounds"
                % (kind.upper(), pipeline_dir(root, config).name + "/logs", kind, total))
    if rounds and rounds >= 5:
        return "cadence: last %s was %s — %d collection rounds ago" % (kind.upper(), last, rounds)
    return ""


def source_health(conn):
    """One-line source-health banner from the latest fetch status per source.
    A failed/gap/blocked fetch must never be silently read as 'a quiet day'. The three bad
    states each need a DIFFERENT fix, so the banner keeps them apart:
      gap     = the source really has nothing, or the config is wrong -> fix config
      failed  = transient (timeout / 429 / 5xx)                       -> retry next round
      blocked = refused by an egress/proxy policy                     -> allowlist it, or collect locally
    Lumping blocked in with failed would tell the user to retry — which never helps."""
    rows = conn.execute(
        "SELECT source, status FROM fetch_log f "
        "WHERE ts = (SELECT MAX(ts) FROM fetch_log WHERE source = f.source)").fetchall()
    if not rows:
        return "source health: no fetch on record yet"
    per = {s: st for s, st in rows}
    blocked = sorted(s for s, st in per.items() if st == "blocked")
    bad = {s: st for s, st in per.items() if st in ("gap", "failed")}
    parts = []
    if blocked:
        parts.append("%d/%d sources BLOCKED by policy (%s) - retrying will NOT help: allow those "
                     "domains in your egress allowlist, or run collection locally"
                     % (len(blocked), len(per), ", ".join(blocked)))
    if bad:
        parts.append("%d/%d sources failed to fetch (%s) - this is a FETCH problem, not 'no news'; "
                     "retry / check config"
                     % (len(bad), len(per), ", ".join("%s=%s" % (s, st) for s, st in sorted(bad.items()))))
    if parts:
        return "WARNING source health: " + " | ".join(parts)
    return ("source health: all %d sources ok (%s) - a short brief today is a genuinely quiet "
            "day, not a fetch failure" % (len(per), ", ".join(sorted(per))))


def health_banner(root, config, conn):
    """Source health + any Cadence debt, as one block for the draft brief."""
    parts = [source_health(conn)]
    debt = cadence_debt(root, config, conn, "qc")
    if debt:
        parts.append("WARNING " + debt)
    return "\n> ".join(p for p in parts if p)


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
        "> **%s**" % health_banner(root, config, conn),   # a short/empty brief must never be misread as 'nothing happened'
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


def constant_score_warning(judgments, seen_source):
    """F3 — warn when one source's items all carry an identical score.

    In a real round 76% of candidates got a per-source constant (52 items at 0.15,
    47 at 0.16, 47 distinct real papers all at 0.28), which is what "judge substance,
    not keywords" is meant to prevent — and the script that produced them was deleted,
    so the reasoning could not be reconstructed.

    ⚠️ A WARNING, never a rejection: a machine cannot tell a lazy blanket score from a
    correct one. In that same round the 52 items at 0.15 really were all issue-index
    pages, and one score for all of them was the right call. Only a person can tell
    the two apart — so this reports, and lets the person decide.
    """
    by_source = {}
    for j in judgments:
        src = seen_source.get(j.get("url"), "?")
        try:
            rel = float(j.get("relevance", 0))
        except (TypeError, ValueError):
            continue
        by_source.setdefault(src, []).append(rel)
    flagged = []
    for src, scores in by_source.items():
        if len(scores) >= 5 and len(set(scores)) == 1:
            flagged.append("%s: %d items all scored %.2f" % (src, len(scores), scores[0]))
    if not flagged:
        return ""
    return ("NOTE constant scores — %s. If that is a real judgement (e.g. they are all "
            "index pages), fine; if it is one blanket score standing in for reading them, "
            "it is what rule 3 forbids. Nobody but you can tell." % "; ".join(sorted(flagged)))


def record_calibration(root, config, entries):
    """①-b — append this round's judgments to _pipeline/calibration.jsonl.

    Item-level judgement has never been persisted, so "8/10 this month vs 7/10 last
    month" compared two different random samples and was never actually comparable.
    With a durable record, the next A1 round can re-score the SAME items and produce
    the first number that means anything.

    Append-only, one JSON object per line, no schema change.
    """
    if not entries:
        return
    path = pipeline_dir(root, config) / "calibration.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")


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
    seen_source = dict(conn.execute("SELECT url, source FROM seen").fetchall())
    calib = []
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
        # (1)-b: persist the item-level judgement so a later calibration round can
        # re-score THE SAME items. Without this, "8/10 this month vs 7/10 last month"
        # compares two different random samples and means nothing.
        calib.append({"ts": ts, "url": url, "source": seen_source.get(url, "?"),
                      "title": title, "topic": topic, "relevance": rel,
                      "threshold": thr, "verdict": "kept" if rel >= thr else "low",
                      "one_line": j.get("one_line", "")})
    conn.commit()
    path, n_draft = write_draft_brief(root, config, conn)
    n_pending = write_pending(root, config, conn)  # judged items leave pending.json
    conn.close()
    record_calibration(root, config, calib)
    log(root, config, "apply: %d kept (>=%.2f) / %d low / %d skipped; draft brief -> %s "
        "(%d items, union of today); %d still pending"
        % (kept, thr, low, skipped, path.name, n_draft, n_pending))
    warn = constant_score_warning(judgments, seen_source)
    if warn:
        log(root, config, warn)
    return 0


# ---------------------------------------------------------------- promote / dismiss


def url_variants(url):
    """The handful of literal spellings the same URL is usually written in.

    Deliberately small. A scheme, a leading `www.`, a trailing slash and a `#fragment`
    are formatting; a query string is NOT — for some sites the query is the identity —
    so it is never stripped. Matching stays case-sensitive: over-matching would raise
    retraction alerts for things nobody cited, and an alert that cries wolf gets tuned
    out, which costs more than the occasional miss. Under-reporting is the safe
    direction here, because this is a reminder and never a gate.
    """
    u = (url or "").strip().split("#", 1)[0]
    if not u:
        return []
    bare = re.sub(r"^https?://", "", u)
    forms = {u, u.rstrip("/")}          # scheme-bearing: `://` anchors it at any length
    stripped = {bare, bare.rstrip("/")}
    for b in tuple(stripped):
        stripped.add(b[4:] if b.startswith("www.") else "www." + b)
    # A bare form has no `://` to anchor it, so a short one matches unrelated prose —
    # `www.a` would hit www.amazon.com, and `a` would hit everything. Drop those
    # instead of guessing: a reminder that stays quiet costs less than one nobody
    # believes any more.
    forms |= {c for c in stripped if len(c) >= 8}
    return sorted((f for f in forms if f), key=lambda f: (-len(f), f))


def citation_scan_dirs(root, config):
    """The directories a dismissal is checked against — an explicit allowlist.

    ⛔ Never walk from the library root. `_pipeline/logs/pipeline.log`,
    `_pipeline/pending.json` and `_pipeline/calibration.jsonl` each contain every URL
    the pipeline has ever handled, so a root walk would report a hit for every
    dismissal — including the one being made at that moment.

    `answers/` comes first because it is what the rule is actually about: an answer
    given from outside the library files its sources as Bronze, and if one is later
    dismissed the owner has to be told (references/keeper.md § Answering from outside
    the library). notes/ and briefs/ are the same question asked of Gold.
    """
    paths = config.get("paths", {})
    return [pipeline_dir(root, config) / "answers",
            root / paths.get("notes", "notes"),
            root / paths.get("briefs", "briefs")]


def find_citations(root, config, url):
    """Files under the allowlisted directories that quote this URL."""
    forms = url_variants(url)
    hits = []
    if not forms:
        return hits
    for d in citation_scan_dirs(root, config):
        if not d.is_dir():
            continue
        try:
            files = sorted(d.rglob("*.md"))
        except OSError:
            continue
        for f in files:
            try:
                body = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue   # one unreadable file must never break a dismissal
            if any(v in body for v in forms):
                hits.append(f)
    return hits


def record_retraction(root, config, url, reason, files):
    """Append the hit to _pipeline/retractions.jsonl (same trick as calibration.jsonl:
    a file, not a table, so no schema moves).

    Printing it would only reach whoever is running the command. Recording it is what
    lets a later QC round ask the question that matters — was the owner ever told? —
    of a keeper that has moved on.
    """
    path = pipeline_dir(root, config) / "retractions.jsonl"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": now_ts(), "url": url, "reason": reason or None,
                                 "cited_in": files}, ensure_ascii=False) + "\n")
    except OSError:
        pass  # the notice already printed; bookkeeping must not fail a dismissal


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
        # R4 — references/keeper.md § Answering from outside the library: a source that
        # gets dismissed after it was cited makes something ALREADY SAID unreliable.
        # That rule was prose, so nothing was looking. Runs after the commit, and never
        # touches the exit code: this is a notice, not a gate.
        try:
            hits = find_citations(root, config, url)
        except OSError:
            hits = []
        if hits:
            rel = [h.relative_to(root).as_posix() for h in hits]
            record_retraction(root, config, url, reason, rel)
            log(root, config,
                "RETRACTION-CHECK this url is still cited in %d file(s): %s%s — tell the "
                "OWNER, unprompted: name the answer or note affected and say that part is "
                "now unreliable, then update its status. Recorded in %s/retractions.jsonl."
                % (len(rel), ", ".join(rel[:5]), " …" if len(rel) > 5 else "",
                   pipeline_dir(root, config).name))
            log(root, config,
                "  ⚠️ This finds the common spellings of a URL, not every one, and it can "
                "only make the fact available — it cannot tell the owner for you. A quiet "
                "result is not proof that nothing cites it.")
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
        for key in ("name", "sources", "paths"):
            if not check("config has %r" % key, key in config):
                failures_cfg.append(key)
        shapes, problem, inferred = library_shapes(config)
        if inferred:
            # Absent means "never written" — infer, say so out loud, and keep going.
            # Libraries built before this key existed must not break on it.
            check("config type (inferred: %s)" % "+".join(shapes), True,
                  "no 'type' key — inferred because %s; add it to be explicit" % inferred)
        elif not check("config type valid", not problem, problem or "+".join(shapes)):
            # Present but wrong is a different thing from absent, and papering over
            # it silently would turn a config error invisible — precisely the class
            # of failure this release exists to remove.
            failures_cfg.append("type")
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

        # F1 — the injection red line is mandatory in the library's own memory file
        # (SKILL.md rule 8) and was, until now, held up by prose alone. A real build
        # dropped it. Graded on purpose: selftest also runs mid-scaffold, before the
        # memory file exists, so "not written yet" must not read the same as "written
        # without the rule".
        inj_state, inj_detail = injection_rule_state(root)
        if inj_state == "marked":
            check("injection red line present in memory file", True, inj_detail)
        elif inj_state == "unmarked":
            check("injection red line present in memory file", True, inj_detail)
        elif inj_state == "no-memory-file":
            check("injection red line (memory file not written yet)", True,
                  "no CLAUDE.md/AGENTS.md yet — re-run selftest after scaffolding")
        else:
            check("injection red line present in memory file", False, inj_detail)
            failures_cfg.append("injection-red-line")

        # R1/R2 — the Intake record. See intake_state() for the grading rationale and
        # for the one implementation rule that must not be broken (no text matching).
        i_state, i_problems, i_note = intake_state(config, shapes)
        if i_state == "ok":
            check("intake record complete (shape %s)" % "+".join(shapes), True)
        elif i_state == "unrecorded":
            # A scar, not an exemption: it prints on every run, and it is greppable.
            check("intake record — DECLARED UNRECORDED", True,
                  "%s; nobody is claiming who decided what" % i_note)
        elif i_state == "absent":
            check("intake record present", False,
                  "config.json has no %s — %s" % (INTAKE_KEY, unrecorded_hint()))
            failures_cfg.append("intake")
        else:
            for p in i_problems:
                check("intake: %s" % p, False)
            failures_cfg.append("intake")

        # R5 — build provenance. One legacy declaration covers both records: a library
        # that predates the intake record certainly predates this one.
        b_state, b_problems = built_with_state(config)
        if i_state == "unrecorded":
            check("build provenance (waived — intake declared unrecorded)", True,
                  "one legacy declaration, not two")
        elif b_state == "ok":
            check("build provenance recorded (%s)" % config[BUILT_WITH_KEY].get("skill_source"), True)
        elif b_state == "absent":
            check("build provenance recorded", False,
                  "config.json has no %r — record where the skill was READ from, and paste "
                  "the scripts' own version rather than typing one" % BUILT_WITH_KEY)
            failures_cfg.append(BUILT_WITH_KEY)
        else:
            for p in b_problems:
                check("build provenance: %s" % p, False)
            failures_cfg.append(BUILT_WITH_KEY)

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
    p = sub.add_parser("add", help="register a manually-found item into Bronze "
                                   "(provenance kept as manual:<source>)")
    p.add_argument("url")
    p.add_argument("--title", required=True, help="the item's title")
    p.add_argument("--source", required=True,
                   help="where you found it (outlet/site); stored as 'manual:<source>' so a "
                        "hand-added row never looks like an automatic fetch")
    p.add_argument("--topic", help="topic label, as a judging hint")
    p.add_argument("--summary", default="", help="one-line gist (optional)")
    p.add_argument("--date", default="", help="publication date, YYYY-MM-DD (optional)")
    sub.add_parser("apply", help="apply _pipeline/judgments.json -> Silver + draft brief (idempotent)")
    p = sub.add_parser("promote", help="mark a Silver item promoted to Gold")
    p.add_argument("url")
    p = sub.add_parser("dismiss", help="dismiss a Silver item with a reason (audited)")
    p.add_argument("url")
    p.add_argument("reason", nargs="*", help="why this item is not relevant (recommended)")
    sub.add_parser("stats", help="tier counts, Silver aging, dismiss reasons, fetch health")
    sub.add_parser("evidence", help="read-only: a paste-able evidence block for QC reports and handover (never retype these numbers)")
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
    if args.cmd == "add":
        return cmd_add(root, config, args)
    if args.cmd == "apply":
        return cmd_apply(root, config)
    if args.cmd == "promote":
        return cmd_promote(root, config, args.url)
    if args.cmd == "dismiss":
        return cmd_dismiss(root, config, args.url, " ".join(args.reason))
    if args.cmd == "stats":
        return cmd_stats(root, config)
    if args.cmd == "evidence":
        return cmd_evidence(root, config)
    if args.cmd == "run":
        return cmd_run(root, config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
