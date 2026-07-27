# Self-Improving Skills — Framework & MCP Server Design

> **Working codename:** Whetstone (a tool that sharpens other tools). Provisional — rename freely.
>
> **Status:** Design draft. This is the primary doc: it describes the whole framework and the **MCP server implementation** in full detail. The MCP server is the entire focus for now.
>
> **Scope of this doc:** MCP server only. A second, file-native "skill" implementation and the A/B comparison between the two are **deferred** and live in a separate doc — see [`SKILL_IMPLEMENTATION_DESIGN.md`](./SKILL_IMPLEMENTATION_DESIGN.md) and §17.
>
> **Relationship to this repo:** This repo (`whetstone`) is the home of the project. It borrows ideas from `great-tables` (skill/reference/example layout, the runner, pinned behavior), which is Whetstone's first **test subject**, not its home.

---

## 1. One-line thesis

**A skill should behave like a model that learns over time.** Whetstone attaches to *any* existing skill and lets it continually improve from real use — capturing what a user likes and what it got wrong, then applying that knowledge on every future run — with **no benchmark, no dataset, and no eval harness required to operate.**

---

## 2. The goal, in plain terms

1. Let a user pick up any skill, build something with it, and — when the output isn't quite right and they critique or correct it — have the skill **automatically get better**, permanently, without re-explaining their preferences next time.
2. Make that improvement **concrete and provable**: a **quantitative** metric drawn from ordinary usage (not a benchmark) plus a **qualitative**, visually obvious before/after.
3. Make it **generalizable to virtually any skill**, not one category (§13).

---

## 3. Origin & motivation

The `great-tables` project reached its quality through a **manual** loop: produce output, have the user add specifications, iterate, fold the judgment back into the skill. That works but is human-driven and skill-specific. Whetstone generalizes it into a **plug-and-play, automatic** mechanism any skill can opt into. The insight we're productizing: the expensive part of a good skill isn't the initial instructions — it's the accumulated taste and the catalog of mistakes it learned not to repeat. Whetstone makes that accumulation automatic and portable.

---

## 4. Core concept & mental model

### 4.1 Base skill vs. learned layer

