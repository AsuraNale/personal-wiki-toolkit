# Glossary: the toolkit's named models and protocols

Read this when you are about to **change** how the toolkit works — rename a
concept, add a rule, adjust a protocol — or when you need to know what a term in
these docs actually commits you to.

**Why it exists:** without a term list, every version re-invents its own
vocabulary. That is not hypothetical: `type` shipped with **three different value
sets** across `config.example.json`, `SCAFFOLD.md` and `SKILL.md`, plus a fourth
value (`hybrid`) defined nowhere at all. A concept that has no registered name
drifts, and nobody notices until the docs contradict each other.

Each entry answers the same eleven questions, in the same order, so that changing
one is a mechanical operation rather than an archaeology project.

| Field | What it is for |
|---|---|
| **Name** | the handle used in discussion and in docs |
| **Definition** | one sentence, to stop drift |
| **Category** | structural model / judgment protocol / status protocol / **Gate** / **Cadence** |
| **Applies to** | which library shapes — *the field whose absence caused this toolkit's largest documentation defect* |
| **Spec lives in** | the file to edit |
| **Enforced in code by** | changing docs without changing this is a no-op |
| **Does NOT cover** | guards against concept creep |
| **Referenced by** | **every file that must be checked when this changes** |
| **Evidence** | the real incident behind the rule, so a later reader can't mistake a hard-won rule for a style preference |
| **Status** | `active` / `proposed` / `deprecated` |
| **Version history** | traceability |

> **`Referenced by` is measured, not remembered.** Each list below came from
> grepping the repo. Re-grep when you change a concept — the list is a snapshot,
> not a contract. Entries are split into **core** (a stale reference here is a
> self-contradicting spec) and **examples/tests** (must follow, but they are
> illustrations, not rules).

---

## Two categories of "make sure this actually happened"

Several rules in this toolkit exist because an agent can *claim* a step happened.
They split into two kinds, and **the difference is what to do when they fail**:

| | Semantics | On failure |
|---|---|---|
| **Gate** | **blocking** — you may not proceed until it passes | **hard stop**, never degrade |
| **Cadence** | **periodic** — do this every N rounds | you missed a round; **catch up**, nothing is blocked |

Do not file a Cadence as a Gate. "Produce a draft every week" blocks nothing;
"prove you can write files" blocks everything.

### Every Gate needs four things — and the first one is the point

1. **Evidence required** ⭐ — what verifiable artifact is left behind
2. **Triggers before** — which step it must precede
3. **How it is checked**
4. **On failure** — hard stop; degrading is not an option

