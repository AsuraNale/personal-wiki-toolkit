# Example: an intel-type library ("vuln-watch")

A worked example of an **intel-type library** — the kind the toolkit builds when you
want to *track a domain over time*.

**This one is real.** The notes, briefs, and fetch log in this folder came from an
actual collection round against live sources on 2026-07-20 — not crafted sample data.
What you see is what the pipeline produced.

```
config.json            6 sources, 4 topics, keep-threshold 0.70
_pipeline/silver/      the machine-drafted brief, exactly as generated
notes/ briefs/         GOLD: what a human decided to keep
CARE.md                the owner's two-minute daily habit
```

> **Not checked in:** `intel.db` / `kb.db` (the ledger and the index) and `scripts/`.
> Databases are gitignored — they are created on first run, and a real library's ledger
> is its own rather than a sample. The scripts live at the toolkit root and are copied
> into a library at scaffold time. **What you see here is the human-readable output of a
> real round; the numbers below are that round's ledger.**

## What actually happened in this round

```
fetch    6 sources → 87 candidates    [5 ok · 0 empty · 0 gap · 0 failed · 1 BLOCKED]
judge    87 scored by the host agent  → 41 kept at ≥0.70
apply    41 → Silver + draft brief
promote  8 → Gold (2 files: one brief, one synthesized note)
```

## What to look at, and why

**1. `_pipeline/silver/AUTO-2026-07-20.md` — read the banner first.**

One of the six sources (CISA) returned HTTP 403. The brief opens with:

> *"1/6 sources BLOCKED by policy — retrying will NOT help: allow those domains in
> your egress allowlist, or run collection locally"*

That banner is the single most important line in this example. **The source published
during that window; we simply couldn't read it.** A pipeline that reported this round
as "nothing new" would have been lying, and the library would have rotted quietly.
`blocked` is a distinct state from `empty` precisely so this cannot happen.

**2. `briefs/` and `notes/` — look at the front-matter `refs`.**

Every Gold file lists the exact Silver `url` behind each claim:

```yaml
refs:
  - key: https://thehackernews.com/2026/07/critical-nginx-vulnerability-can-crash.html
    used_for: "nginx CVE-2026-42533 fixed-version list"
```

Gold summarizes, and summarizing loses detail. The `refs` list is what lets anyone walk
a claim back to the original. **A key that doesn't resolve to a Silver row marks the
item as incompletely sourced — it never triggers a rewrite.** Flagging beats blocking:
an item you can see is under-sourced is far better than one that silently isn't.

**3. `notes/registry-poisoning-2026-07.md` — a synthesized note, not a link dump.**

Three separate Silver entries about package-registry attacks, combined into one note
with a mechanism and a "what these sources do NOT establish" section. That last section
is deliberate: the note says plainly that the three campaigns are **not** attributed to
a common operator, so nobody reads a coordinated wave into it later.

**4. `keeper.md` — the red lines, and one specific rule.**

Duty 4 (Expand) requires that anything found *outside* the library enters through
`pipeline.py add` first — getting a real item-level URL and `manual:*` provenance —
before it can become Gold. **Nothing skips a tier, including things the keeper found
itself.**

**5. `CARE.md` — the two-minute daily habit.**

The part that can't be automated: deciding what's worth keeping, and dismissing the
rest *with a reason*.

---

For a data/ETL-type library instead (numbers, not notes), see `examples/etl-kb/` —
it is deliberately structured differently, and its README explains why.
