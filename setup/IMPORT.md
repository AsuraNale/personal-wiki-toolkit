# Import: organizing an existing pile of files

The user has existing material (a folder, a vault, an export). Your job:
give it structure and an index **without endangering a single file**.

**Prime directive: their files, not yours.** Default mode is *index in
place* — you build structure and index AROUND the files. Physically moving
files happens only after an explicit, reviewed plan and confirmation
(SKILL.md rule 4).

---

## Step 1 — Scan (cheap first, never read everything)

1. Enumerate: full file listing with sizes/dates (glob-style walk). Report
   the shape: how many files, which types, size distribution, obvious
   clusters by folder or naming pattern.
2. Sample: read a FEW representative files per apparent cluster (3–5 each),
   plus any README/index-like files entirely. Do NOT bulk-read a large
   corpus into context — sampled understanding is enough to classify.
3. If the pile is >1–2k files, say so and propose working cluster-by-cluster.

## Step 2 — Propose

Produce a classification proposal the user can react to:

- a category tree (aim 5–12 top categories; deeper only where a cluster is
  big), with 3 example files listed under each;
- an explicit **"unsorted" bucket** — never force-classify; uncertain items
  go there honestly;
- for each category: one line on what belongs in it (this becomes the
  library's own documentation later);
- the mode question, asked plainly: **index in place** (default — files stay
  where they are; the library holds the index + new notes) or **physical
  reorganization** (files are moved into the new tree — requires the full
  move plan to be shown and confirmed first, and you create the plan as a
  reviewable list, never move-as-you-go).

Iterate the proposal until the user approves it.

## Step 3 — Execute

- **Index-in-place mode:** create the library skeleton next to (not inside)
  the user's material unless they say otherwise; then build the index over
  the existing paths.
- **Move mode:** write the complete move manifest (old path → new path) to a
  file, show it, get confirmation, then execute in batches with a progress
  report per batch; verify counts afterwards (files before == files after —
  show the numbers).
- Either mode: run `setup/SCAFFOLD.md` for the library shell (config, memory
  file, databases), with `type: "import"`.

## Step 4 — Index & report

1. Build the index: `python scripts/index_db.py build` (or Level-0
   `index.md` table). The index rows carry: title, path, category, tags,
   dates found in the file, and outbound links if the format has them.
2. Produce a **coverage report** for the user: items per category, date
   range per category, orphans (files that matched no category → unsorted),
   and anything that failed to parse (named explicitly — no silent skips,
   per SKILL.md rule 6 in spirit: a parse failure is not "not there").

## Step 5 — Offer to make it live (optional)

An organized pile is a snapshot; ask whether they want it to grow: "Want
this library to collect new material about these topics automatically?"
If yes → jump to `setup/INTERVIEW.md` Phase 1 items 2–5 (topics from the
categories you just built are usually a good draft), then its Phases 2–4.
If no → still finish with the care guide + handover (INTERVIEW.md Phase 4,
minus pipeline-specific parts).
