# Interview: building an intel-type library from scratch

You are running a guided setup. The user wants a library that **tracks a
domain over time**. Your job across four phases: understand → generate →
prove it works → hand over. Conduct everything in the user's language.

**Style rules for the whole interview:**
- Propose, don't interrogate: draft something concrete from what the user
  said, show it, let them react. One batched follow-up beats five questions.
- Every phase ends with a visible artifact the user can inspect.
- Don't over-promise: this library will be as good as its sources and its
  curation habit. Say so once, plainly.

---

## Phase 1 — Understand the need

Keep it short — but **let the record decide when you are done, not a question
count.** Phase 1 is complete when every item below is settled *and marked with who
settled it* (see **Intake** at the end of this phase). Batching several choices
into one message is how you keep it brief. Deciding on the user's behalf is not.

Collect, in whatever order the conversation allows:

1. **Domain and angle.** Not just "AI" but *what about it* — "agent tooling
   for practitioners" reads very differently from "AI policy for a lawyer".
   Ask what decisions or output this library should feed (research? writing?
   investing? hobby depth?). The angle drives topic design and judging.
2. **Topics** (3–6). Draft them yourself from the domain + angle, each with
   2–4 search keywords. Keywords must be *searchable strings that would
   actually appear in titles*, not abstract category names. Show the draft
   table; let the user edit.
3. **Sources.** ⚠️ **Ask what they already read before you recommend anything.**
   The spec has always said to ask for 2–5 feeds the owner follows; a real build
   never asked, chose all five itself, and recorded them as `user-selected`. Their
   own sources are the best signal you will get, and they are the one thing you
   cannot infer.

   **Take whatever form they can give**, and record how it arrived:

   | They give you | `decided_by` | Your job |
   |---|---|---|
   | a pick from your list | `user-selected` | — |
   | a URL | `user-typed` | — |
   | **a site name** ("that site X") | `user-typed` | **find its feed** |
   | **a rough area** ("the government announcements") | `user-typed` | **turn it into concrete sources** |

   For the last two: **read back what you resolved it to, and get a yes** — "you
   said the government announcements; I found this feed, is that the one?" Resolving
   a vague answer without reading it back is deciding for them again, in a new shape.

   Then recommend by domain to fill the gaps:
   - academic-flavored → arXiv queries (exact-phrase keywords);
   - tech/startup-flavored → Hacker News (Algolia search, min-points filter);
   - any domain → RSS/Atom feeds of the blogs/newsletters/news sites the user
     already reads (ask them for 2–5; these are usually the best signal);
   - avoid: anything paywalled or ToS-hostile (SKILL.md rule 5).
   - **also avoid Cloudflare-protected sites** — some news sites (e.g. Videocardz)
     return HTTP 403 to the polite stdlib fetcher; the pipeline correctly marks them
     `gap`, but they simply won't collect. Prefer a site that serves an open RSS/Atom
     feed; when in doubt, the first fetch will tell you (`gap` vs `ok`).
   Aim for 3–8 sources total. More sources ≠ better — every source adds noise
   to judge. Verify each feed actually fetches on the first run — swap out any
   that come back `gap`.
4. **Cadence & threshold.** Defaults: daily collection, keep-threshold 0.7.
   **Say both defaults out loud, with what they mean**, then let the user accept
   them — most will, and that is fine. What is not fine is deciding silently:
   the threshold governs *what this library will never show them* (anything you
   score below it stays in Bronze, invisible), so picking it on their behalf
   without saying so is not a shortcut — it is an unannounced edit to everything
   they will ever see. Accepting a stated default is a decision; never being told
   is not.
5. **Keeper?** Default yes: a named librarian role with written duties
   (`references/keeper.md`). **This is the library's maintainer, not a chat
   persona** — it is who decides what gets promoted, notices what has gone stale,
   and reports what changed. A library with nobody tending it starts decaying the
   day it is built, and nothing in the tooling will tell you.
   If the user declines, **say that plainly** — "then the upkeep is yours: the
   brief needs skimming and Silver needs clearing, or the library silts up" — and
   record it as `keeper: {"value": false, "decided_by": "user-selected"}`. A
   declined keeper is a decision the user made knowingly, not a step that quietly
   didn't happen.

**Artifact:** a filled `config.json` draft (schema:
`templates/config.example.json`), shown to the user for one confirmation
pass. Do not proceed to Phase 2 without an explicit "looks good".

### Intake — record who decided what (Gate: blocks scaffolding)

That confirmation above has always been required. What was missing is any **record
of it**, which means nobody — not the user, not a reviewer, not you next week —
can tell whether it happened. Fix that by writing the decisions into the config
you are already producing:

