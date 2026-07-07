# Example: an intel-type library ("Home Espresso Log")

This is a **worked example** of an intel-type library — the kind the toolkit builds
when you want to *track a domain over time*. It's here so you (and your agent) can
see what a finished library looks like before building one.

**It's illustrative, not live.** The notes, brief, and ledger contents are crafted
sample data — this example doesn't run a real fetch. When the toolkit builds a real
library, these files get filled from actual collection.

What to look at:
- `config.json` — the filled configuration (topics, sources, thresholds).
- `CLAUDE.md` / `AGENTS.md` — the library's own agent-memory: any agent that opens
  this folder reads it and *becomes the keeper*.
- `keeper.md` — the keeper's full role, instantiated from
  `templates/keeper-instructions.template.md` with the **intel preset**. Note this
  example is a **solo setup**: the owner is also the QC (a common case).
- `briefs/` and `notes/` — Gold: a finalized brief and a curated note.
- `_pipeline/silver/` — a machine-drafted brief awaiting curation (Silver).

For a data/ETL-type library instead (numbers, not notes), see `examples/etl-kb/`.
