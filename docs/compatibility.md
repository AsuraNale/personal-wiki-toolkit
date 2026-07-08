# Compatibility: installing & triggering across agents

`personal-wiki-toolkit` is a plain-Markdown Agent Skill — it works on any agent that
can read files and run scripts. The **universal path always works**:

> **Clone the repo, and tell your AI: "read `SKILL.md` and follow it."**

Native install (below) just adds *automatic triggering*. Per-platform specifics and
known caveats follow (verified against each ecosystem's docs, 2026-07).

## Claude Code
- **Install:** drop the repo folder into your skills directory, or just point the
  agent at the repo ("read github.com/&lt;owner&gt;/personal-wiki-toolkit and help me…").
- **Trigger:** automatic via the `description` in `SKILL.md`, or explicit.
- Native — skills run as a tool with their own context. No caveats.

## OpenClaw
- **Install:** `openclaw skills install git:&lt;owner&gt;/personal-wiki-toolkit`, or copy
  the folder into `<workspace>/skills/`. Takes effect on a **new session** (skills are
  snapshotted at session start).
- **Trigger:** `name` + `description` are injected into the prompt; the model reads
  `SKILL.md` when relevant.
- **Caveats:** no context isolation (the skill runs in your session — long output
  shares the main context); **one skill at a time** (our flow is self-contained in a
  single skill, so this is fine); a `SKILL.md` over **256 KB is skipped** (ours is far
  under). Reference files must use relative paths — the Read tool blocks `..` and
  absolute paths.
- **Publish to ClawHub** (optional): `clawhub skill publish`. Note ClawHub forces
  **MIT-0** and rejects non-text files (**remove `.git/` and `LICENSE`** from the
  bundle), caps the bundle at 50 MB, and requires the account to be at least a week old.

## WorkBuddy (腾讯 CodeBuddy)
- **Install:** GUI → 技能面板 → 添加技能 → 上传技能 (select the repo folder or a zip); or
  place it manually in `~/.workbuddy/skills/`. Officially compatible with OpenClaw
  skill packages.
- **Trigger:** automatic via `description`, or explicit `@<skill-name>`. Put Chinese
  trigger words in the description — its users speak Chinese (建资料库 / 整理资料 /
  搭知识库).
- **Caveats:** WorkBuddy ships a **built-in "本地知识库构建" skill** — make the
  description distinguish this toolkit (dual-layer store + collection pipeline +
  tiered curation + keeper) to avoid trigger collisions. **A Python runtime is not
  guaranteed** — but before falling back to **Level-0 mode**, test `py -X utf8` on
  Windows: bare `python` there is often a Microsoft Store alias that falsely reports
  "not installed", and a real build wrongly went Level-0 despite having Python 3.12
  (see `SKILL.md` § Level-0). Local file access needs the user's explicit
  authorization. If the host runs a **global skill that auto-starts on session
  launch** (e.g. a productivity/todo skill), it can pre-empt the keeper boot — tell
  the agent explicitly to read the library's `CLAUDE.md` + `keeper.md` and adopt
  that role.
- Optionally add `agent_created: true` to the frontmatter so WorkBuddy can edit the
  skill itself (a WorkBuddy-specific field; Claude Code / OpenClaw ignore it — safe to
  add. Keep it OUT of the core repo copy so `skills-ref validate` stays clean; add it
  only in the WorkBuddy-uploaded copy).

## Codex (OpenAI)
- **Install:** copy or link the repo folder into `~/.agents/skills/`. Codex natively
  supports the Agent Skills standard (since 2025-12) and scans `.agents/skills` —
  **not** `.claude/skills`. The repo's `AGENTS.md` also routes clone-and-read usage.
- **Trigger:** explicit `$<skill-name>`, or implicit via `description`.
- **Caveat:** the skill-list injection budget is ~8000 characters across all skills —
  keep the `description` short and precise.

## Level-0 mode (no Python anywhere)
Any host where Python isn't available still works: the library keeps a Markdown index
(`index.md`) instead of SQLite, and the agent uses its own web tools instead of the
fetch scripts. All curation discipline and red lines are unchanged. See `SKILL.md`
§ "Level-0 mode".

---
*One skill package, four ecosystems. The only host-specific asset is the optional
`agent_created` field (WorkBuddy) and a thin `AGENTS.md` (Codex/clone routing) —
everything else is the same plain-Markdown standard.*