- **Base skill = the *architecture*.** The canonical, shared, tested logic (e.g. great-tables' flowchart and pinned values). Whetstone **never mutates this.**
- **Learned layer = the *weights*.** Everything learned about a specific user/context. Surfaced and applied at runtime; never baked into the base skill.

The `SKILL.md` (base logic) stays canonical, unmodified, safe, shareable. Improvement lives entirely in the learned layer, injected at runtime.

### 4.2 The two stores — `LEARNINGS` and `ISSUES` — and why both

The learned layer has two stores with **opposite polarity and fundamentally different natures**. This distinction is the heart of the design:

| | `LEARNINGS` | `ISSUES` |
|---|---|---|
| **Polarity** | Positive — "*do* this" | Negative — "*never do* this again" |
| **Nature** | **Soft, subjective preference / taste** | **Absolute, objective rule / constraint** |
| **Origin** | The user expressed a preference | The skill made a concrete mistake, **or** a preference was declared absolute ("always/never") |
| **Application** | Applied by priority (`weight`); soft | **Mandatory** — every relevant one must be handled before completion |
| **Scoring** | Has `recurrence`, `recency`, derived `weight` | **None** — no recurrence, no weight (all are equally mandatory, so ranking is meaningless) |
| **Lifecycle** | **Decays slowly** — taste drifts; can fluctuate up/down and be retired | **Permanent** until explicitly removed/softened |
| **Fluctuation** | Reinforced (+) when repeated, weakened (−) when contradicted | Not reinforced; changed only by explicit promotion/demotion/removal |
| **Dashboard role** | "personalization fit" (a taste metric) | "regressions prevented" (a hard, objective statistic) |

**Why not merge into one store?** A single store cannot cleanly carry two polarities (do-vs-don't would have to be inferred from prose every time), two application semantics (soft/weighted vs. mandatory), two scoring models (scored vs. unscored), or two lifecycles (decays vs. permanent). Separating them makes each structural, unambiguous, and independently measurable.

**The graduation path (critical).** The line between the stores is *soft-vs-absolute*, and entries can cross it:
- **Promote (learning → issue):** when the user declares a preference absolute — "always do X" / "never do Y" — even a subjective preference becomes an *objective* rule and moves to `ISSUES`. Also triggered when a learning's `recurrence` reaches a threshold (see §6). **Promotion always asks the user first** (§6).
- **Demote (issue → learning):** when the user softens a hard rule ("don't guarantee this, just lean that way"), the issue becomes a learning seeded at **recurrence 3** (§6).

### 4.3 Entry schema (differs by store)

**Every entry (both stores):**
- **Body** — human-readable prose, a few short sentences. For issues, worded **objectively** ("Never …", "Always …"). Editable, diffable — not an opaque mutation.
- **Scope** — a short phrase for *when it applies* ("currency columns", "color palette"). The organizing/grouping key and the retrieval unit (§5.4).
- **Provenance** — the critique/turn it came from.

**Learnings only:**
- **`recurrence`** — an integer **net count**: +1 when the preference is repeated/reinstated, −1 when contradicted (§6).
- **`first_seen` / `last_seen`** — timestamps; `last_seen` feeds recency.
- **`weight`** — a **derived** 0–1 priority (not stored), from `recurrence` and `recency` (§4.4).

**Issues have none of the scoring fields** — they are all equally mandatory.

### 4.4 Scoring (learnings only)

Two base signals; everything else is derived. No per-entry "learning rate," no "severity."

- **`recurrence`** *(stored int)* → interpreted as **trust/stability**: high = a repeated, reliable signal.
- **`recency`** *(derived 0–1)* → `recency = exp(−ln2 · Δdays / H)`, Δ = days since `last_seen`, `H` = the configured **half-life** in days (so `recency = 0.5` exactly when `Δ = H`). Interpreted as **freshness**.
- **`weight`** *(derived 0–1, surfaced to the model)*:
  - `r = 1 − 1/(1 + max(recurrence, 0))` — saturating map of the count.
  - **Decay ON (learnings default, slow):** `weight = r × recency`.
  - **Decay OFF:** `weight = r`.

**Interpretation shipped to the model (in `recall`'s `how_to_use`):** *"Each learning has a 0–1 `weight` = how firmly to apply it. Apply high-weight learnings firmly and first; treat low-weight ones as soft suggestions. Issues have no weight — every issue returned is mandatory."*

**Decay is configurable for learnings:** ON but slow by default (`H` = 180-day half-life), and the half-life is tunable (or decay disabled) in config. **Issues do not decay** — they have no `last_seen`/`recurrence`/`weight` to decay on, so there is no issue-decay switch; an issue persists until explicit removal or softening (§6).

---

## 5. The MCP server

A single local process, `whetstone` (MCP server), that any MCP-compatible host (Claude Code, Cursor, Codex, Copilot, …) connects to via one standard config entry. Portability is a core reason for the server: skills and hooks are Claude-Code-only, but an MCP server runs anywhere MCP does.

### 5.1 Storage & on-disk format (scope-organized, markdown is source of truth)

Per attached skill, a git-tracked store. Humans read/edit the markdown; the model never reads it directly (it goes through tools). Derived artifacts live beside it, inside the server — never in the target skill's folder.

```
<server-data>/<skill>/
  learnings/<scope-slug>.md ← source of truth (prose + metadata), grouped by scope
  issues/<scope-slug>.md    ← source of truth, grouped by scope
  index.sqlite             ← derived: per-scope vectors (centroid + phrase), per-entry vectors, entry metadata (rebuildable)
  events.jsonl             ← append-only telemetry (§11)
  .git/                    ← version history of the markdown
```

**Scope is the organizing unit.** Entries are grouped into files by `scope`. The filename is a **bounded, always-hash-suffixed slug** of the scope — `<slug>-<hash>.md`, where the slug is the scope lowercased with spaces→`-` and path separators/`..` stripped (so a model-/user-supplied scope can never write outside `learnings/`/`issues/`), truncated to a fixed length, and the hash is a short digest of the full scope string. Suffixing the hash *unconditionally* (not only on collision) makes the mapping deterministic, collision-free, and length-safe without any persisted lookup table; the human-readable scope phrase lives in each block's `scope:` field. Each entry block is legible and parseable:

```markdown
## L12 · Right-align currency columns
- recurrence: 4
- first_seen: 2026-05-01
- last_seen: 2026-07-10
- scope: currency columns
- provenance: "2026-07-10 — 'make the revenue column right-aligned'"

Right-align currency columns and drop vertical gridlines. The user consistently
prefers a clean, numeric-first look for financial tables.
```

Issue blocks are identical minus the `recurrence`/`first_seen`/`last_seen` fields, with the body worded objectively. **Parser contract:** split on `## `; heading = `<id> · <title>`; the bullet list is metadata; prose after the blank line is the body. `weight` is never stored — computed on read.

### 5.2 Tool surface

Five tools. **Two are in the task loop** (`recall`, `capture`); **`revise`** edits existing entries; `attach` is optional setup; `metrics` is out-of-band reporting. There is **no `review` tool** — the user is the reviewer (§8).

#### `recall(skill, intent, learnings_k=12)` — start of task

Called blindly at the start of any task that might have precedent; returns empty if nothing is learned. It also appends a **per-run event** (run id, `intent`, and the learning/issue ids it returned) to `events.jsonl` — this is the only per-run denominator §11 has for application-rate and regressions-prevented, since a run the user simply accepts produces no follow-up `capture`/`revise`.

- **`intent` is the retrieval query and must be the model's *elaborated* description of what it is about to do — NOT the user's raw prompt.** This is enforced in the description and `how_to_use` because it is the linchpin of retrieval quality (§5.4).

```json
{
  "skill": "great-tables",
  "run_id": "r-2026-07-16-a1b2",
  "learnings": [
    { "id": "L12", "rule": "Right-align currency columns and drop vertical gridlines; prefers a clean, numeric-first look.", "scope": "currency columns", "recurrence": 4, "weight": 0.78 }
  ],
  "issues": [
    { "id": "I3", "rule": "Never apply heavy row banding to tables under 10 rows.", "scope": "small tables" }
  ],
  "how_to_use": "Learnings have a 0–1 weight = how firmly to apply. Issues have NO weight — every issue returned is MANDATORY and must be handled before you complete, regardless of anything else.",
  "capture_contract": "When the user reviews this output and asks for a change, the moment you implement that change also record it: `capture` for something new, `revise` for something already listed above (use its id). Pass this `run_id` on that `capture`/`revise` so the correction joins this run. A preference → a learning; a mistake or an 'always/never' rule → an issue.",
  "conflicts": []
}
```

**`conflicts`** (§M7b) is a purely additive, read-only OBSERVER pass over the *finalized* returned set above (after any skill/global union) — it never changes what was retrieved, ranked, capped (MMR), or the fallback floor. It flags pairs where a returned **learning affirms what a co-returned issue forbids**, applying the exact same test `capture` already applies at write time (§7): prohibition-heuristic asymmetry, overlapping scope (same scope, or the two scopes' phrase-vector similarity clearing the conflict cutoff — otherwise similarly-worded entries in genuinely unrelated contexts would be misflagged), and the cosine cutoff — run pairwise over the small returned set instead of one-candidate-vs-whole-store. Each item is `{"a": <learning id>, "a_origin": "skill"|"global", "a_skill": <skill arg for `revise`>, "b": <issue id>, "b_origin": "skill"|"global", "b_skill": <skill arg for `revise`>, "note": "…"}`. `*_origin` disambiguates ids since the skill store and the global store mint ids from independent counters and can collide; `*_skill` is the literal `skill` to pass to `revise` for that side — for a `"global"`-origin entry this is the reserved global slug, **not** the calling skill, since `revise(skill, entry_id, …)` always resolves `entry_id` against the store named by its `skill` argument. The field is **always present**, `[]` when nothing conflicts. Same-polarity (learning↔learning) contradiction detection is a separate, later concern and is not covered here. Example with a real conflict:

```json
"conflicts": [
  { "a": "L12", "a_origin": "skill", "a_skill": "great-tables", "b": "I3", "b_origin": "skill", "b_skill": "great-tables", "note": "Learning L12 (skill) affirms what issue I3 (skill) forbids — the issue is mandatory (§5.2) and wins. Resolve via `revise(skill='great-tables', entry_id='L12', ...)` or `revise(skill='great-tables', entry_id='I3', ...)`." }
]
```
*Description (read by the model):* "Call at the START of any task that might use an attached skill — call it blindly; empty is fine. **Pass `intent` as a concrete, elaborated description of what you are about to produce, expanding vague requests into their specific dimensions (e.g. 'styling a table: color palette, number formatting, column alignment, row banding, density') — do NOT pass the user's raw words.** Returns learnings (preferences, weighted) and issues (mandatory constraints)."

#### `capture(skill, polarity, body, scope, provenance, run_id?, confirm=false)` — record NEW knowledge

Called when the model implements feedback that isn't about an entry `recall` already surfaced. Distills a scoped rule, then in code: dedups (near-duplicate **learning** → increment `recurrence` + refresh `last_seen`; near-duplicate **issue** → `noop`, since issues have no `recurrence`), detects `LEARNINGS`↔`ISSUES` conflicts, applies the supervision gate (§9), writes markdown, commits, appends an event. Pass the `run_id` returned by `recall` (when this feedback follows a recalled run) so the correction event joins its originating run for telemetry (§11).

```json
{ "status": "committed" | "reinforced" | "noop" | "conflict" | "needs_confirmation", "entry_id": "L13", "recurrence": 1,
  "conflict": { "with_id": "I3", "explanation": "…" },
  "prompt": "…returned only with needs_confirmation — for a supervised add, re-call `capture` with `confirm:true`; a promotion-threshold prompt is resolved via `revise` (see below)…" }
```

`noop` means a duplicate issue was recognized and nothing was added (optionally its provenance was refreshed) — the safeguard against issue-set bloat (§7).

`needs_confirmation` is returned whenever a prompt is required *before* committing; the caller asks the returned `prompt`, then re-calls with the user's choice in `confirm`:
- **Supervised mode** (§9) — gates every new entry **and** every dedup reinforcement (a reinforcement still changes an existing learning's `recurrence`/`last_seen`, so it is a "changed entry" per §9). Re-call with `confirm:true` to commit, or don't re-call to abort.
- **Promotion threshold** (§6) — a dedup pushes a learning's `recurrence` to the threshold. `capture` applies the reinforcement and then returns `needs_confirmation` carrying the entry's `id`; the promotion itself is resolved through **`revise(skill, id, action:"promote", confirm:"promote", body:…)`** (or left a learning by doing nothing). Routing promotion through `revise` — which addresses the entry by `id` — avoids re-running dedup against a reworded body (which could miss the entry and mint a duplicate). So `capture`'s `confirm` is a plain **boolean** (the supervised-commit gate only); the `"promote"`/`"keep"` choices live on `revise`.

*Description:* "Call the moment you act on user feedback about output from an attached skill, when it's something *new*. Cues: a fix ('right-align that'), a preference ('I like muted palettes'), a rejection ('no, not like that'), approval of a specific choice. Classify: taste/preference → `polarity:"learning"`; a mistake to never repeat, or an explicit 'always/never' rule → `polarity:"issue"` (word the body objectively). Generalize into a scoped rule of a few short sentences, capturing the user's *why*. If the server returns `needs_confirmation`, ask the user the returned prompt, then call again with `confirm:true` to commit a supervised add/reinforcement; a promotion-threshold prompt is resolved via `revise(action:"promote")`. If it concerns something `recall` already listed, use `revise` instead."

#### `revise(skill, entry_id, action, body?, scope?, run_id?, confirm=false)` — edit EXISTING knowledge

Used when feedback concerns an entry `recall` already surfaced (the model has the `id`). Optional `body`/`scope` supply **reworded prose** for the entry — required when the action changes how it should read (e.g. `promote` must reword a subjective learning into an objective "Never …"/"Always …" issue; conflict resolution may reword the surviving entry). If omitted, the server keeps the existing prose. `action` ∈:

| action | meaning | notes |
|---|---|---|
| `reinforce` | learning `recurrence` +1, refresh `last_seen` | preference repeated/reinstated. May cross the promotion threshold → see below. |
| `weaken` | learning `recurrence` −1 | preference contradicted. If this takes `recurrence` **below 0**, returns `needs_confirmation` with prompt *"you've gone against this — keep this learning?"* → keep: retain at `recurrence 1`; else `remove`. |
| `remove` | delete the entry (learning or issue) | |
| `promote` | learning → issue | **always** returns a confirm prompt first (§6); on `confirm:true`, moves to `ISSUES`, drops scoring, rewords objectively. |
| `demote` | issue → learning | seeds the new learning at **recurrence 3**. Used when a user softens a hard rule. |

**Issue contradiction is a 3-way prompt.** Calling `weaken`/`remove` on an *issue* returns `needs_confirmation` with prompt: *"This was made a hard rule and you're going against it — fully remove it, soften it to a preference, or no change?"* → `remove` | `demote` (→ learning at recurrence 3) | do nothing.

*Description:* "Call when user feedback concerns a learning or issue that `recall` already showed you (use its `id`). Reinforce when they repeat a preference; weaken when they contradict one; promote when a preference should become an always/never rule; demote when a hard rule should soften; remove when they reject it outright. If the server returns `needs_confirmation`, ask the user the returned prompt, then call again with `confirm` and the chosen action."

#### `attach(skill, path?)` — optional setup
Scaffolds the store, registers the skill. *"Optional: register a skill so Whetstone tracks its learned layer. `recall`/`capture` create a store lazily if you skip this."*

#### `metrics(skill?)` — out-of-band reporting
Computes the KPIs (§11) for the dashboard. *"Reporting only — never call during normal work."*

### 5.3 The call lifecycle

1. *(once, optional)* `attach(skill)`.
2. *(start)* `recall(skill, intent)` with an **elaborated** `intent` → apply learnings by weight; **handle every returned issue** while producing output.
3. Produce output.
4. **The user reviews and gives input** — the only review (§8).
5. *(on implementing that input)* `capture` (new) or `revise` (existing, by id); handle any `needs_confirmation` prompt with the user.
6. *(out-of-band)* the dashboard calls `metrics`.

### 5.4 Scope-based retrieval via embeddings

The mechanism, end to end:

1. **Elaborated query (the linchpin).** The model passes `intent` = a concrete description of what it's about to do, not the user's vague words. This closes the *abstraction gap*: "make a table styled well" embeds nowhere near a scope named `currency formatting`, but the model's elaboration — *"styling a table: color palette, number formatting, alignment, banding, density"* — lives in the same concrete vocabulary as the scopes, so they match. **No threshold value fixes the abstraction gap; fixing the query does.**
2. **Scope vectors + per-entry vectors.** Each scope carries two vectors in `index.sqlite`: its **centroid** (average of its entries' embeddings) and its **phrase** (the scope label embedded). A scope matches if `max(sim(intent, centroid), sim(intent, phrase)) ≥ cutoff`. **Scope *matching* uses only these two vectors** — we chose centroid + phrase over matching every individual entry: it's simpler, uses two stable vectors per scope, and the phrase anchors matching even when a scope's centroid is broad (coherent scopes, kept so by merging below, and the fallback floor cover the residual risk). The individual entry embeddings are computed anyway to form the centroid, so they are **also retained per-entry** in `index.sqlite` — not for scope matching, but because the MMR diverse cap (point 4) scores over per-entry similarity.
3. **Multi-scope, asymmetric cutoffs.** One request touches several scopes, so we select **every** scope above its cutoff (not top-1). **Issues use a lower cutoff than learnings** — erring toward inclusion is *free* for issues (an issue only says "don't do X"; handling a marginally-relevant one costs nothing), but harmful for learnings (a mis-applied preference actively degrades output).
4. **Diverse cap for learnings (MMR).** From all matched-scope learnings, if the count exceeds `learnings_k`, select a **diverse** subset via Maximal Marginal Relevance — iteratively pick the learning maximizing `λ·(weight × similarity) − (1−λ)·max_similarity_to_already_picked` (default `λ = 0.7`). This returns breadth, not `k` near-duplicates, so the model sees a representative majority. **Issues are never capped or subsetted** — all matched issues return (they're mandatory); the issue catalog is kept lean by compaction (§7) instead.
5. **Fallback floor.** If no scope clears the cutoff (a genuinely thin request), return the skill's top-`weight` learnings plus its broadly-scoped issues, so a vague-but-real request never returns empty.

**Calibrating the cutoffs.** Cutoffs are not guessed. Build a small labeled set of `(elaborated intent → truly-relevant scopes)` pairs; sweep the cutoff and pick the value meeting a target precision/recall. Two cutoffs result (issues lower than learnings). Similarity scales differ per embedding model, so the number is never portable — the *calibration procedure* is.

**Scope creation & anti-fragmentation.** The model proposes a `scope` string at capture. The server **merges** two scopes when their **centroids are within ε_c** OR their **name embeddings are within ε_n** (so "currency" and "currency columns" collapse). Merge folds entries into the larger scope and recomputes the centroid. ε_c / ε_n are calibrated constants.

**Embedding model.** A small **local** sentence-embedding model (default candidate `all-MiniLM-L6-v2`, 384-dim, ~80 MB, CPU, offline). No API key. Swappable via config. Brute-force cosine over `index.sqlite` is sufficient at hundreds-of-entries-per-skill scale — no ANN library.

**Worked example.** User: *"make a high quality table that is styled well."* Model passes `intent`: *"Styling a data table well: color palette + row banding, number/currency formatting, column alignment, header emphasis, density."* → matches scopes `color palette`, `formatting`, `alignment`, `banding`, `density` → returns those learnings (MMR-capped to a diverse 12) and all their issues (mandatory). Without elaboration, "styled well" matches none — which is exactly why elaboration is mandatory.

### 5.5 Why the server, concretely

Portability across runtimes; deterministic bookkeeping (schema, dedup, `recurrence`, conflict detection, atomic writes, `weight`) as *code* rather than model-maintained prose that drifts; embedding retrieval, a genuine capability the model lacks; and a runtime-agnostic event log that produces the statistics.

---

## 6. The capture-contract

The learning signal is **the critique, not a file diff** — media-agnostic, richer than a diff (carries the *why*), available even when the artifact isn't. The irreducible fact: *"did a correction just happen?"* is always the model's judgment; the only lever is how reliably the question is asked at the right moment.

Our mechanism: the natural trigger is **the moment the model implements the user's feedback, it also records it.** The `capture_contract` field returned by `recall` plants a standing directive (see §5.2) that (a) fires at implement-time while the correction is fresh, (b) routes to `capture` (new) vs. `revise` (existing, by id already in context), and (c) at the **promotion threshold** (learning `recurrence` reaches **4**, configurable) prompts: *"This has come up ~4 times — promote it to a guaranteed always/never rule?"* → promotes only on user yes.

**Promotion and contradiction-removals always ask the user**, regardless of supervision mode — they are definitional/destructive. The supervision dial (§9) governs only routine additions.

**Graceful degradation:** a missed capture just fails to *record* a preference (recorded next time) — it never ships a *wrong* output. We measure capture-rate (§11) rather than assume it.

---

## 7. Distill & reconcile

Captured critique → a **generalized, scoped candidate rule**, not a raw diff. Then:
- **Dedup:** near-duplicate learning → increment `recurrence`, refresh `last_seen`. A near-duplicate **issue** has no `recurrence` to bump, so it is a **no-op** (optionally refresh provenance) rather than a second mandatory block — this keeps the uncapped issue set from bloating.
- **Conflict:** `capture` surfaces **cross-polarity** contradictions as its `conflict` status, resolved with the user via `revise`. A conflict is flagged when a new entry is highly similar to an existing opposite-polarity entry **and** one side *forbids* what the other *affirms* — decided by a **prohibition heuristic** on the issue text (`never`/`don't`/`avoid`/…). An aligned `Always …` mandate, or an aligned *negative* learning ("prefer avoiding X" next to "never X"), is therefore **not** flagged. Both directions are covered: new learning vs. existing issue (→ `remove`/`demote` the issue) and new issue vs. existing learning (→ `weaken`/`remove`/`promote` the learning), so `recall` can't later return both "do X" and "never do X". **`LEARNINGS`↔`LEARNINGS` contradictions are *not* auto-detected** — embeddings can't separate a contradiction ("left-align") from a near-duplicate ("right-align"), which the dedup path would instead *reinforce* — so they are handled when the user explicitly routes the correction through `revise`/`weaken`. Detection is best-effort over the same-scope embedding neighbourhood already scanned for dedup — no separate subsystem, and a **heuristic** (prose polarity isn't perfectly recoverable from embeddings).
- **Compact:** periodically dedupe, **merge overlapping scopes** (§5.4, centroid within ε_c OR name-embedding within ε_n), and retire stale learnings below the weight threshold (default `weight < 0.15`). **Issues are not auto-retired**; keeping the issue catalog lean is a manual/periodic curation step (they're all mandatory, so bloat there is costly). Compaction runs **out-of-band** — it is not one of the five tools; it is invoked as `whetstone compact <skill>` (or the equivalent function), never during a normal task.

---

## 8. Applying the learned layer — no separate review step

There is **no review tool and no post-output rubric check.** Both stores are applied **upfront, during generation**:
- **Learnings** — preferences to follow, weighted (apply high-weight firmly, low-weight softly).
- **Issues** — **mandatory objective constraints.** The `recall` payload states plainly: *regardless of anything else, every returned issue must be handled before completion.* Because issues are all mandatory and unranked, "handling" is a flat obligation, not a prioritized checklist.

**The user is the reviewer.** They look at the output and give input; that input is the signal `capture`/`revise` record. A model re-checking its own output against a rubric is a redundant protection layer that adds complexity without a signal the user's own review doesn't already provide. (Handling known issues is part of *producing* the output — a hard constraint — not a separate recheck of overall quality.)

---

## 9. Supervision dial

- **Supervised** — confirm every new/changed entry before committing.
- **Balanced** (default) — silently commit clear, non-conflicting learnings; ask on conflict or ambiguity.
- **Autonomous** — commit routine additions silently.

**Independent of the dial:** promotion (learning → issue) and contradiction-driven removals **always** prompt the user (§6). In A the gate lives in `capture`/`revise`, which return `needs_confirmation` when a prompt is required.

---

## 10. Versioning

Every change is committed to **git** — free audit and rollback. The server commits its markdown store; `LEARNINGS`/`ISSUES` diffs are the entire change log, and "which learnings survived vs. were reverted/inverted" is a query over that history (feeds §11).

---

## 11. The statistics — proving value from ordinary usage

The **headline proof is usage telemetry**, not a benchmark. From `events.jsonl` + git:

- **Repeat-correction rate** *(the money metric)* — how often a user re-corrects the *same class* of thing over time; should fall. Visible as `recurrence` growth slowing.
- **Learnings applied per run** and **% survived** (never later overturned).
- **Regressions prevented** — a recalled issue was in scope for a task and *not* reintroduced.
- **Capture-rate** — of turns with a correction, how many were recorded (honesty metric for §6).
- **Retrieval precision** — from embedding match scores against the calibration set.

Reported per-skill; framed honestly as **personalization fit**, not universal quality. KPIs needing a known denominator (capture-rate; regressions-prevented) are measured cleanly in the controlled showcase (§12), where critiques are scripted.

---

## 12. Showcase & dashboard

A **simple documentation website** — proof and marketing.

**Qualitative (persuasion).** For each curated example, three things side by side: **Before** (base skill, no learned layer) · **The learned layer** (the accumulated learnings/issues with `recurrence`/`weight`) · **After** (same skill, with the learned layer). Because great-tables re-renders cheaply, the improvement is *visually obvious*.

**Quantitative (honest, not circular).** A fixed-rubric LLM-as-judge scores before/after on curated examples, with two guardrails since the naive version is circular: **blind the judge** to before/after, and keep the **rubric independent** of the logged learnings. This judge exists **only for the showcase** — never required to operate.

Must cover one example from each of the three skill classes (§13), in priority order.

---

## 13. Generalizability — three skill classes, in priority order

1. **Visual / formatted output** — e.g. `great-tables`. Learnings = color/band/alignment taste; issues = layout regressions. Cheap re-render → the strongest visual demo. **Lead here.**
2. **Direct code-improvement skills** — learnings = preferred patterns; issues = bugs/anti-patterns. Gives **objective, non-LLM-judge ground truth** (tests, lint, types) — the strongest "exact statistics."
3. **Context-organizing skills** — e.g. a frontend-design skill. Improvement is *downstream* and diffuse → hardest to measure. **A stretch**, last.

Common substrate: **critique-as-signal + two prose stores + apply-at-recall** — none assume a medium.

---

## 14. How we differ from existing R&D

- **kayba-ai/recursive-improve** — patches LLM calls, records JSON traces, runs an autonomous `/ratchet` loop that keeps/reverts against **custom evals**.
- **sentient-agi/EvoSkill** — evolutionary search scoring variants on a **held-out validation set**, a git "frontier" of winners.

Both are **benchmark-driven, offline optimizers**. EvoSkill's README concedes benchmark-free evolution and "continuous evolution from regular usage" are open/under-development.

| Axis | recursive-improve / EvoSkill | Whetstone |
|---|---|---|
| Trigger | Batch job over a benchmark | **Online, from real user critique** |
| Needs a dataset/eval to operate | Yes | **No** (evals are showcase-only) |
| Improvement representation | Opaque mutations, trusted via a score | **Legible prose** you can read/edit/diff |
| Optimizes for | Benchmark accuracy | **User taste + regression-avoidance**, media-agnostic |
| Mental model | Research framework | **Plug-and-play, one clear mechanism** |

---

## 15. Open questions & calibration constants

Defined defaults chosen for now (confirm/tune during build):
- **Promotion threshold:** learning `recurrence` = **4**.
- **Learning contradiction:** `weaken` −1; below 0 → ask keep (retain at 1) / remove.
- **Issue softening:** demote → learning seeded at **recurrence 3**.
- **Decay:** learnings ON, half-life `H` = **180 days**; issues OFF.
- **Compaction retire:** learning `weight < 0.15`.
- **Retrieval:** `learnings_k = 12`; MMR `λ = 0.7`; issues uncapped.
- **Cutoffs (learnings, issues) and merge thresholds (ε_c, ε_n):** by calibration against a labeled set; issues lower than learnings.
- **Embedding model:** `all-MiniLM-L6-v2` (candidate), swappable.

Still to resolve: the exact showcase/benchmark harness (curated examples, scripted critiques, blinded rubric, locked metric list); confirmation of the embedding model; packaging of the `whetstone` MCP.

---

## 16. Milestone plan (MCP)

1. **M0 — Attach + store.** `whetstone` MCP with `attach`; seed the git-tracked, scope-organized markdown store (§5.1). Target: `great-tables`.
2. **M1 — Recall + capture loop.** `recall` (elaborated `intent`, centroid+phrase scope match, MMR cap, fallback floor) + the capture-contract; `capture` distills/dedups/commits. Apply-at-recall (§8), no review.
3. **M2 — Revise + scoring + supervision + telemetry.** `revise` (reinforce/weaken/remove/promote/demote + contradiction prompts); the `recurrence`/`recency`/`weight` model with decay toggles; conflict detection; the supervision modes; `events.jsonl` + `metrics`; compaction + scope merging.
4. **M2.5 — Dual-backend CI & test hardening.** Introduce CI (there was none) that runs the suite against both embedding backends as two jobs: the fast, deterministic `hashing` suite on every push (`pytest -m "not embeddings"`, primary signal), and a separate cached `sentence-transformers` calibration suite (`pytest -m embeddings`) that verifies the real semantic behavior the thresholds are tuned for — dedup-by-paraphrase, cross-polarity conflict detection, retrieval relevance — which the deterministic hashing stand-in cannot. `hashing` stays the default backend; ST remains the opt-in `[embeddings]` extra. Bridges M2's engine to M3's showcase, which must run on the ST backend.
5. **M3 — Showcase.** Simple docs site: before / learned-layer / after; telemetry KPIs; blinded judge; one example per class (visual → code → context).
6. **M4 — Generalize.** Attach to a code-improvement skill, then a context-organizing skill; confirm the substrate holds without skill-specific code.

---

## 17. Future work (deferred, separate doc)

A **file-native "skill" implementation** (the same substrate delivered as co-located markdown the model reads/edits directly, no server) and an **A/B comparison** measuring it head-to-head against this MCP server are deliberately deferred. They live in [`SKILL_IMPLEMENTATION_DESIGN.md`](./SKILL_IMPLEMENTATION_DESIGN.md). For now, the MCP server is the entire project.

---

## 18. Summary

Whetstone is a **plug-and-play MCP server that makes any skill continually self-improve from ordinary use** — capturing user taste in `LEARNINGS` (soft, weighted, decaying) and hard rules in `ISSUES` (objective, mandatory, permanent), applying both **upfront on every run** (no separate review; the user is the reviewer), and committing legible improvements to git under a user-chosen supervision level. Prioritization uses just `recurrence` + `recency` → a 0–1 `weight` (learnings only; issues are unranked and mandatory). Retrieval is **scope-based over embeddings of the model's *elaborated intent*** (not the raw prompt), with centroid+phrase scope matching, calibrated asymmetric cutoffs (issues lower), an MMR diverse cap for learnings, and a fallback floor. Capture fires when the model implements feedback; `capture` adds new knowledge, `revise` edits existing (reinforce/weaken/remove/promote/demote), with promotion and contradiction-removals always confirmed by the user. We **prove value from usage telemetry** (repeat-correction rate and friends) as the headline, with a curated before/after showcase for persuasion — operating **online with no benchmark**, in **readable prose**, **general across visual, code, and context skills**.