```json
"$intake": {
  "domain":    { "value": "agent tooling for practitioners", "decided_by": "user-typed" },
  "topics":    { "value": ["…"],  "decided_by": "user-selected" },
  "sources":   { "value": ["…"],  "decided_by": "user-selected" },
  "cadence":   { "value": "daily", "decided_by": "default-accepted" },
  "threshold": { "value": 0.7,     "decided_by": "default-accepted" },
  "keeper":    { "value": true,    "decided_by": "user-selected" }
}
```

**Three values, and the line between them is whether the user knew:**

| `decided_by` | Means | Allowed on |
|---|---|---|
| `user-typed` / `user-selected` | they said it, or picked it from options you offered | anything |
| `default-accepted` | **you stated the default and its effect**, and they took it | `cadence`, `threshold`, `keeper` only |
| ⛔ `agent-inferred` | you decided quietly; they never knew it was a question | **nothing — this is the failure** |

**Shape is one of the recorded decisions.** Which shape this library takes —
adjudication (Bronze→Silver→Gold) or accumulation (Fact→Derived→Conclusion) —
changes the scaffold, the tier rules, and what the keeper does. **It is not yours
to settle quietly.** Say which you think it is and why, in one line the owner can
disagree with:

> "This looks like a **tracking** library — items arrive, you decide what's worth
> keeping. The other kind is for **numbers over time**, where rows just accumulate
> and you write conclusions on top. Sound right?"

Record it as `shape` in `$intake`, with the same `decided_by` rules as everything
else. **A library whose shape was never discussed is the one failure mode with a
name**: one real tracker was configured `intel` while its actual work was a price
table — the intel scaffold sat empty beside the data it never touched, and nothing
in the flow noticed, because nobody was ever asked.

**The check, before you scaffold:**
- any field marked `agent-inferred` → **stop, go back and ask**
- `domain` / `topics` / `sources` marked `default-accepted` → **stop**; these have
  no sensible default, so a "default" there means it was really inferred

**`default-accepted` is not a free pass.** You may only write it if you actually
said the default *and what it does* — "the threshold defaults to 0.7, so anything
I score below that stays out of sight" — not if you merely defaulted internally.

⚠️ **Text you drafted is never `user-selected`, even when the user said yes to it.**
A real session put the keeper's top red line — which the agent had proposed itself
("let me suggest we write it as…") — under `decided_by: user-selected`, alongside
genuine yes/no answers. Approving wording you wrote is weaker evidence than
choosing it, and burying the two in one field hides which is which.

So: **any value that is free text you drafted goes in its own key, marked
`default-accepted`** — never merged with the user's own choices. If the user
rewrote it in their words, *then* it is `user-typed`. The test is not "did they
agree" but **"whose words are in the file"**.

**Why record rather than force a choice:** asking a first-time user to pick
between 0.6 / 0.7 / 0.8 is a fake choice — they have no basis yet. **Telling them
is more honest than making them choose.** But telling them and recording that you
told them is the part that has to be true.

> Prefer options over open questions wherever the answer is enumerable — you draft
> the topics and sources, the user ticks and edits. That is not only easier for
> them; a set of ticked options is **checkable later**, and free text is not.

---

## Phase 1.5 — One design confirmation, before anything is built

Three things used to be settled without ever being shown: which **shape** the
library is, what **structure** it gets, and which **sources** feed it. Each was a
place where the flow simply continued with nobody having looked.

Do not ask about them three times. **Show all three once**, in one message the
owner can react to:

```
Here's what I'd build for you:

  SHAPE     A tracking library — things arrive, you decide what's worth keeping.
            (The other kind is for numbers over time. Say if that's closer.)

  STRUCTURE my-kb/
              notes/agent-tooling/    ← one folder per topic
              notes/evals/
              briefs/                 ← what I write for you each round
              _pipeline/              ← my working area; you can ignore it

  SOURCES   • Simon Willison's blog        (you named this one)
            • Hacker News, ≥50 points      (my suggestion)
            • arXiv: "agent memory"        (my suggestion)

Anything you'd change?
```

**If they want changes, go back to Phase 1** and re-show. That loop is the point:
it is cheaper to redraw this than to rebuild a library.

**Why one message and not three:** every question costs the owner their place in
what they were doing. Three separate confirmations interrupt three times *and*
still leave the gaps, because two of the three were never asked at all. One
message, one interruption, nothing settled behind their back.

---

## Phase 2 — Scaffold

Read `setup/SCAFFOLD.md` and execute it with the confirmed config. Summary of
what it produces (details there): library directory tree, `config.json`, the
library's own `CLAUDE.md`/`AGENTS.md` memory file, SQLite databases (or
Level-0 index), instantiated scripts, and — if the user wants automation —
platform-specific schedule registration instructions (the user runs those
themselves; scheduled-task registration is often privileged).

