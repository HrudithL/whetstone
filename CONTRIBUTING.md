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
6. [Phase 5 — Codex Auto-Review Loop](#6-phase-5--codex-auto-review-loop)
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
- **Automated review must pass before merging up.** Wait for the Codex auto-review, address every non-subjective comment, and get a thumbs-up before proceeding.
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

---

## 6. Phase 5 — Codex Auto-Review Loop

The agent MUST wait for automated review before merging any PR up the tree.

### Wait for the complete signal before adjusting

Do not react to partial results. Before making ANY fix on a PR, wait until **both** signals have
fully finished:

- **The entire CI run** — every job (including the slower `sentence-transformers` job), not just the
  first one to report. A green fast job while another job is still running is **not** a pass.
- **The entire Codex review** — the complete review (its emoji marker present), not the first inline
  comment to arrive.

Reacting to a partial signal is the failure mode this rule prevents: pushing a fix while CI is still
running or the review is mid-flight wastes CI minutes on a commit that's about to change, and it
fragments one review into several passes. Collect **all** CI failures and **all** review comments
first, then address them in a single follow-up pass and re-request review. (Now that CI includes a
heavier ST job, the full run takes longer — waiting for it is deliberate, not optional.)

### Detecting the Codex review

- The Codex auto-review posts a review comment on the PR containing a recognizable **emoji marker** it always leaves. The agent verifies the review is complete by locating that marker on the PR.
- If, after a reasonable wait, **no Codex review appears**, that means Codex has opted not to review this PR. In that case the agent MUST NOT invent a substitute — it MUST **ask the human user how review should be handled for this repository** (e.g., which reviewer, which bot, what criteria) and follow the instruction given.

### Iterating on review feedback

Read the whole review, decide what is reasonable to fix, and **make those fixes yourself**. Do not turn the review into a checklist of questions for the human — that is the failure mode this section exists to prevent.

For each Codex comment, apply the [§10.1](#101-when-to-decide-vs-ask) test:

1. **If the fix is clear and reasonable — just make it.** A defect, an inconsistency, a missed test, a straightforward correctness/security fix, or a change with one obviously-right implementation is the agent's to make at its own discretion. Push a follow-up commit; re-request review.
2. **Escalate only a genuine fork:** a fix that has **multiple materially-different reasonable implementations**, or that is a true product/policy/naming/architecture decision per [§10](#10-subjective-vs-objective-decisions). Then ask one focused question — "implement it this way or that way?" — with a recommendation. Do not ask about fixes that are straightforward to make.
3. **Decline what would overcomplicate.** A suggestion that adds scope, abstraction, or infrastructure beyond what the spec needs may be declined or deferred — briefly note why on the PR. Keeping it simple (§1) outranks satisfying every suggestion.
4. Repeat until Codex issues a clean/approving pass **and** any genuinely-escalated fork has a human answer.

The PR is only eligible to merge up when **both** are true: Codex thumbs-up AND any escalated forks resolved by the human.

---

## 7. Phase 6 — Merging Up the Tree

- Merges from sub → feature and feature → root are **allowed and expected** without additional user gating, provided **CI is green (all jobs)** and the Codex loop in [§6](#6-phase-5--codex-auto-review-loop) has completed.
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
- Merge a PR up the tree before the Codex review loop completes.
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
- [ ] Waited for the **entire CI run** (all jobs) AND the **entire Codex review** to finish before making any fix — no reacting to partial signals.
- [ ] Waited for the Codex auto-review emoji marker.
- [ ] If no Codex review appeared, asked the human how to proceed.
- [ ] Made the reasonable fixes at own discretion; declined/deferred anything that would overcomplicate (noted why).
- [ ] Escalated only genuine forks (multiple reasonable implementations, or a §10 decision); recorded the human's answer.
- [ ] Merged up with a **merge commit** (not squash, not rebase).
- [ ] Proposed branch deletion to the human.

For `main`:
- [ ] All features merged into root; CI green.
- [ ] Posted consolidated summary to the human.
- [ ] Received **explicit** approval.
- [ ] Merged via merge commit. No force push. No auto-merge.
- [ ] Proposed root-branch deletion.
