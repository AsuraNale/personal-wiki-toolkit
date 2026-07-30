# QC rubric: how to check this library is actually good

Read this before declaring any setup step "done", and give it to the user —
it is THEIR audit tool over YOU and any keeper. Every check here was used in
production to catch a real failure; none is theoretical.

## The prime principle: verify from the source, not from the claim

Whoever checks quality must not accept the builder's own summary as
evidence. Concretely:
- re-derive numbers from the ledger/index yourself (`pipeline.py stats`,
  direct queries), don't quote the report you're auditing;
- sample items the builder did NOT showcase (pick randomly, not from the
  examples it offered);
- for every "0 / empty / no data" claim, ask: **genuinely empty, or a
  failure misread as emptiness?** (One production system reported "this
  source has no data" for weeks; the fetch was 504ing. Another agent's
  self-check "passed" because it fed its own wrong assumption into the
  checker's prompt.) Never put the conclusion you're testing into the test.

## Rubric A — intel-type library health

Run monthly, or whenever the user doubts the library. ~15 minutes.

| # | Check | How | Pass bar |
|---|---|---|---|
| A1 | **Judgment calibration** | User blind-scores 10 random machine-judged items (mix of kept + rejected), compare | agreement ≥ ~80%; misses analyzed (keyword-bait pattern? threshold drift?). ⛔ **Diagnose before you touch the threshold** — see the note below the table |
| A2 | **No fabrication** | Pick 5 random Gold notes/brief entries → follow every source link | every claim traceable to its source; dead links flagged, not silently kept. **Also check the status words**: a figure the source called a *target/forecast* must not read as *achieved* in the note — same digits, different claim |
| A3 | **Noise floor** | Read the latest 2 briefs cold | ≥⅔ of entries genuinely worth the owner's attention; if not, judging went soft (→ curation.md) |
| A4 | **Flow** | `pipeline.py stats`: Silver ages | nothing waiting > 2 weeks; dismissals carry reasons |
| A5 | **Dedup** | stats: duplicate-key hits across layers | no repeated story surfacing as "new" twice |
| A6 | **Coverage honesty** | compare topics in config vs what actually arrived | topics that fetch nothing are flagged as gaps, not quietly ignored |
| A7 | **Failure hygiene** | logs: any FETCH-FAIL entries | failures were retried or reported — never converted into "source was empty" |

## Rubric B — data/ETL-type library health

For structured-data libraries (see `etl-guide.md`). Run after every build
and monthly after.

| # | Check | How | Pass bar |
|---|---|---|---|
| B1 | **Source-of-truth sampling** | pick N random stored values → re-fetch/compare against the origin (API/site) | exact match, or documented transform |
| B2 | **Derived values recompute** | hand-recompute a few derived fields (ratios, aggregates) from stored raw values | matches stored derivation |
| B3 | **Empty vs failed** | for every empty table/series: check the fetch log | emptiness has a positive explanation (source confirmed empty), never inferred from an error |
| B4 | **Idempotency** | run the fetch twice | second run adds nothing, changes nothing |
| B5 | **No silent truncation** | anywhere the system caps/paginates/samples | the cap is stated in output ("showing 50 of 740"), never implied completeness |
| B6 | **Degradation honesty** | items that can't be computed (missing inputs) | shown as N/A with a reason — never a plausible-looking wrong number |

## Before you grade anything: where does the ground truth live?

Not every check is the same kind of claim, and treating them alike is how a QC
round ends up asserting things it cannot know. Ask where the correct answer
actually exists:

| Ground truth lives | Checks | What a verdict means |
|---|---|---|
| **In the ledger** | A4 · A5 · A6 · A7 | You can settle these yourself — the number is computable. Take it from `pipeline.py evidence`, don't retype it |
| **In an external source** | A2 | You can settle it by going and looking — follow the link |
| ⚠️ **In the owner's head** | A1, and the first half of A3 | **You cannot pass these alone.** "Is this relevant to me?" has no answer inside the library |

**So a QC round run entirely by the agent legitimately ends with A1 unresolved,**
and `skipped — needs the owner` is the correct verdict there, not a gap in the
work. Recording it as a pass is the failure; recording it as skipped is the rubric
working.

> This is a principle, not yet a pass/fail change: A1's bar isn't being redefined
> here. Tightening it needs `_pipeline/calibration.jsonl` to have accumulated real
> data first — a gate with no data behind it is a gate in name only.

## Auditing an agent's work (the meta-rubric)

When the user asks "is my keeper doing a good job?" — or when YOU audit a
previous session's work:

1. Ask for claims with evidence pointers (ledger rows, file paths, source
   URLs). A report that can't point is a finding in itself.
2. Reproduce 2–3 claims from the raw data yourself.
3. Test with material the agent didn't choose: pick your own sample.
4. Check the red lines mechanically: any note without a source? any dismiss
   without a reason? any owner-authored file with machine edits?
5. Grade the *system*, not the day: one bad judgment is noise; a pattern
   (every miss is keyword-bait; every "done" lacks evidence) is the finding.

## ⛔ Never tune the threshold to make a score go up

A1 can be "passed" by lowering the keep-threshold until agreement improves. That
changes the number without changing the judging, and it makes the library worse
while the report looks better.

**Fixed order when A1 fails:**

1. **Read the misses.** What do they have in common — keyword-bait? one source
   dominating? a topic whose keywords stopped matching how people write?
2. **Fix the judging**: sharpen the topic keywords, re-read `curation.md`, correct
   the anchor values you were using.
3. **Re-score the SAME items** and compare against the same human scores.
4. **Only then**, if the shape of the disagreement genuinely says so, adjust the
   threshold — and **record what you changed and why** in the QC report.

**⛔ Never re-run a check with an adjusted parameter and report the second number
as if it were the first.** A metric moved by changing the measurement is not an
improvement; if the threshold changed, the QC report says so next to the score.

**⛔ And the threshold is not yours to move.** It decides what the library will
never show its owner, so changing it is an owner decision, not a QC finding:
propose it with the evidence ("agreement was 6/10; the four misses were all X"),
and **wait for an explicit yes**. Recording a unilateral change is not the same as
being allowed to make one — a QC round that both moved the parameter and graded
the result has audited itself.

## Reporting QC results

State what was checked, what passed, what failed **with the evidence**, and
what changes as a result (threshold tweak, curation.md re-read, keeper.md
amendment). A QC round that ends in "all good 👍" with no numbers attached
did not happen.

**Use `templates/qc-report.template.md`** — it has a row per check with a column
for the actual number or quote, a place to record what changed, and an explicit
`skipped` verdict so a check you didn't run can't quietly read as one that passed.

## ⚠️ "The file was produced" is not "the file is correct"

When a check produces a rendered artifact — an exported document, a generated
index, a chart, a converted file — **open it and look**. Generation succeeding
says nothing about the content being right:
- **follow the links** (conversion is where links get mangled, split, or silently
  re-pointed)
- check the numbers survived formatting (thousands separators, dates, currency)
- confirm it isn't truncated at the end

Report what you *looked at*, not what you *generated*.
