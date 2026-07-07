# 个人Wiki工具包 · Personal Wiki Toolkit

> 让 AI 管家帮你从零建库、持续喂库、按纪律策展。
> (English: [README.md](README.md))

一套 **AI agent 技能包**:对话式面试、或拖一个文件夹给它,帮你**从零搭起一座个人知识库**
—— Markdown + SQLite 双层存储、自动情报采集管线、Medallion 分层策展、一个"图书管理员"
agent 角色、以及 QC 质检标准。跨 **Claude Code / OpenClaw / WorkBuddy / Codex**(其实任何
能读 markdown、跑脚本的 agent 都行)。

## 一句话用法

跟你的 AI 说:

> 读一下 github.com/&lt;owner&gt;/personal-wiki-toolkit,帮我建一个追踪「XX」的资料库。

就这样。agent 读 `SKILL.md`,面试你(或扫你指给它的文件夹),搭好库,**当着你的面**跑通
第一轮采集,再交给你一页「养库指南」。工具包本身之后可以删掉 —— 你的库自己带着说明书。

## 你最终得到什么

```
my-kb/
├── CLAUDE.md / AGENTS.md   ← 库自己的说明书:任何 agent 打开即成"管家"
├── notes/  briefs/          ← Gold:策展过、带出处、永久
├── _pipeline/silver/        ← 机器初筛草稿,等你裁决
├── kb.db  intel.db          ← 索引 + 采集账本(SQLite)
├── scripts/                 ← 抓取 / 判分入库 / 升降级 / 索引 / 需求看板
└── keeper.md                ← 你的管家的职责与红线
```

- **双层**:人读 Markdown,查询走 SQLite。
- **Medallion 策展**:一切先进 Bronze,机器判断填 Silver,只有显式升格才成 Gold;剔除都带理由。
- **agent 就是判官** —— 不需要额外 API key,谁托管它谁当 judge。
- **需求驱动自生长**:管家记下你反复问、但库里没有的东西 → 攒够了**主动提议**加成追踪主题
  (你批准才建,绝不静默生长)。
- **自带 QC 标准**:你的库附带审自己管家的 checklist。信任,但机械地验证。
- **Level-0 模式**:没 Python?markdown-only 索引 + agent 自带 web 工具,照样跑。

## 和别的"第二大脑"技能有什么不一样?

已有很多优秀的 AI 笔记库项目(尤其 claude-obsidian 的引导式 vault setup)。这个工具包的侧重
不同:**把库当成一个活的系统** —— 结构化双层存储 + **持续采集管线** + **分层策展纪律** +
**成文的管家角色** + **审计 rubric**,而且**跨四个 agent 生态**。它每天在长,还能自证质量。

## 装成原生技能(可选 —— 自动触发)

| 平台 | 怎么装 |
|---|---|
| Claude Code | 放进 skills 目录,或直接让 agent 读这个 repo |
| OpenClaw | `openclaw skills install git:&lt;owner&gt;/personal-wiki-toolkit`(新 session 生效) |
| WorkBuddy | 技能面板 → 添加技能 → 上传技能(选本仓库文件夹);或手动放 `~/.workbuddy/skills/` |
| Codex | 拷 / 链到 `~/.agents/skills/`;仓库的 `AGENTS.md` 也能路由 clone 用法 |

细节与各平台注意事项见 [`docs/compatibility.md`](docs/compatibility.md)。

## 状态

**v0.1 —— pre-1.0。** 内容完整,并已在 **Claude Code 上端到端验证**:一个全新 agent 只拿到本
repo + 一个主题,就从零建出了能用的库(真实采集、策展、管家),全程无作者指导。**Codex 与
WorkBuddy 的跨生态验证尚待进行**,通过后才到 1.0。方法论提炼自三个跑了数月、每日自动化 +
独立 QC 的生产资料库。

## License

MIT。(若发布到 ClawHub,按其要求用 MIT-0。)
