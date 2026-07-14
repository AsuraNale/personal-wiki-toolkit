# Pipeline discipline: making automated collection trustworthy

Read this before you write or schedule any fetch automation. A collection
pipeline that runs unattended every day will, over months, hit every failure
mode a network can produce. These rules are what separate a library you can
trust from one that quietly rots. Every one was paid for by a real incident in
a production library.

## 1. A failed fetch is not an empty result (the cardinal rule)

The most dangerous bug in a collection pipeline is silent: a source errors, the
code treats "I got nothing" as "there was nothing," and a whole topic quietly
stops updating while the library looks healthy.

Classify every fetch into **five** outcomes, never two:

| Outcome | Meaning | What it is NOT |
|---|---|---|
| `ok` | fetched, parsed, ≥1 item | — |
| `empty` | fetched fine, zero items — the source genuinely had nothing | not a failure |
| `gap` | permanent-looking: HTTP 4xx (except 403/407/408/429), unparseable feed, wrong URL | not transient — blind retry won't fix it; fix the config |
| `failed` | transient: HTTP 5xx, 408/429 rate-limit, timeout, connection reset | **not empty** — the items exist, we just didn't get them; retry next round |
| `blocked` | refused by policy: HTTP 403/407, or a proxy refusing the connection/tunnel | **neither** "the source is empty" **nor** "your config is wrong" — retrying never helps; allow the domain, or collect locally |

A production library once reported a data series as "empty" for weeks because a
single HTTP 504 (a transient `failed`) was misread as emptiness. The fix wasn't
cleverer code — it was refusing to collapse five states into two.

**Each state exists because it needs a DIFFERENT fix.** That is the whole point:
`gap` → fix the config · `failed` → retry next round · `blocked` → allowlist the
domain, or move collection local. Merge any two and you hand the user an action
that cannot work.

**429 and 408 are `failed`, not `gap`.** They're rate-limiting / request-timeout
— transient. arXiv in particular returns 429 readily (it asks for ≥3s between
requests); mislabeling that as a permanent `gap` tells the user to "fix their
config" when all they need is the next round.

**403/407 are `blocked`, not `gap`.** A refusal is no evidence the source is
empty, and "check your config URL" is the wrong advice when the real problem is
an egress allowlist. Two things make this worth its own state:
- **It is the dominant failure mode in the cloud.** One production cloud round
  lost **7 of 8 sources** to policy denials and still "succeeded" — only the
  health banner revealed the brief had been built from the one source that
  happened to be allowed.
- **The same denial can arrive at two layers.** An HTTP 403 surfaces as an
  HTTPError; a proxy refusing an https CONNECT surfaces as an `OSError`
  ("Tunnel connection failed: 403 Forbidden") instead. In that same round one
  identical cause landed in two different states (`gap` for arXiv, `failed` for
  Hacker News) until both were routed to `blocked`. **Classify at both layers**,
  or the inconsistency survives.

And a refusal is **ambiguous** (egress policy / anti-bot / auth required), so
never assert the cause — report the troubleshooting priority: in a cloud or
sandbox environment, check the allowlist first. Details: `cloud.md`.

## 2. Idempotency and catch-up by construction

Every step must be safe to run twice, and safe to run after a missed run:

- **Dedup on a stable key** (URL for items, path for notes) so re-fetching
  overlapping windows inserts nothing new.
- **Rebuild the work queue from state, not from this run's catch.** Regenerate
  `pending.json` from *all* unjudged rows (`WHERE status='new'`), not just what
  this fetch returned. Then a round that was interrupted before judging simply
  reappears next time — catch-up needs no special code.
- **Re-applying judgments upserts, never duplicates or clobbers.** INSERT OR
  IGNORE the row, then UPDATE the machine fields — human promote/dismiss flags
  survive untouched.

The test for idempotency is blunt: run the whole pipeline twice with no new
upstream data. The second run must change nothing.

## 3. One bad source never sinks the round

Fetch each source in isolation. A parser bug, a 500, or a malformed feed on
source #3 must not stop sources #4–#20 or crash the run. Concretely:

- Catch per-source; record the failure in the ledger; **keep going**.
- The overall process exits 0 even when individual sources failed — a failed
  source is data (a `failed` row), not a crash. (A scheduler that sees a nonzero
  exit may retry the *whole* round, re-fetching everything — usually worse.)
- Surface failures loudly in the run summary and in `stats`, so "exit 0" never
  means "all was well" when it wasn't.

## 4. Windowed fetching for backfill

When first building a library or filling a gap, don't ask a source for
"everything" — page or date-window the requests (e.g. month by month) so a
single request can't time out on a huge response, and so a failure only costs
one window, not the whole backfill. Each window is idempotent (rule 2), so a
failed window is just retried.

## 5. Politeness and compliance

- Identify yourself with a `User-Agent`; respect rate limits (back off on 429,
  honor `Retry-After` when present).
- **Free, public sources only.** No paywalls, no ToS-hostile scraping, no
  credentials the user didn't provide.
- **Store title + link + summary + date — never full article text.** The
  library is an index and a set of your own notes, not a copy of the web. This
  keeps it lean and keeps it clean.

## 6. The fetch log is the health record

Write every fetch outcome to a ledger row (source, kind, status, item count,
detail, timestamp). This is what lets `stats` answer "is any source silently
broken?" A `failed` streak on one source over several rounds is a health
problem to raise with the user — not a blip to average into "mostly working."
Discipline that lives only in prose gets lost; discipline written to a `status`
column gets enforced.

**Level-0 (no DB):** the health record is a Markdown run-log instead —
`_pipeline/logs/YYYY-MM-DD.md` per round, listing each source's outcome
(ok / empty / gap / failed / blocked) and counts. Same purpose: so "nothing new" is always
distinguishable from "the fetch didn't run," and what was actually fetched stays
separable from what the agent merely asserts it fetched.

## 7. Scheduling is the user's to own

Registering a scheduled task often needs privileges an agent shouldn't assume,
and the user should know exactly what runs on their machine. Generate the
schedule command (Windows `schtasks`, macOS `launchd`, Linux `cron`) and have
the *user* run it. Always offer the no-schedule alternative too: "open your
agent in the library and say *run a collection round*" needs no registration
and works everywhere. See `setup/SCAFFOLD.md` for the per-platform commands.
