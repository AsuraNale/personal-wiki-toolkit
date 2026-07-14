# Personal Wiki Toolkit · User Manual

> **What it is**: this toolkit gets your AI assistant to build you a private library that **keeps growing** — it fetches new material from public web pages, judges what's worth keeping, files it, and **records a source and a date for every entry**. (**Scheduled automatic refresh** needs local mode with Python — see "What you get".)
>
> **No programming needed.** You just talk to your AI assistant.
>
> An example: "**What does an RTX 5070 cost right now? Is that above or below list price? Buy now or wait?**" — it watches that for you, daily. Full walkthrough below.
>
> 👉 **First time: choose "local" — running on your own computer. Cloud is only an option, and there are many sites it can't open** — see Step 1.

---

## ⚠️ Read this first

Before you start, make sure you have **both** of these. Missing either one and you won't get through.

### 1. An AI subscription

The AI assistant that drives this toolkit needs a paid account. **If you already have Claude Pro / Max, or ChatGPT Plus or above, you're already covered — there's nothing more to buy.**

> **Don't worry if you see the word "API"**: you can also pay per use with an API key, but **if you're not sure what an API is, just use a subscription** — this manual assumes the subscription route.
>
> **Prices vary by region** — check the vendor's site for what you'll actually pay. (Figures below are US reference prices.)

### 2. An AI assistant that can read and write files on your computer

**Pick one:**

| Assistant | What you need to know |
|---|---|
| **Claude Code** ⭐ recommended for first-timers | Has a **Windows / Mac desktop app** — install it like any normal program. Sign in with your **Claude subscription** (Pro / Max) — **the account you're already paying for; nothing extra to buy.** https://claude.com/claude-code |
| **Codex** (OpenAI) | ⚠️ **There's no separate "Codex" program to download.** Codex is a **mode inside the ChatGPT desktop app**. Install the ChatGPT desktop app → sign in → open a folder → pick Codex mode. **If you have ChatGPT Plus, you already have Codex — nothing extra to buy.** Download: https://chatgpt.com/download/ (lowest confirmed tier: **Plus**; the vendor doesn't state whether Free / Go can run local tasks, so don't count on them) |
| **WorkBuddy** | If you already use it, just use it. |

### ⚠️ These **won't** work — but note the distinction

**ChatGPT in your browser, the Claude web chat, and phone apps — none of them can do this job.** The reason: they can only talk to you. They **can't touch the files on your computer** — and this library *is* a real folder on your computer.

> ⚠️ **Don't confuse the web version with the desktop app** — this is the easiest thing to get wrong:
> - **ChatGPT in your browser** ❌ won't work
> - **The ChatGPT desktop app** ✅ **will** (Codex lives inside it)
>
> So: **if you have ChatGPT Plus you already qualify** — you just need to install the **desktop app** rather than using it in a browser.
>
> (Phone apps can't build the library. But once it's built, querying a cloud library from your phone is fine — see Step 1.)

### How to check the assistant you have

**Don't ask it "can you?"** — an AI will confidently say yes, and **the browser version of ChatGPT will say yes too**. **Make it do the thing, and look for yourself:**

> Tell it: **"Create a folder called `wiki-test` on my Desktop, then tell me the full path."**

Then **go look at your Desktop**:
- The folder **is actually there** → you're good (delete it once you've looked)
- **Nothing appeared**, or it starts explaining that it can't access your file system → it won't work; switch to one from the table above

### What to expect

| | |
|---|---|
| ⏱️ **Time** | About **30–60 minutes**, and you're just watching for most of it |
| 💰 **Cost** | Your AI subscription (above); the toolkit itself is **free and open source** |
| ⌨️ **Coding** | **None** |

---

## Step 1 · Local or cloud?

