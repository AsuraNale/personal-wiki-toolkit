---
title: Package-registry poisoning — three campaigns in July 2026
date: 2026-07-21
type: note
tier: gold
topic: supply-chain
curated_by: Sentry
refs:
  - key: https://thehackernews.com/2026/07/compromised-asyncapi-npm-packages.html
    used_for: "@asyncapi maintainer-account compromise; 4 packages, multi-stage loader"
  - key: https://thehackernews.com/2026/07/seven-malicious-vite-npm-packages-use.html
    used_for: "7 Vite-impersonating packages; blockchain-resolved C2"
  - key: https://thehackernews.com/2026/07/sleepergem-uses-three-malicious.html
    used_for: "SleeperGem; 3 RubyGems incl. git_credential_manager; staged download"
---

# Package-registry poisoning — three campaigns in July 2026

> **Gold tier · synthesized note.** Built from three separate Silver entries in the
> same collection round (see `refs`). Nothing here is asserted beyond what those three
> sources reported — where they don't say, this note says they don't say.

## Why these three belong in one note

They surfaced independently within a single week and share a shape: **the registry
itself is the delivery channel, and the developer workstation is the target.** Read
one at a time they look like three routine advisories; read together they show two
distinct entry techniques and one shared objective.

## The two entry techniques

**① Account compromise — trusted namespace, real package.**
The `@asyncapi` case: four packages under a legitimate, widely-depended-on namespace
were republished carrying a multi-stage botnet loader after a maintainer account was
compromised. **Nothing about the package name looks wrong** — the name is the real one,
the namespace is the real one. Only the version is hostile. This is why the source's
enumeration of affected versions matters more than the package names: **name-based
blocklists do not catch this; lockfile version pinning does.**

**② Impersonation — plausible name, package that never was.**
The Vite case (seven packages) and SleeperGem (three RubyGems, including
`git_credential_manager`) both rely on a developer reaching for a name that *sounds*
like tooling they already trust. Note the SleeperGem name choice — a credential helper
is exactly what a developer installs without much thought, and exactly what sits next
to the secrets worth stealing.

## What is new: C2 that cannot be taken down the usual way

The Vite campaign resolves its command channel **through blockchain transactions**
rather than a domain or IP. The operational consequence: there is no registrar to
notify and no host to seize — the usual takedown path does not apply, and blocklists
keyed on domains will not see it. Defenders are pushed toward egress and behavioral
detection instead of indicator blocking.

## What this changes in practice

- **Pin and review lockfile diffs, not package names.** Technique ① is invisible at the
  name level; the affected-version list is the actionable artifact.
- **Treat the developer workstation as production.** All three campaigns target it —
  SleeperGem explicitly so. Credentials on a dev box are the objective, not a bonus.
- **Blocklists age out fast here.** Blockchain-resolved C2 means indicator lists lose
  value quickly; egress policy and behavior beat enumeration.

## What these sources do NOT establish

- **No stated linkage between the three campaigns.** They are contemporaneous and
  similar in shape; none of the three reports attributes them to a common operator.
  Do not read a coordinated wave into this note — that is not what the sources say.
- **No published victim counts or download totals** in any of the three.
- **The RubyGems payload's final stage is described as staged-download**, i.e. the
  reporting covers the delivery mechanism, not a full analysis of what lands.

---
*Curated by Sentry · 2026-07-21 · every claim traces to a `refs` key above; gaps stated explicitly*
