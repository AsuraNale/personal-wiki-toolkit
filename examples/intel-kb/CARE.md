# Caring for vuln-watch

One page. This is for **you**, the owner — not for the agent.

A library only stays useful if someone decides what's worth keeping. That part
can't be automated, but it's about two minutes a day.

## Daily — or whenever a new brief shows up (~2 min)

1. **Skim the newest draft** in `_pipeline/silver/`.
2. **Check the top banner first.** If it says a source was **blocked** or **failed**,
   that round is incomplete — *it does not mean there was no news*. Fix the source or
   accept the gap knowingly.
3. For anything worth keeping: **promote it.** For anything not: **dismiss it with a
   reason.**

```
py -X utf8 scripts/pipeline.py promote <url>
py -X utf8 scripts/pipeline.py dismiss <url> "too vendor-marketing, no technical detail"
```

**The reasons matter more than they look.** They accumulate into your working
definition of "not relevant here", and they're what stops the same item resurfacing
as new. A dismissal with no reason throws that away.

Leaving something in Silver is a legitimate third option. Not everything needs
deciding today.

## Weekly (~5 min)

Open this folder with your agent and ask:

> *"What's new, what's gone stale, and what have I kept asking about that we don't track?"*

Then check the backlog: `py -X utf8 scripts/pipeline.py stats`.
**If items have been waiting more than two weeks, curation has stalled** — either
catch up or lower the threshold, but don't let Silver silently become a landfill.

## Monthly (~15 min)

Pull five random Gold items and **follow every `refs` key**. Each one should land on
the actual article the claim came from.

- A key that doesn't resolve is a **finding, not a typo** — it means something got
  summarized past the point of traceability.
- This is also the check that catches the failure this library is designed against:
  a Gold write-up that reads fine but can no longer be verified.

## When something looks wrong

Every Gold file lists its sources in the front-matter `refs`. **Go read the original.**
That's the whole point of keeping them — the summary is a convenience, the source is
the record.

## What this library will never do on its own

- Add a source or a topic — it can *propose*, you approve.
- Delete anything you wrote.
- Report a quiet round as "no news" without telling you whether the sources actually
  answered.