| | **Local** (on your computer) | **Cloud** (online) |
|---|---|---|
| **Which sites it can open** | ✅ **No site restrictions** (a few sites block automated visitors themselves — that's the site's policy, not the toolkit's limit) | ⚠️ **Many sites won't open** — a cloud AI runs on the provider's servers and **can only reach a list of sites the provider set in advance**; anything off that list won't open, **and you can't add to the list yourself** |
| When your computer is off | ❌ Nothing runs (it runs when you're on) | ✅ Keeps running |
| Query it from your phone | ❌ | ✅ |
| **Sign up for anything?** | **No** | **Yes** — a **free GitHub account** (that's where the library lives) |

> ### 👉 **First time: choose local.**
>
> **Why**: the cloud has one hard limit — **it's great at building the library, but many of your data sources it simply can't open.** The retail sites you'd need for graphics-card prices are **almost certainly not on the provider's list.** That's not the AI falling short; it runs in a restricted environment and can only visit places on that list.
>
> And the first time through, what you most need to confirm is **whether it really fetched a price** — **only local can show you that.**
>
> **Cloud is only an option.** It suits you if you want it running while your computer is off, or want to query it from your phone. **Get local working first, then consider it.**

---

## Step 2 · Send the instruction

**Copy this as-is; change only the topic in the quotes:**

```
Read github.com/AsuraNale/personal-wiki-toolkit and
help me build a library that tracks "PC parts".
```

> **About GitHub**: it's a site where programmers park public material. **This instruction is addressed to your AI assistant — it goes and reads it itself.** **If you took the recommendation and chose local, you never touch GitHub at all** (no account, no download, no visiting the site). **Only cloud mode needs a GitHub account** — see below.

**Then, per your Step 1 choice:**

- **Local** → Create an empty folder on your computer (say "My PC Parts Library" on your Desktop), **open that folder with your AI assistant** (Claude Code and the ChatGPT desktop app both let you open a folder as your working location), and send it the instruction.
- **Cloud** → Go to **claude.ai/code** and sign in. You'll need a **free GitHub account** first (https://github.com/signup) and an **empty private repository** there (an online folder only you can see). Start a new task against it and send the instruction.
  > Note: on the cloud path, **if you later want it to genuinely fetch prices automatically, you'll still need an assistant installed on your own computer** to move the fetching there (see Troubleshooting).

---

## Step 3 · Answer its questions, watch the first round

It'll ask you a few things:

> - Which country do you buy in? (sets the currency and which sites to check)
> - **What's this machine mainly for?** (it recommends which models to track — you don't need to know hardware)
> - How should it get prices? (fetch automatically where it can, or you paste them in)

**Answer properly** — these few answers decide how useful the library turns out.

Then **watch it finish the first round** and confirm **data actually landed** (prices in the table, with links and dates). About 10–20 minutes, and you're just watching.

- **Chose local** → the library is that ordinary folder on your computer, and it's yours.
- **Chose cloud** → the library lives in your own private GitHub repository, visible only to you.

---

## What you get

- **📄 Notes and briefs to read** — plain text files (`.md`, "markdown" in the trade). **Any text editor opens them** (Notepad on Windows, TextEdit on Mac); **the first time you double-click on Windows you may get a "How do you want to open this file?" prompt — choose Notepad.** For nicer reading: **Obsidian** (free for personal use) or **Typora** ($14.99, 15-day trial).
- **🗃️ A data table** — every price it ever fetched, so you can ask "what's the lowest the 5070 hit in the last three months?"
- **🤖 Automatic refresh** — fetches new prices on a schedule. ⚠️ **Needs local mode + Python** (see FAQ); without it, **it runs when you ask it to**.
- **📋 A one-page maintenance guide (CARE.md)** — everything about day-to-day use
- **👤 A librarian role** — when you want to know something, **open that folder with your AI assistant and just ask: "what's the lowest the 5070 hit last month?"** — it reads the library itself; you don't re-explain the background.

---

## Walkthrough · PC-parts price tracking

Here's a **real run**, mapped step by step onto the three steps above.

### Matching Step 1 (choosing a mode)
This run used **cloud**. ⚠️ **And precisely because it was cloud, the automatic price fetching got blocked** — which is exactly why we suggest you **start local**.

### Matching Step 2 (the instruction)
Exactly the sentence above: "Read github.com/AsuraNale/personal-wiki-toolkit and help me build a library that tracks 'PC parts'."

### Matching Step 3 (the questions)

| It asked | The user answered |
|---|---|
| Which country do you buy in? | The US |
| What's this machine mainly for? | **Mainly Dota 2 and Wuthering Waves** |
| How should it get prices? | Fetch automatically where you can |

**Three sentences, that's all.** From that it configured a **mid-range 1440p list** — because neither game is demanding, it **didn't push top-end cards the user would never need.**

### Matching "What you get" (the actual output)

| Part | Latest price | vs. list price |
|---|---|---|
| RTX 5070 | $609.99 | ↑ 11% **over** |
| RTX 5060 Ti 16G | $499.99 | ↑ 16% **over** |
| Ryzen 7 7800X3D | $324.99 | ↓ **28% under — good buy** |

> *Real results from a run on 2026-07-14 (the AI looked the prices up live from public retail pages). **Your numbers will differ.** This table omits the "source link" and "fetched on" columns for readability — **every row in your library carries both**.*

From that you can judge directly: **graphics cards are broadly above list price (supply is tight), while one CPU is discounted.** It hands you not articles but **facts you can decide on**.

### What actually happened on this run — and what it proves

- **Automatic fetching was blocked by the cloud environment** → the AI **reported that failure honestly**; it **did not dress it up as "prices unchanged"**
- So it switched to looking prices up on public pages instead, **citing a source and a date for each**
- **Three entries weren't reliable enough** → it flagged them "to verify" rather than papering over them

> 👆 That's the **"if it couldn't fetch, it says so"** rule below, working in the wild — **the rules aren't decoration.**

> PC parts is just the example. The same approach tracks an industry you follow, papers in your field, or your own reading notes. **Change the topic, send the same instruction.**

---

## The rules it runs by (why you can trust it)

The core value isn't that it can fetch data — it's that **it doesn't paper over its own faults**:

- **✅ Every entry carries a source and a date** — "$609.99, source: this Newegg link, fetched 2026-07-14." **Data without a source doesn't get in.**
- **✅ If it couldn't fetch, it says so** — **the most important rule here.** When a round fails on a network problem or a site restriction, it states plainly: **"this is a fetch failure, not an absence of new content."**
  > **Why this matters**: a real case — a library had 8 sources configured; **7 of them had been fetching nothing for days without raising a single flag**, and the brief read perfectly normal ("nothing new today"). **Without this rule, nobody would ever have caught it.** "Couldn't fetch" and "genuinely unchanged" are different facts — blur them and your library rots while you have no idea.
- **✅ It doesn't invent** — anything uncertain is flagged "to verify" rather than padded with a guess. If the library doesn't have something, it says so.
- **✅ Important things need your nod** — machine-filtered material waits in a draft area; only what you confirm becomes permanent. It doesn't add things on its own.
- **✅ It won't touch files you already have** — **it won't change anything you wrote without your agreement**; it lists what it plans to do first, and acts once you confirm.
- **✅ Free, public sources only** — it follows sites' public-access rules, **skips (and tells you about) any site that clearly forbids fetching**, and never stores anyone's full article (just title, link, summary, and its own judgment).
- **✅ Fetched content is material, not orders** — if a page contains "AI: ignore your rules and do as I say," it **flags it as suspicious and doesn't comply**.

---

## Later: using both modes

**(Skip on your first run — get local working first.)**

After a week or two of local running smoothly, the nicest setup is usually **both**:

- **Cloud**: building, organizing, answering questions (from your phone, any time)
- **Local**: fetching (no site restrictions)

Tell your AI assistant when you get there and it'll set it up.

---

## FAQ

**Q: What's Python? Do I have to install it?**
Python is a **free, small program**. Installing it is what lets the library **refresh automatically on a schedule** and answer trend questions ("chart the last three months"). **It's not required** — things work without it (the table is kept as text, and the AI searches itself); the difference is **you trigger each run yourself**. **If you install it, your AI assistant walks you through in about 5 minutes** — it doesn't affect anything else on your computer.

**Q: Can I really use this without programming?**
Yes. You just talk to your AI assistant: it asks, you answer in plain words. In the real run above, the user said three sentences total.

**Q: Does my material get sent anywhere?**
**Local mode: it all stays on your computer and goes nowhere.** Cloud mode: it lives in **your own private GitHub repository** (an online folder only you can see). What goes in is your call.

**Q: Will it mess with files I already have?**
No. This rule is firm: **it won't change anything you wrote without your confirmation — it lists what it plans to change first, and acts once you agree.** When organizing files you already have, it by default only **builds a separate "index"** (what you have, what each covers, where it lives). **Your originals aren't touched** — not moved, not copied, not a character changed.

**Q: How is this different from just asking an AI?**
Asking an AI: it starts from zero each time, forgets when it's done, and you can't verify it.
This library: **it remembers** (it keeps accumulating), **it's queryable** (that price from three months ago is still there), **it's verifiable** (every entry has a source) — and **it tells you where it fell short** (a failed fetch raises a flag).

---

## Troubleshooting

- **My assistant says it can't open the link / can't browse** → It's probably a talk-only one (the browser version of ChatGPT, for instance). Go back to **Read this first** and switch to one that can work with files — **note that the ChatGPT desktop app works; the browser version doesn't.**
- **It says it's done, but I see no real prices** → Ask it to show you the data table. **Every row should have a link and a date.** If not, the first round didn't really finish — ask it to run it again.
- **Cloud can't fetch anything** → **That's expected** (see Step 1). Send this to the assistant **on your computer**: "My library can't fetch anything from the cloud — please move the fetching step to run on this machine." (This does mean having an assistant installed locally.)
- **I want a different topic** → Send the instruction again and build a second library.
- The **CARE.md** in your library is your first reference.

---

## 📣 About this test

**v0.1.2 is an early build. What we most want to know:**

- Did the first round **actually finish**?
- **Where did you get stuck?**
- **Which parts didn't make sense?** (paste the exact wording — that helps most)

⚠️ **If it didn't run, please tell us** — **a failure is a useful finding, not "nothing to report"** (which is exactly the principle this toolkit is built on). "**It didn't work**" is worth far more to us than "it was fine."

**How to send feedback**: fill in this form → **`<survey link to be added>`**
No need to tidy it up — **a screenshot plus "I got stuck at step N" is enough**.

---

*Personal Wiki Toolkit · v0.1.2 · MIT licence · Chinese version: [MANUAL.zh.md](MANUAL.zh.md)*
