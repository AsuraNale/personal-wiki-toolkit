# Personal Wiki Toolkit · 个人Wiki工具包

> Build, feed, and curate your personal wiki — with an AI librarian that
> never skips QC.
> 让 AI 管家帮你从零建库、持续喂库、按纪律策展。 · 中文用户:[使用说明书 MANUAL.zh.md](MANUAL.zh.md)

An **agent skill toolkit** that interviews you (or ingests your existing
folders) to build a personal knowledge base from scratch — Markdown + SQLite
dual-layer storage, an automated intelligence-collection pipeline,
Medallion-tier curation, a librarian agent role, and QC rubrics. Works across
**Claude Code, Tencent WorkBuddy, and Codex** — plus OpenClaw, which follows the
same skill format but hasn't been run end-to-end (any agent that can read
markdown and run scripts, really).

📖 **Not a developer? Start with the [manual](MANUAL.md)** — a plain-language
walkthrough (no code) with a worked example, an honest local-vs-cloud comparison,
and troubleshooting. 中文说明书:[MANUAL.zh.md](MANUAL.zh.md)。

🛡️ **Letting an agent fetch from the open web on your behalf?** Read
[SAFETY.md](SAFETY.md) — what the toolkit commits to, where the injection rule is
enforced, and what it explicitly does *not* protect you from. 中文:[SAFETY.zh.md](SAFETY.zh.md)。

## Use it in one sentence

Tell your AI agent:

> Read https://github.com/<owner>/personal-wiki-toolkit and help me build a
> knowledge base for <your topic>.

That's it. The agent reads `SKILL.md`, interviews you (or scans the folder
you point it at), scaffolds the library, runs the first collection round
**with you watching**, and hands you a one-page care guide. The toolkit is
disposable afterwards — your library carries its own instructions.

给你的 AI 助手发一句:「读一下这个 repo,帮我建一个关于 XX 的资料库」即可。

## What you end up with

```
my-kb/
├── CLAUDE.md / AGENTS.md   ← the library explains itself to any agent
├── notes/  briefs/          ← Gold: curated, cited, permanent
├── _pipeline/silver/        ← machine-drafted, awaiting your verdict
├── kb.db  intel.db          ← index + collection ledger (SQLite)
├── scripts/                 ← fetch / judge-apply / promote / dismiss / index
└── keeper.md                ← your librarian's duties and red lines
```

- **Dual-layer**: humans read Markdown; queries hit SQLite.
- **Medallion curation**: everything enters Bronze, machine judgment fills
  Silver, only explicit promotion makes Gold. Dismissals carry reasons.
- **The agent is the judge** — no extra API keys, works with whatever model
  hosts it.
- **Demand-driven growth**: the keeper logs what you keep asking about but the
  library doesn't hold, and once it recurs it *proposes* adding it as a tracked
  topic — you approve; it never grows silently.
- **QC rubrics included**: your library comes with the checklists to audit
  its own librarian. Trust, but verify — mechanically.
- **Level-0 mode**: no Python? Everything still works with markdown-only
  indexing and the agent's own web tools.

## Local by default, cloud optional

Your library can live on your machine, or in a cloud agent session.

| | Cloud | Local |
|---|---|---|
| Build the library, design it, write its docs | ✅ strong | ✅ |
| Ask it things, curate, reach it from anywhere | ✅ runs with your PC off | needs your machine on |
| **Actually collecting from the web** | ⚠️ limited by an egress allowlist — many sources can't be allowed at all | ✅ no such limit |

**Start local for your first library.** There's no egress policy in the way,
collection genuinely works, and you finish the whole loop in one sitting. Choose
cloud when you need it running with your PC off, want it reachable from anywhere,
or won't install Python. **Best of both — the hybrid: build and curate in the
cloud, run the collector locally.**

The cloud path has one step this toolkit otherwise assumes away — configuring the
egress allowlist — plus a few realities about where the library lives and which
branches an agent may push. All of it: `references/cloud.md`.

## How is this different from other second-brain skills?

Excellent projects exist for AI-assisted note vaults (notably
claude-obsidian's guided vault setup). This toolkit's focus is different:
**the library as a living system** — a structured dual-layer store with a
*continuous collection pipeline*, *tiered curation discipline*, a *written
librarian role*, and *audit rubrics*, portable across every agent ecosystem it has been run on.
It grows every day and it can prove its own quality.

## Install as a native skill (optional — auto-triggering)

| Platform | How |
|---|---|
| Claude Code | drop this folder into your skills directory, or just point the agent at the repo |
| OpenClaw | `openclaw skills install git:<owner>/personal-wiki-toolkit` (new session to take effect) |
| Tencent WorkBuddy | 技能面板 → 添加技能 → 上传技能(选本仓库文件夹);或手动放入 `~/.workbuddy/skills/` |
| Codex **CLI** | copy/link into `~/.agents/skills/`; `AGENTS.md` here also routes repo-clone usage. (Bare "Codex" is now a mode in the ChatGPT desktop app — the CLI is the separate install) |

Details and per-platform caveats: `docs/compatibility.md`.

## Status

**v0.1.3 — pre-1.0.** The build path is validated end-to-end on **three agent
ecosystems** — Claude Code (local *and* cloud), Tencent WorkBuddy, and Codex —
each a fresh agent that built a working library from just this repo plus a topic,
unaided, in Level-0 *and* full-SQLite modes. That run predates this release: the
two gates added in 0.1.3 are specified and checked at the document level, but
their runtime behaviour has **not** been exercised in a live session. See
[CHANGELOG.md](CHANGELOG.md) § *Verified at the document level only* for exactly
which seven behaviours that covers.

**What 0.1.3 changed**, in one line each — full log in
[CHANGELOG.md](CHANGELOG.md) (中文:[CHANGELOG.zh.md](CHANGELOG.zh.md)):

- **It stops pretending.** A **Preflight** gate now runs before anything else and
  ends with *the user* confirming a file appeared on *their* machine — because an
  agent cannot prove from its own side that where it wrote is where the user looks.
  A previous user finished a session believing a library had been built, inside an
  assistant with no filesystem at all.
- **It records who decided what.** An **Intake** gate writes the setup decisions
  into `config.json` marked `user-typed` / `user-selected` / `default-accepted` —
  and `agent-inferred` is not allowed anywhere. Accepting a stated default is a
  decision; never being told is not.
- **Tiers are a shape, not a law.** Bronze→Silver→Gold is for libraries that
  adjudicate items; data libraries use Fact→Derived→Conclusion, where facts land
  final on write. Forcing the tiers onto data stalls the library — with receipts.
- **Rules that caused errors were fixed**: the QC threshold could be tuned until a
  score looked good; dedup treated "tendering begins" and "breaks ground" as
  duplicates; numeric honesty guarded digits but not the word *target* vs *achieved*.
- **Answers can now be taken back.** A question answered from outside the library
  files its sources as Bronze; if one is later dismissed, the keeper says so
  unprompted — the first mechanism here that corrects something *already said*.
- **Everything has a name**: `references/glossary.md` registers each model with its
  scope, its enforcement point, every file that must change with it, and the
  incident that produced it.

**Still pre-1.0** — hardening continues before the 1.0 tag. Methodology distilled
from production libraries that ran for months with daily automation and independent
QC, and from a survey of 11 real libraries built with it.

## License

MIT. (ClawHub distribution, if/when published there, uses MIT-0 per that
registry's requirement.)
