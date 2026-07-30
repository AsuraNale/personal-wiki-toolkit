# Changelog

Notable changes, newest first. Written for the people who use this toolkit —
developer-facing structure lives in [README.md](README.md), and the
plain-language walkthrough is [MANUAL.md](MANUAL.md) (中文:[MANUAL.zh.md](MANUAL.zh.md)).

---

## v0.1.4 — unreleased

### Withdrawn: the Preflight gate

**v0.1.3's headline feature is removed, two weeks after shipping.** It required
the agent to prove it could write to the user's machine — state the path, drop a
probe file, and have the user go look at it — before anything else happened.

It is withdrawn because it broke the flow it was protecting: three exchanges
before the work starts, one of them asking the user to leave the conversation and
check a folder. And the users it would have turned away are ones this toolkit does
not set out to serve — someone who cannot give their assistant a working folder
after reading the manual needs a different kind of product.

**What replaces it:** one sentence in the manual — *open a folder as its workspace
before you start*. Nothing that cannot be checked automatically should cost the
user an action.

**What this gives up, stated plainly:** the failure it caught was real — a user
once finished a whole session believing a library had been built, inside an
assistant with no filesystem at all. That failure can happen again, and now
nothing will stop it. The v0.1.3 entry below is left exactly as published;
withdrawing a feature is not a reason to edit the record of having shipped it.

The constraint that made it hard is unchanged and will face any future attempt:
**an agent cannot prove from its own side that where it wrote is where the user
looks.** The concept stays in `references/glossary.md`, marked `deferred`, with
that constraint recorded.

## v0.1.3 — 2026-07-27

**The theme: the toolkit stopped taking its own word for it.**

Both new gates in this release exist for the same reason — an agent cannot
verify its own claims from its own side. **Preflight** ends with *you* looking
at your own disk. **Intake** records who decided each setup value rather than
what the agent concluded. The QC rubric now asks what you *opened*, not what you
*produced*. The pattern was already in the collector (a fetch that returns
nothing is `empty`; a fetch that never happened is `gap`) — this release pushes
it into setup, curation, and QC.

### What you'll notice

**Setup can no longer end with a library that isn't there.**
A **Preflight** gate now runs before anything else, in three parts: the agent
states the absolute path it is about to write to, writes a probe file and reads
it back, and then — the part that matters — asks *you* to go look and confirm
the file is there. Only then may it say the library exists.

> This came from a real report: someone finished a whole session believing a
> library had been built, inside an assistant that had no filesystem at all. The
> probe alone would not have caught it. **An agent cannot prove from its own
> side that where it wrote is where you look** — that isn't caution, it's a
> logical impossibility, so the last step has to be yours.

**Setup decisions are now on the record.**
The **Intake** gate writes what was decided into `config.json`, each value
marked `user-typed`, `user-selected`, or `default-accepted`. `agent-inferred`
is not permitted for any key decision. Accepting an offered default is a
decision; never being asked is not — and now you can tell the two apart months
later.

**The interview stopped rushing you.**
Phase 1 no longer carries a "≤3 exchanges" target, and the instruction to raise
structural choices *"only if the user seems opinionated"* is gone. Those two
lines were the toolkit telling the agent not to ask — which made every
downstream guardrail moot.

**The librarian is presented as the maintainer, not a convenience.**
You can still decline it. You'll now be told the trade in plain terms: nothing
will error, the library will just quietly silt up, and the upkeep becomes yours.

**Answers given outside the library can be taken back.**
When a question is answered from outside the collection, its sources are filed
as Bronze. If one of them is later dismissed, the librarian raises it unprompted
rather than waiting to be asked again. This is the first mechanism here that
corrects something *already said*.

**Data libraries stopped being forced into tiers.**
Bronze→Silver→Gold is for libraries that **adjudicate items**. Libraries that
**accumulate measurements** now have their own documented shape —
Fact→Derived→Conclusion, where facts are final on write and the human judgment
happens at the interpretation, not the row. Forcing the tiers onto data was
stalling those libraries in practice.

