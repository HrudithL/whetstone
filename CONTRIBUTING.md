# Contributing

## For human contributors

1. Fork and clone the repo, then `pip install -e '.[dev]'` (add `,embeddings` if you're touching
   retrieval — see the README's "Optional: higher-quality recall" section).
2. Branch off `main`.
3. Make your change. Run `ruff check .` and `pytest -m "not embeddings"` before opening a PR (add
   `pytest -m embeddings` too if you touched anything semantic — retrieval, dedup, conflict detection).
4. Open a PR against `main` using the PR template. Small, focused PRs are easier to review.

The rest of this document is the **Agent Playbook** — the branch/PR/review ceremony this project's
maintainer uses when building with an autonomous coding agent. It's not a requirement for human
contributors; read it if you're curious how the project has actually been built, but the four steps
above are what matter for a normal PR.

---

# Contributing Guide (Agent Playbook)

This guide is a **drop-in template** for any GitHub repository. It defines how an autonomous coding agent (and its subagents) must plan, branch, commit, review, and merge work. It is written in imperative voice: every "MUST" / "MUST NOT" is a hard rule.

The agent's north star: **ship small, reviewable, reversible slices; keep it simple and decide the obvious yourself, escalating only genuine forks; never touch `main` without explicit approval.**

---

## Table of Contents

1. [Core Principles](#1-core-principles)
2. [Phase 1 — Plan Before You Touch Code](#2-phase-1--plan-before-you-touch-code)
3. [Phase 2 — The Branch Tree](#3-phase-2--the-branch-tree)
4. [Phase 3 — Executing Slices (Subagents)](#4-phase-3--executing-slices-subagents)
5. [Phase 4 — Pull Requests](#5-phase-4--pull-requests)
6. [Phase 5 — Codex Review](#6-phase-5--codex-review)
7. [Phase 6 — Merging Up the Tree](#7-phase-6--merging-up-the-tree)
8. [Phase 7 — Merging to `main`](#8-phase-7--merging-to-main)
9. [Phase 8 — Branch Cleanup](#9-phase-8--branch-cleanup)
10. [Subjective vs. Objective Decisions](#10-subjective-vs-objective-decisions)
11. [Hard Prohibitions](#11-hard-prohibitions)
12. [Quick Reference Checklist](#12-quick-reference-checklist)

---

## 1. Core Principles

- **Keep it simple and linear.** Build the smallest thing that satisfies the spec. Do not add scope, abstraction, features, or ceremony the task did not ask for. Do not make the project more than it is. When two paths both work, take the simpler one. When in doubt, do less.
- **Use senior-developer discretion.** Act like a talented senior engineer: make straightforward, reasonable fixes and decisions yourself instead of asking permission for the obvious. Don't make silly mistakes, and know where the boundaries are (§10). The bar for interrupting the human is high — see [§10.1](#101-when-to-decide-vs-ask).
- **Plan, then read your plan, then execute.** Never begin editing code before a written spec exists and has been re-read.
- **One small feature per branch.** A branch holds a few commits at most, each tightly scoped to one condensed piece of behavior.
- **Distribute and parallelize** work across a tree of branches using subagents. The tree always terminates at a single **root branch** that is the only branch that merges to `main`.
- **The agent does not make *genuine-fork* calls alone.** Product/UX, public API shape, naming, dependencies, architecture, security posture — the categories in [§10](#10-subjective-vs-objective-decisions) — are escalated. Straightforward, obviously-right fixes are made at the agent's discretion, not escalated (see [§10.1](#101-when-to-decide-vs-ask)).
- **Automated review is triaged each round, not chased to zero.** Wait for the Codex review, decide which of its suggestions actually warrant a change (§10.1), make only those, and re-review if warranted. More than one review-fix round is normal — but each round must be earning its keep. Stop once a round's comments stop being substantive (§6); do not keep looping in pursuit of a perfectly silent report.
- **`main` is sacred.** No direct pushes, no force pushes, no auto-merge, no shortcuts.

---

## 2. Phase 1 — Plan Before You Touch Code

For every task, spec, or feature request:

1. Create a working plan file at:
   ```
   .planning/<spec-name>.md
   ```
   The `.planning/` directory MUST be listed in `.gitignore`. These are the agent's private working notes — not artifacts of the PR.

2. The plan file MUST include:
   - **Goal** — one paragraph.
   - **Scope in / Scope out** — bulleted.
   - **Assumptions** — anything the agent inferred.
   - **Subjective items to escalate** — list every decision the agent identifies as opinion-shaped (see [§10](#10-subjective-vs-objective-decisions)). Ask the human before proceeding on any of these.
   - **Slice breakdown** — the ordered list of small features, each destined for its own branch.
   - **Branch tree sketch** — root branch, feature branches, sub-branches, and their parent relationships.
   - **Acceptance criteria** — per slice, measurable and testable.
   - **Risks / rollback notes**.

3. **Re-read the plan** in a fresh step before executing. This is not optional — the read pass is what catches contradictions the write pass missed.

4. If the plan changes mid-flight, update `.planning/<spec-name>.md` first, then continue.

---

## 3. Phase 2 — The Branch Tree

Work is organized as a **worktree**: many small branches that all trace back to one root branch, which is the only branch permitted to open a PR into `main`.

```
main
 └── root branch          (integration branch for the whole spec)
      ├── feature branch A
      │    ├── sub-branch A1
      │    └── sub-branch A2
      ├── feature branch B
      │    └── sub-branch B1
      └── feature branch C
```

### Rules for the tree

- **Naming:** follow the repo's existing branch conventions. Inspect recent branches (`git branch -a`, PR history, any `CONTRIBUTING`/`STYLE` docs) and mirror the shape. If no convention exists, propose one to the user and get approval before creating branches.
- **Root branch:** created off the latest `main`. It is long-lived for the duration of the spec and only receives merges from its feature children.
- **Feature branches:** branch off the root. Each represents one cohesive capability from the plan.
- **Sub-branches:** branch off a feature. Each holds **one atomic slice** — the smallest shippable unit of that feature.
- **Commits per branch:** keep it to a handful of small, semantically meaningful commits. If a branch grows large, split it into more sub-branches.
- **Parallelism:** independent slices MUST be developed in parallel via subagents (see [§4](#4-phase-3--executing-slices-subagents)). Dependent slices are serialized behind their parent.
- **Every branch is a leaf until proven otherwise.** Only create children when needed.

---

## 4. Phase 3 — Executing Slices (Subagents)

The agent MUST delegate slice work to subagents to parallelize and to keep each unit of work optimally scoped.

### When to spawn a subagent

- The slice is independent of other in-flight slices.
- The slice has clear, written acceptance criteria in the plan.
- The slice can be completed without needing to negotiate scope with the user mid-execution.

### Subagent context contract

Each subagent invocation MUST include a **context contract** in its prompt:

1. **Targeted goal** — a single-sentence objective for the slice.
2. **Branch to work on** — exact branch name, and the parent it was cut from.
3. **Files/areas expected to change** — the agent's best guess; the subagent may expand this after investigating.
4. **Detailed acceptance criteria** — how "done" is measured (tests to pass, behaviors to demonstrate, files to produce).
5. **Non-goals** — what the subagent MUST NOT touch or refactor.
6. **Escalation triggers** — the categories from [§10](#10-subjective-vs-objective-decisions) that, if encountered, must be surfaced to the parent agent (which surfaces to the human) rather than decided unilaterally.

The subagent **may read the entire repository** as needed to understand context, but its **writes must be surgical** and confined to what the acceptance criteria require. Broad reads, narrow writes.

### Subagent completion

A subagent's final message back to the parent MUST include:
- Files changed and why.
- Any assumptions it made.
- Any items it flagged as subjective and did **not** decide.
- Test/lint results.
- The PR URL (see [§5](#5-phase-4--pull-requests)).

---

## 5. Phase 4 — Pull Requests

Every branch (sub → feature, feature → root) is integrated via a PR. No exceptions.

### PR requirements

- **Base branch:** the direct parent in the tree. Sub-branch PRs target their feature branch. Feature PRs target the root branch. Only the root branch PR targets `main`.
- **Title:** concise, imperative, scoped to the slice.
- **Description MUST contain:**
  - Link to the parent plan section in `.planning/<spec-name>.md` (paste the relevant excerpt — the file itself is gitignored).
  - Summary of behavior change.
  - Explicit list of what was **not** changed / left for later slices.
  - Test evidence (commands run, output summary).
  - Any items the agent flagged as subjective and is awaiting human input on.
- **Size:** small. If a PR's diff is sprawling, split it into more sub-branches.
- **Draft first** if the agent is still iterating; mark ready for review only when it believes the slice is complete.
- **Request Codex review immediately.** Codex does not auto-review — as soon as the PR is opened (or marked ready), post `@codex review` as a comment. See [§6](#6-phase-5--codex-review) for the full detection/polling protocol.

---

## 6. Phase 5 — Codex Review

The agent MUST wait for automated review before merging any PR up the tree. More than one review-fix round is normal and expected for a PR with real findings — but the loop has a **stopping condition** (see "When to stop reviewing" below), and it isn't "keep re-reviewing until Codex has literally nothing left to say." Each round must justify itself with substantive findings; once it stops doing that, the PR is done.

**Codex no longer auto-reviews.** Automatic review on PR open has been turned off — a newly opened PR gets no bot activity at all until asked. There is no "first pass" distinct from later passes anymore: **every** review, including the very first one, is manually requested by the agent. Do not wait for a reaction or comment to appear unprompted; if you didn't request it, it isn't coming.

### Request review as part of opening the PR

As soon as a PR is opened (or a draft is marked ready for review), the agent MUST request review by posting a comment with exactly:

```
@codex review
```

Treat this as part of the act of creating the PR, not a separate later step — do not leave a PR sitting unreviewed. The same request is repeated after every subsequent push, since a prior review is stale as soon as new commits land.

### Wait for the complete signal before adjusting

Do not react to partial results. Before making ANY fix on a PR, wait until **both** signals have
fully finished:

- **The entire CI run** — every job (including the slower `sentence-transformers` job), not just the
  first one to report. A green fast job while another job is still running is **not** a pass.
- **The entire Codex review** — the fresh bot review *comment* for your requested pass, not a partial
  or stale one. After each `@codex review`, wait for the new comment rather than assuming an earlier
  pass still applies.

Reacting to a partial signal is the failure mode this rule prevents: pushing a fix while CI is still
running or the review is mid-flight wastes CI minutes on a commit that's about to change, and it
fragments one review into several passes. Collect **all** CI failures and **all** review comments
first, then address them in a single follow-up pass and re-request review. (Now that CI includes a
heavier ST job, the full run takes longer — waiting for it is deliberate, not optional.)

### Detecting the Codex review

Codex is driven by the **`chatgpt-codex-connector[bot]`** account. **Consult this section every time you request a review** — getting the completion signal wrong means either acting on a stale approval or waiting forever for a signal that will never come.

After posting `@codex review`, `chatgpt-codex-connector[bot]` responds through **one of two channels depending on the outcome**, and **both embed the reviewed commit SHA** — that SHA (matched to your latest HEAD) is the completion signal:

- **Findings** → a **pull-request review** on `pulls/<pr>/reviews` (a `### 💡 Codex Review` body) plus **inline review comments** on the diff, with the review's **`commit_id`** set to the reviewed commit.
- **Clean** → an **issue comment** on `issues/<pr>/comments` like *"Codex Review: Didn't find any major issues…"* containing a **`Reviewed commit: <sha>`** line. A clean pass does **not** post a `pulls/reviews` entry, so watching only the review endpoint will miss it.

So after `@codex review`, poll **both** channels for the reviewed-commit SHA equal to your latest HEAD; if it's a `pulls/reviews` entry, read that review's inline comments and address findings; if it's the clean issue comment, the review passed.

### Polling for the signal

The signal is not pushed to you — you must **poll** for it. After each `@codex review`, check periodically until the signal lands. Always `--paginate` (GitHub returns 30 per page; on a busy PR the bot's entry can fall on a later page and be missed):

```sh
# FINDINGS channel — a bot review whose commit_id == your latest HEAD, then that
# review's own inline comments (the PR-wide list also holds earlier passes' stale findings):
gh api --paginate repos/<owner>/<repo>/pulls/<pr-number>/reviews   # pick user==bot AND commit_id==HEAD -> review_id
gh api --paginate repos/<owner>/<repo>/pulls/<pr-number>/reviews/<review_id>/comments   # this review's findings
# CLEAN channel — a bot issue comment whose "Reviewed commit:" line == your latest HEAD:
gh api --paginate repos/<owner>/<repo>/issues/<pr-number>/comments   # look for "Didn't find any major issues" + Reviewed commit
```

A review is complete when the reviewed-commit SHA equals your latest HEAD in **either** channel. Read only the inline comments of the matched review (via `pulls/<pr>/reviews/<review_id>/comments`, or by filtering PR-wide `pulls/<pr>/comments` to `commit_id == HEAD`); the PR-wide list keeps every earlier pass's comments, so treating all of them as "the fresh review" makes you re-address already-fixed findings.

Poll on a **modest cadence (~every 30s) within a bounded window (~15–20 min)**, ideally as a background loop that exits the moment the signal appears. Two distinct gates use different bars:

- **To begin the FIX pass** — proceed once the **full CI run has completed (green OR red)** *and* the requested review signal is in (a `pulls/reviews` entry with findings, or the clean issue comment) referencing your latest commit. You need CI *finished*, not passing, so you can collect and fix its failures. Match on the **reviewed-commit SHA**, not merely "a review exists" — a review of a prior commit is stale.
- **To MERGE up** — CI must be **fully green** (all jobs), and the review must have reached its stopping condition per "When to stop reviewing" below (see [§7](#7-phase-6--merging-up-the-tree)). This does not mean the report is spotless — it means the agent has kept reviewing while it was worth it and stopped once it wasn't.

Re-request after each round of fixes, for as many rounds as the findings stay substantive. If, after the full polling window, **no signal appears at all** for your requested review, or Codex reports it is **rate-limited**, Codex is unavailable for this PR — fall back to the **Claude self-review** below rather than inventing some other substitute or silently skipping review.

### Fallback when Codex is unavailable (rate limits)

Codex code review runs against the account's usage limits and can be **rate-limited** — instead of reviewing, `chatgpt-codex-connector[bot]` posts an issue comment such as *"You have reached your Codex usage limits for code reviews."* When Codex is unavailable this way (or gives no signal within the polling window), the Claude Code agent driving the branch **performs the review itself and posts it as a PR comment**, standing in for Codex:

- Review with the same rigor Codex would: read the **full diff** and post a single PR comment (`gh pr review <pr> --comment`, or `gh pr comment <pr>`), clearly labelled as the stand-in review. List findings **ordered most-severe first**, each with a concrete failure scenario, then a short **verdict** on whether it is safe to merge up. Say in the comment that it stands in for the rate-limited Codex.
- Then apply the same [§10.1](#101-when-to-decide-vs-ask) discipline to your own findings: fix what is clear, escalate only genuine forks, decline what would overcomplicate.

This self-review **satisfies the review gate** for merging up the tree — it is not a licence to skip review, it is the *same* review performed by the agent when the external reviewer cannot run. Only if a self-review genuinely cannot be produced should the agent instead **ask the human** how review should be handled.

> An external `@claude review` GitHub Action is deliberately **not** used as the fallback: it runs Claude inside CI, which requires paid auth (a Claude Max OAuth token or an `ANTHROPIC_API_KEY`) this repo does not carry. The Claude Code agent already driving the work provides the equivalent review at no extra cost.

### Acting on review feedback

Read the whole review, decide what is reasonable to fix, and **make those specific fixes yourself**. Do not turn the review into a checklist of questions for the human — that is one failure mode. Grinding through round after round chasing a perfectly silent report is the other. A review is a set of suggestions to weigh each round, not a queue to empty.

For each Codex comment, apply the [§10.1](#101-when-to-decide-vs-ask) test:

1. **If the fix is clear and reasonable — make it.** A defect, an inconsistency, a missed test, a straightforward correctness/security fix, or a change with one obviously-right implementation is the agent's to make at its own discretion.
2. **Escalate only a genuine fork:** a fix that has **multiple materially-different reasonable implementations**, or that is a true product/policy/naming/architecture decision per [§10](#10-subjective-vs-objective-decisions). Then ask one focused question — "implement it this way or that way?" — with a recommendation. Do not ask about fixes that are straightforward to make.
3. **Decline what would overcomplicate.** A suggestion that adds scope, abstraction, or infrastructure beyond what the spec needs may be declined or deferred — briefly note why on the PR. Keeping it simple (§1) outranks satisfying every suggestion.
4. **Push a follow-up commit with those changes and re-request review.** If that next round comes back with more substantive findings, repeat the same triage on them — a second or third round of real findings is normal. If it doesn't (see below), stop.

### When to stop reviewing

The goal is never a literally empty report — it's a round whose comments stop being worth acting on. After each round, ask whether it raised anything substantive: a real defect, an inconsistency, a gap in test coverage, a genuine fork. If yes, fix it (or escalate it) and go again. Stop the loop once a round's remaining comments are:

- restating something already declined or deferred with a reason on the PR,
- purely stylistic/cosmetic with no behavior or clarity impact,
- scope the PR deliberately doesn't cover, or
- otherwise not clearing the [§10.1](#101-when-to-decide-vs-ask) bar for "worth changing."

**Out-of-scope findings get at most 2–3 corrective rounds.** If a review surfaces out-of-scope comments and the agent's follow-up explicitly asks Codex to confine itself to the PR's scope, but the next round comes back out-of-scope again, do not keep re-requesting review hoping it corrects itself. After 2–3 such rounds, stop, note on the PR that remaining comments are out-of-scope and were not actionable via re-review, and proceed as if the stopping condition were met. Continuing to loop past that point is not caution, it's wasted CI and review budget on a signal that has already shown it won't converge.

Note the outcome briefly on the PR ("remaining comments are stylistic nits / already addressed — stopping here") and move on. This is a judgment call the agent makes itself, the same way it makes any other §10.1 call — it is not a genuine fork to escalate.

The PR is eligible to merge up once **both** are true: the review has reached this stopping point — the requested review (findings or the clean issue comment) has, on its most recent round, either come back clean or surfaced nothing left worth fixing per the criteria above; or, when Codex is unavailable (rate-limited / no signal), the agent's **self-review** posted for your latest commit per the fallback above has been triaged the same way — AND any escalated forks are resolved by the human. None of this requires a spotless report; it requires that the feedback was actually considered each round and acted on where it mattered.

---

## 7. Phase 6 — Merging Up the Tree

- Merges from sub → feature and feature → root are **allowed and expected** without additional user gating, provided **CI is green (all jobs)** and the Codex review in [§6](#6-phase-5--codex-review) has been triaged.
- **Use merge commits everywhere** (not squash, not rebase-and-merge). Full history is preserved so the small-commit trail up the tree stays intact and auditable.
- After each successful merge, propose branch cleanup per [§9](#9-phase-8--branch-cleanup).

---

## 8. Phase 7 — Merging to `main`

The root-branch → `main` merge is the **only** merge that requires the human user's explicit, complete review and acceptance.

Before proposing the merge to `main`, the agent MUST:
- Confirm every feature PR has merged into the root branch.
- Confirm CI is green on the root branch.
- Post a consolidated summary to the human: goal, slice list, notable decisions, subjective items resolved, test coverage, migration/rollback notes.
- **Wait for the human's explicit approval** to merge to `main`.

Auto-merge MUST NOT be enabled on any PR targeting `main`. Merge only happens after the human says "merge it."

---

## 9. Phase 8 — Branch Cleanup

**Merged branches MUST be removed once they are no longer relevant.** Stale branches clutter the tree and confuse future work.

- After a sub-branch is merged into its feature, the sub-branch is a candidate for deletion.
- After a feature branch is merged into the root, the feature branch is a candidate for deletion.
- After the root branch is merged into `main`, the root branch is a candidate for deletion.

Rules:
- The agent MUST propose the deletion to the user (list of branches, local + remote) and **wait for approval** before deleting. Branch deletion is one of the actions that requires explicit user consent.
- Never delete a branch that still has open PRs, unmerged commits, or ongoing work by any collaborator.
- Delete both the local and the remote branch once approved.

---

## 10. Subjective vs. Objective Decisions

The agent's job is to **think about what is important** and, for every change under consideration, ask: *"Is any part of this dependent on human opinion, product judgment, or repo-level policy?"* If yes — and it is a genuine fork — it escalates. Otherwise it decides and moves on.

### 10.1 When to decide vs. ask

Default to **deciding**. Interrupt the human only when it is genuinely warranted. Before asking, run this test:

- **Is the fix/decision straightforward with one obviously-right answer?** → **Decide and do it.** (correctness fixes, inconsistencies, mechanical refactors, tests, security/robustness fixes, following an explicit instruction, the plainly-simpler of two options.)
- **Are there multiple materially-different reasonable implementations?** → **Ask** one focused "this way or that way?" question with a recommendation. A difference that is trivial or cosmetic is *not* material — pick the clean one and move on.
- **Is it one of the always-subjective categories below (product/UX, public API shape, naming, deps, architecture, security posture)?** → **Ask.**
- **Would it add scope/abstraction/infra the spec doesn't need?** → **Don't do it** (or do the minimal version); note the choice.

Batch genuinely-needed questions; never fan a single review out into many small questions. When you do proceed on your own, say briefly what you decided and why, so it stays auditable.

### Always subjective — escalate to the human

- **Product/UX behavior and copy** — what the feature does from a user's perspective, wording, tone.
- **API shape / public interface design** — endpoints, payload shapes, function signatures exposed to consumers.
- **Naming** — files, symbols, endpoints, config keys. Naming carries meaning; the human owns it.
- **Dependency additions or version bumps** — adding a package, upgrading a major version, swapping a library.
- **Architectural tradeoffs** — performance vs. readability, sync vs. async, monolith vs. split, caching strategy.
- **Security posture decisions** — auth models, threat scope, what data is trusted, what is logged.
- **Deleting or renaming existing public APIs** — anything that could break downstream consumers.
- **Anything else the agent's judgment flags as opinion-shaped.** When in doubt, ask.

### Safe to decide autonomously

- Mechanical refactors that preserve behavior.
- Fixing a demonstrated bug with a minimal change.
- Adding tests for existing behavior.
- Following an explicit instruction the human already gave.
- Complying with lint/format rules already configured in the repo.

### How to escalate

- Present the decision, the options, the tradeoffs, and a recommendation.
- Do not proceed with the affected code path until the human answers.
- Record the answer in the PR description so the decision is auditable.

---

## 11. Hard Prohibitions

The agent MUST NOT:

- Push directly to `main`.
- Force push to any branch (`--force`, `--force-with-lease`, or otherwise) without explicit human instruction for that specific push.
- Bypass hooks (`--no-verify`) for any reason.
- Amend or rewrite commits that have already been pushed.
- Enable auto-merge on any PR targeting `main`.
- Delete any branch without user approval.
- Commit secrets, tokens, credentials, or `.env` files. If one is discovered committed, stop and alert the user.
- Make a genuine-fork decision on the human's behalf — a §10 category (product/UX, public API shape, naming, deps, architecture, security posture) or a choice with multiple materially-different reasonable implementations (see [§10.1](#101-when-to-decide-vs-ask)). Straightforward fixes are the agent's to make.
- Merge a PR up the tree before the Codex review ([§6](#6-phase-5--codex-review)) — or the agent self-review stand-in when Codex is rate-limited/unavailable — has been read and triaged for HEAD.
- Treat "the CI passed" as a substitute for the Codex review.

---

## 12. Quick Reference Checklist

Before every task:
- [ ] Wrote `.planning/<spec-name>.md` with goal, scope, slices, acceptance criteria, and subjective items.
- [ ] Re-read the plan.
- [ ] Escalated all subjective items in the plan to the human and received answers.

Per slice:
- [ ] Cut a sub-branch off the correct feature branch.
- [ ] Spawned a subagent with a full context contract (goal, branch, files, acceptance, non-goals, escalation triggers).
- [ ] Made a small number of tightly scoped commits.
- [ ] Opened a PR to the parent branch with a complete description.

Per PR:
- [ ] Posted `@codex review` as part of opening the PR — Codex no longer auto-reviews, so this is required every time, including the first pass.
- [ ] Waited for the **entire CI run** (completed, green or red) AND the **entire Codex review** to finish before making any fix — no reacting to partial signals.
- [ ] Detected the requested Codex signal for HEAD: a findings review (`pulls/reviews` `commit_id`) or the clean issue comment (`Reviewed commit` SHA).
- [ ] If Codex was unavailable (rate-limited / no signal), posted the Claude **self-review** stand-in for HEAD as a PR comment (or asked the human only if that wasn't possible).
- [ ] Made the reasonable fixes at own discretion each round; declined/deferred anything that would overcomplicate (noted why).
- [ ] Escalated only genuine forks (multiple reasonable implementations, or a §10 decision); recorded the human's answer.
- [ ] Repeated review-fix rounds only while findings stayed substantive; stopped once remaining comments were nits/already-addressed/out-of-scope, and noted that on the PR.
- [ ] Merged up with a **merge commit** (not squash, not rebase).
- [ ] Proposed branch deletion to the human.

For `main`:
- [ ] All features merged into root; CI green.
- [ ] Posted consolidated summary to the human.
- [ ] Received **explicit** approval.
- [ ] Merged via merge commit. No force push. No auto-merge.
- [ ] Proposed root-branch deletion.