**Artifact:** the tree, printed, with one line per item explaining what it is.

---

## Phase 3 — First run (never skip; never "set up now, run later")

An unproven pipeline is a broken pipeline. Walk it end to end NOW:

1. Run the fetch: `python scripts/pipeline.py fetch` (from the library root).
   It writes `_pipeline/pending.json` — the judgment queue. If zero items
   arrive, treat it as a problem to diagnose (source config? network? — see
   `references/pipeline-discipline.md`), not something to shrug at.
2. **You are the judge now.** Read `references/curation.md` (judging criteria
   + output format), score every pending item, write
   `_pipeline/judgments.json`.
3. Apply: `python scripts/pipeline.py apply`. This moves keepers into Silver
   and writes the draft brief (`_pipeline/silver/AUTO-<date>.md`).
4. Show the user the brief. Then the **teaching moment** — do these two
   actions *with* them, not for them:
   - pick the best item together → `python scripts/pipeline.py promote <url>`
     → show them where it landed (Gold) and how the index reflects it;
   - pick the weakest item → `python scripts/pipeline.py dismiss <url>
     "<reason>"` → explain that dismissed items never resurface, and the
     reason is kept for audit.
   These two verbs are 90% of the curation the user will ever do by hand.

**Artifact:** first brief + one promoted note + one dismissal, all real.

**Level-0 variant:** same loop, but you fetch with your own web tools, keep
`_pipeline/seen.md` as memory, and append to `index.md` instead of applying
to SQLite.

---

## Phase 4 — Handover

1. If keeper enabled: run the full keeper setup in `setup/SCAFFOLD.md` §7
   (name it → pick type preset → "what's the worst mistake it could make?" →
   instantiate `templates/keeper-instructions.template.md` as `keeper.md` →
   first-run rite: verify the library map against the REAL library → hand off).
   Role definition: `references/keeper.md`.
2. **Introduce the keeper, and let the owner name it.** ⚠️ Not "I've enabled a
   keeper called X, keep it?" — in two real builds the agent chose the name and the
   owner was left approving it, which was then recorded as their decision.

   Have the keeper introduce itself in three short beats:

   > "I'll be looking after this library: I collect on the schedule we set, score
   > what comes in, and keep the index honest. **Ask me anything about what's in
   > here — that's what I'm for.**
   >
   > Right now **54 items are waiting for your verdict**. Whenever you feel like
   > it, tell me which are worth keeping and I'll write them up properly. **Leaving
   > them costs nothing** — I keep collecting either way.
   >
   > What would you like to call me?"

   Three things happen in that one message, at no extra cost:
   - **It says what state the library is in** — the handover obligation from red
     line #7. Take the count from `pipeline.py evidence`; don't type it from memory.
   - **It explains what happens next** without a vocabulary lesson. ⛔ **Do not say
     "Bronze", "Silver" or "Gold" to the owner.** Those words appear nowhere in the
     manual — they are ours, not theirs. Say *waiting for your verdict* and *written
     up properly*. One owner who personally promoted 39 items still could not
     recall which tier was which; the words are not what makes it usable.
   - **Naming is the owner's.** Record it `user-typed`. A name someone chose is a
     thing they own; a name they approved is a thing you chose.

   ⚠️ **Naming is not the same as setting its red lines.** If you draft the keeper's
   top red line, that text is yours — record it `default-accepted` under its own key
   (`setup/INTERVIEW.md` § Intake), never merged with what the owner actually picked.

3. Write **`START-HERE.md`** from `templates/start-here.template.md` — the file
   the owner opens when they've forgotten how this works. ⚠️ **Test every
   suggested question against the real library first**: one that returns nothing
   teaches them the library is useless. For ≥3 topics also instantiate
   `templates/notes-index.template.md`.
4. Give the user the **one-page care guide** (write it into the library as
   `CARE.md`, in their language):
   - daily/whenever: skim the new brief (2 min);
   - promote what deserves permanence, dismiss what doesn't — with reasons;
   - weekly: ask the library agent "what's new, what's stale, and any
     demand-board candidates?" (coverage + emergent-topic proposals);
   - monthly: skim `references/qc-rubric.md` checks — or just ask the agent
     to run a self-audit and show evidence.
5. Remind them: the toolkit repo can be deleted; the library is
   self-describing via its own memory file. Updates to the toolkit can be
   re-applied by re-reading it against an existing library (idempotent
   scaffold).
6. State honestly what was NOT set up (e.g. schedule not registered yet, or
   Level-0 mode) and what the user must do for it.

Done means: the user watched the loop run once, touched promote/dismiss with
their own hands, and knows the three care actions. Anything less is not done.
