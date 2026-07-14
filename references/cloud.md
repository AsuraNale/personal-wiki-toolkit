# Running in the cloud (optional path)

Read this when the user wants their library to live in a **cloud agent session**
(a web session or a scheduled cloud routine) instead of on their own machine —
or when you discover you are running inside one.

**One line: the cloud is the strongest library *builder* and the weakest
*collector*.** Plan around that, and say it before the user invests.

## Local is the default; cloud is a choice

| | Cloud | Local |
|---|---|---|
| Build the library, design the schema, write the docs | ✅ strong | ✅ |
| Q&A, curation, reachable from anywhere | ✅ (runs with the PC off) | needs the machine on |
| **Real collection (reaching arbitrary sources)** | ⚠️ **limited by an egress allowlist** — many sources cannot be allowed at all | ✅ no such limit |
| Unattended scheduling | ✅ | at the mercy of sleep/downtime |

**First library? Start local.** No egress policy, collection genuinely works, and
you can finish the loop (rule 7) in one sitting. Choose cloud when the user needs
it to run with their PC off, wants access from anywhere, or won't install Python.

**Best of both — the hybrid:** build and curate in the cloud, run the collector
locally. Two independent cloud builds reached this same conclusion on their own.

## The capability boundary — say it out loud

Cloud sandboxes route outbound traffic through a proxy with a domain allowlist.
**Anything not on the list fails with a policy denial (typically HTTP 403) — not
a site error.** This is environment policy, not anti-bot defence: the source is
fine; your sandbox refused to go there.

The pipeline records these as **`blocked`** — a state of its own, deliberately
separate from `gap` ("nothing there / fix your config") and `failed` ("transient,
retry"), because a policy denial needs a third fix entirely: allow the domain, or
collect locally. Note the denial can arrive at two layers — an HTTP 403, or a
proxy refusing the https CONNECT (surfacing as `Tunnel connection failed: 403`).
Both are `blocked`. See `pipeline-discipline.md` §1.

Evidence (two independent cloud builds, same week):
- an ETL library: 3 retail sources → policy-denied;
- an intel library: **7 of 8 sources (all Hacker News, all arXiv) died** — the run
  "succeeded", and only the source-health banner revealed the brief had been built
  from the single source that happened to be allowed.

So: **"I can build you a library in the cloud" ≠ "it can collect in the cloud."**
Tell the user *before* they choose this path. To actually collect you need either
(1) the egress allowlist configured for your sources — and not every source can be
allowed — or (2) the collector running locally.

## Mandatory step: configure the egress allowlist

The rest of this toolkit was written for local use, where this step does not
exist. In the cloud **it is not optional** — skip it and collection dies quietly.

1. Find where your platform sets network access for the session/environment. (On
   Claude Code on the web: the routine's cloud environment → Network access →
   **Custom** → Allowed domains.)
2. Allow, at minimum:
   - **every host your `config.json` sources resolve to** — e.g. `hn.algolia.com`,
     `export.arxiv.org`, each feed's domain;
   - the git host you push to: `github.com`, `api.github.com`, `codeload.github.com`;
   - your agent platform's own API domain (e.g. `api.anthropic.com`).
3. **Verify after the first run — don't assume.** Read the source-health banner /
   `fetch_log`. If sources show failures, check for a proxy denial *before* you
   conclude "no news".

**What "missed this step" looks like:** every fetch is policy-denied, the pipeline
records failures, and the brief gets built from whatever slipped through. A green
run status means the session exited — not that collection worked. Rule 6 exists
for exactly this.

## Read the toolkit with `git clone`, not a web fetch

If you are a cloud agent reading this toolkit from its repo: **clone it.**

Cloud agents have `git`. A web-fetch tool will often hand you a *summary* of a
page instead of its bytes — one production run found the fetcher declined to
reproduce `setup/INTERVIEW.md` verbatim and paraphrased it, leaving the agent
working from a lossy copy of its own instructions. Clone the repo; read the files
off disk.

(Related: the GitHub API tree endpoint requires auth for some repos. If you hit
that, browse the public repo pages instead — or just clone, which sidesteps it.)

## Where the library actually lives

**In the repo — and the user pulls it back.** A cloud sandbox is a temporary
container with no access to the user's machine. If the user hands you a path like
`C:\Users\them\Desktop\my-kb`, that path does not exist for you. Say so, early,
and agree on the repo instead.

Be concrete: "your library will live in `github.com/<you>/<repo>`; to have it on
your laptop, `git clone` it there (and `git pull` after each round)."

## Branch reality: you can likely only push `claude/*`

Cloud agent sessions are typically restricted by the platform to pushing branches
under `claude/` — pushes to `main` are refused. The platform enforces this, not
you, and it is a feature: an unattended session cannot rewrite the canonical branch.

State plainly:
- your work lands on a `claude/…` branch, **not** `main`;
- the user must pull/merge (or merge a PR) to make it canonical;
- anything bound for `main` goes through a pull request the user reviews.

## If policy blocks you: report it, don't route around it

A policy denial is a fact to report, not an obstacle to defeat. **Never** evade it
— no alternate proxies, no mirror scraping, no "creative" routing. Record the
denial (it lands in `blocked`, never "nothing new"), tell the user which domains
were refused and what to allow, and continue with what you honestly have.

If nothing survived, say the round collected nothing, and why. **A library built
from the one source that happened to be allowed, presented as a normal round, is a
lie of omission.**

**The honest fallback when collection is blocked:** find items with your own web
tools and register each one with

```
python3 scripts/pipeline.py add <url> --title "…" --source "<where you found it>" [--topic …]
```

It enters Bronze, joins the dedup ledger, and appears in `pending.json` for normal
judging — with its provenance permanently recorded as `manual:<source>`, so a
hand-found item never masquerades as an automatic fetch. **Do not hand-write the
SQLite files** to work around a blocked round (rule 1); that is what this command
is for.