> **The evidence must be something the agent cannot fabricate alone** — either the
> user confirms it, or it is an artifact left on disk that someone else can
> inspect.
>
> **A Gate without an evidence requirement is a slogan.** The first draft of
> Preflight failed exactly here: its "proof" was a file the agent wrote, read
> back, and then deleted — a closed loop, which `references/qc-rubric.md` § The prime principle ("verify from the
> source, not from the claim") already forbids.

**A Gate is usually not a new door — it is an evidence requirement added to a door
that already exists.** Three of this toolkit's known failures share one shape, and
it is not "the step was skipped":

| Already doing the right thing | What was missing |
|---|---|
| `setup/INTERVIEW.md` § Phase 1 (the Artifact line) demands an explicit "looks good" before scaffolding | no record of it, so nothing can verify it |
| The first Preflight draft did verify write access | it verified itself, then deleted the proof |
| A production stock library's owner really does adjudicate | the verdicts were never written back to the library |

All three **did the work and could not prove it.** Look for the existing door
before building one.

---

## 1. Medallion — `active`

| | |
|---|---|
| **Name** | **Medallion** (三层分层) |
| **Definition** | Bronze (everything seen) → Silver (judged, queued for a human) → Gold (what a human approved) |
| **Category** | Structural model |
| **Applies to** | ⚠️ **Shape A only** (adjudication-type: intel / import). **Not** data/ETL libraries |
| **Spec lives in** | `references/medallion.md` |
| **Enforced in code by** | `scripts/pipeline.py` — `seen` / `silver` tables, `promote` / `dismiss` |
| **Does NOT cover** | Shape B · how items are scored (Curation) · fetch status (Fetch Honesty Protocol) |
| **Referenced by** | **core:** `SKILL.md` · `README.md` · `references/{curation,etl-guide,storage,keeper,qc-rubric,cloud}.md` · `setup/{INTERVIEW,SCAFFOLD}.md` · `templates/{kb-agent-memory,keeper-instructions}.template.md` · `scripts/{pipeline,index_db}.py`<br/>**examples/tests:** `examples/intel-kb/*` · `examples/etl-kb/README.md` · `tests/test_pipeline.py` |
| **Evidence** | Borrowed from data engineering's medallion architecture (`references/medallion.md`, opening section). **Its failure mode is documented**: applied to a data library, Silver silts up — one production recall library sat at 21 Silver rows, 0 promoted / 0 dismissed, while its real table accumulated 567 records around it; the whole scaffold was deleted in the rewrite |
| **Status** | `active` |
| **Version history** | v0.1.2 as shipped · **v0.1.3 adds the "applies to" limit** (it previously claimed universal scope) |

## 2. Shape B (accumulation-type) — ⚠️ `proposed`

| | |
|---|---|
| **Name** | **Shape B** (累积型) — *deliberately descriptive; see Status* |
| **Definition** | Fact (auto-appended, **final on write**) → Derived (recomputable, **never hand-edited**, not a source of truth) → Conclusion (human-authored = Gold) |
| **Category** | Structural model |
| **Applies to** | data / ETL libraries |
| **Spec lives in** | `references/medallion.md` § *Shape B — accumulation* (written in v0.1.3). `references/etl-guide.md` § *Raw observations auto-append* carries the data-library framing and points here |
| **Enforced in code by** | nothing. Data libraries do not run `pipeline.py` at all (`examples/etl-kb` references it zero times; `SKILL.md` § Start here: route the request — "there is no one-click scaffold") |
| **Does NOT cover** | relevance scoring · per-row human promotion (**explicitly forbidden here**) |
| **Referenced by** | **core:** `references/etl-guide.md` § Raw observations auto-append; only analysis is curated<br/>**examples:** `examples/etl-kb/` |
| **Evidence** | `references/etl-guide.md` § Raw observations auto-append — a real build gated raw snapshots behind human promotion by *proposing* weekly `INSERT`s; **the table never grew a second data point.** Separately: **four highly active libraries with no draft step produced zero human Gold** (420 rounds/1,109 rows · 165/89,136 · 127/297 · 44/9,533) |
| **Status** | ⚠️ **`proposed`** |
| **Version history** | Formulated 2026-07-27. **Named descriptively on purpose**: the concept was revised twice during the very discussion that produced it, it is not implemented anywhere, and a coined term would freeze it early. **Name it properly after 2–3 real libraries have run on it.**<br/>**Correction (v0.1.4):** the message on `9a6ac6f` said the "spec lives nowhere yet" contradiction was one "this commit created". It was not. `git log -S` places the Shape B section in `medallion.md` at `535d71f`, several commits earlier, so the contradiction shipped inside v0.1.3 itself. The fix was right; the attribution was wrong, and a wrong attribution sends the next reader looking in the wrong release |

## 3. Curation — `active`

| | |
|---|---|
| **Name** | **Curation** (判读规范) — *the existing file title; not a new coinage* |
| **Definition** | The complete discipline for scoring a candidate's relevance: output contract + judging rules + anchor values + calibration + dedup + echo-chamber defense |
| **Category** | Judgment protocol |
| **Applies to** | Shape A (adjudication). Data libraries validate on write instead — a different thing |
| **Spec lives in** | `references/curation.md` (**already complete — it was simply never registered**) |
| **Enforced in code by** | `scripts/pipeline.py` — the `how_to_judge` handoff text and the judgment contract `{url, relevance, one_line, topic}`, both written by `write_pending()`; the threshold comparison in `cmd_apply()` |
| **Does NOT cover** | the threshold **value** (that is `config.thresholds.keep`) · **auditing the library's quality** (that is `qc-rubric.md` — do not conflate the two; this is why the proposed name "Curation Rubric" was rejected) |
| **Referenced by** | **core:** `SKILL.md` · `references/{medallion,keeper,qc-rubric,storage}.md` · `setup/{INTERVIEW,SCAFFOLD}.md` · `scripts/pipeline.py`<br/>**examples/tests:** `examples/intel-kb/{CLAUDE,AGENTS}.md` · `tests/test_pipeline.py` |
| **Evidence** | Two production judges initially scored anything containing a keyword at 0.8+, reaching only ~69% agreement with human judgment; nearly all misses were keyword-baited. Hence "judge substance, not keywords" and the low-score-when-unsure anchors |
| **Status** | `active` |
| **Version history** | Formed in v0.1.2 · v0.1.3 **registers it** and closes two holes (threshold-tuning loophole; status distortion) |

## 4. Fetch Honesty Protocol — `active`

| | |
|---|---|
| **Name** | **Fetch Honesty Protocol** (采集诚实协议) |
| **Definition** | Every fetch lands in exactly one of five states — `ok / empty / gap / failed / blocked` — **each of which implies a different fix** |
| **Category** | Status protocol |
| **Applies to** | ⭐ **every library type.** This is the one thing with cross-type code-reuse evidence |
| **Spec lives in** | `references/pipeline-discipline.md` § *A failed fetch is not an empty result* |
| **Enforced in code by** | `scripts/fetch_rss.py` (`FetchGap` / `FetchFailed` / `FetchBlocked` + two-layer classification) · the `fetch_log` table · the health banner in `scripts/pipeline.py` · assertions in `tests/test_pipeline.py` |
| **Does NOT cover** | content quality · relevance · tiering |
| **Referenced by** | **core:** `SKILL.md` § *A failed fetch is not an empty result* · `MANUAL.md` · `references/{pipeline-discipline,etl-guide,medallion,storage,cloud}.md` · `setup/SCAFFOLD.md` · `scripts/{fetch_rss,pipeline}.py`<br/>**examples/tests:** `examples/etl-kb/{fetch_quakes.py,CLAUDE.md,keeper.md}` ← **the cross-type reuse evidence** · `examples/intel-kb/*` · `tests/test_pipeline.py` |
| **Evidence** | A cloud round lost **7 of 8 sources** to egress policy and still "succeeded" — only the health banner revealed the brief had been built from the single source that happened to be allowed. Before `blocked` existed, that same denial was filed as `gap`, i.e. the user was told to fix a config that was already correct |
| **Status** | `active` |
| **Version history** | v0.1.1 four states → **v0.1.2 adds `blocked`** (policy refusal ≠ "nothing there" ≠ "retry later") |

## 5. Preflight — ⏸️ `deferred`

| | |
|---|---|
| **Name** | **Preflight** (准入自检) |
| ⏸️ **Status note** | **Withdrawn in v0.1.4, two weeks after shipping.** Not deleted: the failure it was built for is real and the constraint it ran into is the hard part of any future attempt — see Evidence and Version history below |
| **Definition** | Before anything else, establish that this agent can really create files **on the user's machine** |
| **Category** | **Gate** |
| **① Evidence required** ⭐ | **An artifact the user has looked at with their own eyes**, in a location the user knows |
| **② Triggers before** | everything — before `find_root()`, before reading config |
| **③ How it is checked** | three stages, each catching a different failure: **1** state the absolute path (E3 if none) → **2** write `.pwt-capability-check`, read back, compare verbatim (E1 unreadable/mismatched, E2 refused) → **3** ⭐ **the user opens that path and confirms the file is there** (E4 if not). Probe is deleted only *after* stage 3 |
| **④ On failure** | **hard stop** + tell them what to switch to. ⛔ Never degrade to "I'll simulate one in chat" |
| **Applies to** | every library type |
| **Spec lives in** | `SKILL.md` (v0.1.3) |
| **Enforced in code by** | nothing — it must run before any script can (`find_root()` raises `SystemExit(2)` without a config, and the existing `.selftest-probe` sits **inside** `cmd_selftest()`'s `if config is not None:` guard — so it cannot run until a config already exists, which is exactly when an entry check is too late) |
| **Does NOT cover** | whether Python exists (that is Level-0 detection) |
| **Referenced by** | **none in the active flow.** Re-grepped after the v0.1.4 withdrawal: the only remaining mentions are historical — `CHANGELOG.md` / `CHANGELOG.zh.md` (the v0.1.3 entry, kept as shipped history, plus the v0.1.4 withdrawal) and `README.md` (a one-line pointer to that entry). `SKILL.md`, `MANUAL.md` and `MANUAL.zh.md` no longer mention it |
| **Evidence** | A user ended a session believing a library had been built, in an assistant with no filesystem at all. **And the naive fix fails too**: a write-read-compare probe passes inside a sandbox/cloud container whose files never reach the user's machine — an agent cannot prove from its own side that "where I wrote" equals "where the user looks" |
| **Status** | ⏸️ **`deferred`** — shipped v0.1.3, withdrawn v0.1.4, no target version |
| **Version history** | v0.1.3 shipped it (first draft used probe-only self-verification and was **rejected for violating `references/qc-rubric.md` § The prime principle**). **v0.1.4 withdrew it** — it broke the setup flow, and the users it would have turned away are ones this toolkit does not aim to serve. ⚠️ **The constraint outlives the withdrawal**: an agent still cannot prove from its own side that where it wrote is where the user looks. Any future attempt starts from that, not from a better probe |

## 6. Intake — 🆕 **Gate**

| | |
|---|---|
| **Name** | **Intake** (需求受理) |
| **Definition** | Turn a vague request into a structured, **recorded** set of decisions before any library is built |
| **Category** | **Gate** |
| **① Evidence required** ⭐ | **The user's own words / selections written into `config.json`**, each marked with who decided it |
| **② Triggers before** | scaffold (and after Preflight) |
| **③ How it is checked** | every setup choice carries `decided_by`. **`agent-inferred` anywhere → stop**; `default-accepted` outside cadence/threshold/keeper → stop. `default-accepted` is only truthful if you stated the default *and its effect* |
| **④ On failure** | **do not scaffold** — go back and ask |
| **Applies to** | every library type |
| **Spec lives in** | `setup/INTERVIEW.md` + `setup/IMPORT.md` (v0.1.3) |
| **Enforced in code by** | **nothing** — no script reads `$intake` (`git grep -i intake` over `scripts/` and `tests/`: zero hits). `cmd_selftest` does read `config.json`, but only checks name/sources/paths, `type`, source shape, threshold, pipeline-dir writability and the db schema. If this is ever enforced, it must be **graded, not added to the required-key loop**: a missing `$intake` is a warning (no v0.1.2 library has one — the same tolerance `cmd_selftest` already extends to a missing `type`), while `agent-inferred` is a failure |
| **Does NOT cover** | how the need evolves *after* the library exists |
| **Referenced by** | **core:** `SKILL.md` · `README.md` · `setup/{INTERVIEW,IMPORT,SCAFFOLD}.md` · `templates/config.example.json` · `templates/start-here.template.md` |
| **Evidence** | Models already ask a question or two on their own, so "did it ask" is not the differentiator — **"can anyone check that it asked" is.** `setup/INTERVIEW.md` § *Phase 1* already *demands* confirmation ("Do not proceed to Phase 2 without an explicit 'looks good'") but **requires no record of it**, so nothing can verify it happened. The toolkit was also pushing the other way, which **v0.1.3 fixed (FIX-12)**: Phase 1 was headed `aim: ≤3 exchanges` — a question budget — and told the agent to surface cadence and threshold "only if the user seems opinionated", while the threshold is Curation's core parameter and governs what the library will never show them |
| **Status** | ⏸️ **`deferred`** — shipped v0.1.3, withdrawn v0.1.4, no target version |
| **Version history** | v0.1.3. **Not a new gate — it gives an existing one an evidence requirement.** Ships the cheap version (record the user's own words in config); full structured confirmation deferred |

---

## Registered Cadences

| Name | Definition | Spec | Evidence |
|---|---|---|---|
| **Draft cadence** (Shape B) | Produce a Silver draft document on a fixed trigger (e.g. end-of-day, weekly), so a human has something concrete to adjudicate | v0.1.3, `references/medallion.md` + `setup/SCAFFOLD.md` | A draft step is **necessary but not sufficient** for Gold: four highly active libraries with no draft step produced **zero** human Gold; and one library with 3,000 rounds and 21 drafts still shows zero, because its verdicts were never written back |

---

## Changing any of this

1. **Read the `Referenced by` row first, then re-grep** — it is a snapshot. Changing `medallion.md` alone touches every core file listed on its card — the hand-written version of that list missed more than half of them. **Count from the row, never from a number written in prose**: a hard-coded count is one more thing that silently goes stale (this sentence said "sixteen" while the row listed 14).
2. **Check `Enforced in code by`** — a doc change with a code enforcement point is only half done.
3. **Never delete a rule whose `Evidence` row names a real incident** without saying what changed about that incident. That row exists because a later reader will otherwise mistake a hard-won rule for a style preference.
4. **Anything `proposed` is not settled** — do not build on it as if it were.