**Your language on screen, ASCII on disk.**
Naming is no longer a trade-off you have to make. Directories and filenames stay
ASCII (paths that don't break intermittently under sync tools and shells) while
titles, START-HERE, and index tables carry your own language.

**The toolkit says what it is not.**
It is not a document converter. If you ask for a polished export, you'll be told
that's a separate job rather than handed a file whose links were silently
mangled in conversion — a caveat added in direct response to a report of broken
links in a generated `.docx`.

### Curation rules that were producing wrong output

- **A later stage of the same story is no longer a duplicate.** "Tendering
  begins", "breaks ground", and "opens" are three events, not one repeated
  three times. Dedup now checks stage, the underlying event date (not the
  publication date), and whether figures were revised.
- **A number keeps its meaning, not just its digits.** *Aims to build 30,000
  units* must not end up in a note as *30,000 units built*. Status words —
  target, forecast, approved, achieved — now survive into the note, and where a
  source is vague, the vagueness is stated rather than resolved in the
  favourable direction.
- **The QC threshold can't be nudged until the score looks good.** Diagnosing
  comes first, in a fixed order: read the misses, fix the judgment, re-score the
  same batch, and only then touch the threshold — recording that you did.
- **"The file was produced" is not "the file is correct."** Any rendered
  artifact — an export, a generated index, a chart — has to be opened and
  checked before it's reported: links followed, numbers checked for formatting
  damage, the ending checked for truncation. QC reports now state what was
  *looked at*.
- **Source reliability is a band, not a boolean.** Where a library genuinely
  mixes official filings with aggregators, `source_type` records which band a
  figure came from, bands are shown rather than silently averaged together, and
  conflicting bands are both displayed. Single-source libraries add nothing.

### Under the hood

- **`type` is now validated.** The one code change in this release: the library
  type is checked against a vocabulary instead of being accepted as any string.
  A missing `type` is inferred with the inference stated out loud, rather than
  defaulting silently — a real library had been running with the wrong shape
  since the day it was created, and nothing had ever said so. Composite
  libraries can declare an array (`["intel", "data"]`), which is legal.
- **Tests: 65 → 81.**
- The example libraries were filled in. `examples/intel-kb` now shows a complete
  Silver→brief chain with per-claim source URLs on the Gold note — previously
  its only Gold note cited sources in prose with no links at all, which taught
  exactly what the QC rubric forbids. `examples/etl-kb` now explains *why* it
  has no tiers, instead of leaving the difference silent.

### For anyone reading the docs

- **`references/glossary.md`** is new. Six models are registered — Medallion,
  Curation, Fetch Honesty Protocol, Preflight, Intake, and the accrual chain —
  each with its scope, where it's enforced, every file that has to change with
  it, and the incident that produced it.
- Two organizing ideas are now named and kept distinct: a **Gate** blocks and
  requires evidence an agent cannot fabricate alone; a **Cadence** is periodic
  and is simply re-run if a cycle is missed.
- New templates: `qc-report`, `start-here`, `notes-index`.
- `README.zh.md` was removed. Developer-facing docs are English-only from here;
  user-facing docs (the manual, this changelog) stay bilingual. The Chinese entry
  point is [MANUAL.zh.md](MANUAL.zh.md), still linked from the README.

### ⚠️ Verified at the document level only

Seven behaviours specified in this release were **not** exercised end-to-end,
because each requires a live agent session to observe:

1. Preflight reporting `E1` in an environment with no file tools
2. Preflight reporting `E2` when the target directory is read-only
3. Preflight reporting `E3` when no working directory was given
4. Preflight reporting `E4` when the user answers "I don't see it"
5. Preflight refusing to declare the library built while stage 3 is unconfirmed
6. Intake blocking a setup in which a key decision was `agent-inferred`
7. The retraction prompt firing when a previously-cited source is later dismissed

They are specified, and the documents were checked — but they were not run. A
check that didn't happen is recorded as not having happened, not as a pass. That
is the same rule this toolkit applies to its collectors, and it applies here.

### Upgrading from v0.1.2

No migration needed; no schema changes. Existing libraries keep working. If a
library's `config.json` has no `type`, the next run will state which shape it
inferred — worth a look, since a wrong shape is the failure that motivated the
check.

---

## v0.1.2 and earlier

Not recorded in this format. See the repository history.
