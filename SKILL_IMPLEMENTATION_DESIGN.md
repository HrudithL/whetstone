# File-Native "Skill" Implementation & A/B Comparison — Design (Deferred)

> **Status:** **Deferred.** Not being built now. The active project is the MCP server — see [`LEARNING_SKILLS_DESIGN.md`](./LEARNING_SKILLS_DESIGN.md). This doc captures the alternative implementation and the head-to-head experiment so the intent isn't lost.
>
> **Shared substrate:** everything conceptual — the two-store model (`LEARNINGS`/`ISSUES`), the entry semantics, `recurrence`/`recency`/`weight` (learnings only), the capture-contract, promotion/demotion, apply-at-recall (no separate review), supervision, git versioning — is defined in the main doc and is **identical** here. Only the *delivery mechanism* differs.

---

## 1. Why a second implementation exists

We do not know a priori whether a **tool-native** (MCP server) or a **file-native** (skill) design produces better, more reliable learning. Rather than bet, the long-term plan is to build both, keep them **pure and separate**, and measure which wins on the same showcase. This doc holds the file-native design and the comparison methodology. It is deferred until the MCP server is proven.

---

## 2. Implementation B — the skill (file-native)

A pure skill with **no server**. The learned layer is legible markdown co-located with each attached target skill:

```
some-skill/
  SKILL.md            ← base skill, untouched
  LEARNINGS.md        ← index of positive learnings
  ISSUES.md           ← index of mandatory rules
  learnings/          ← categorized detail, loaded on demand (e.g. color.md, layout.md)
  issues/
```

- **Retrieval** is model-judgment: the model reads the index (`LEARNINGS.md`), sees the categories/scopes, and loads only the relevant subfiles — the on-demand pattern skills already use for `references/`. Semantic routing for free, **no embeddings**. (The MCP's centroid+phrase embedding retrieval is replaced by the model reading an index and choosing.)
- **Capture** is the model editing the markdown directly with its native file tools, under the same distill/reconcile rules and the same schema as the main doc (§4.3): for learnings, `recurrence` + `first_seen`/`last_seen` are **stored** and `weight` is **derived on read, never stored**; issues carry no scoring fields — maintained by hand rather than by server code.
- **Apply-at-recall, mandatory issues, promotion/demotion, contradiction flows** — identical semantics to the MCP, but executed as model behavior + file edits instead of tool calls.
- **No `index.sqlite`, no `events.jsonl`.** In normal operation telemetry comes from **git history**. For the A/B showcase, the shared harness emits its own per-run event log for this arm too (§5), so run-level facts git can't see — runs that applied learnings but changed no file, and correction turns that should have been captured but were missed — are still recorded.
- **Organization for the skill may differ from the MCP** and is to be detailed when this is picked up (the MCP uses scope-vector files; the skill may prefer a flatter, index-driven layout for legibility). **TBD.**

Deliberately minimal: two index files + two subfolders. Legibility maximal; infra zero. Claude-Code-only (skills are not portable across runtimes).

---

## 3. The purity rule — no hybrid

The two implementations **must not be blended.** A hybrid (readable files next to an MCP server) is wrong for two reasons:

1. **It contaminates the experiment.** If the model can read the files directly, it will often skip the tools — it already has what it wants — short-circuiting the MCP path. Measuring the server requires the model to go *only* through tools; the skill has no server to compete.
2. **It is overengineered.** Files + index + events + server in one place is bloat. Separated, the bloat vanishes.

---

## 4. Why the experiment is well-motivated — opposite failure modes

| | **Skill (file-native)** | **MCP server** |
|---|---|---|
| Application (using what it has) | Strong — content is in context | At risk — depends on the model invoking tools |
| Selectivity (avoiding bloat at scale) | Weak — grows; retrieval is unmeasurable model-judgment | Strong — `recall` returns only relevant; scales; precision measurable |
| Infra / dependencies | None | Local embedding model + server |
| Portability | Claude Code only | Any MCP host |
| Reliability character | "Just reading" — steady | Higher ceiling; invocation is the soft spot |

Which failure mode bites harder is **empirical** — which is exactly why we measure instead of argue.

---

## 5. The A/B comparison methodology

Run the same showcase harness **twice** — once through the MCP server, once through the skill — under one **hold-constant rule**: identical target skills, identical scripted critique sequences, identical blinded judge rubric, identical supervision mode. The *only* variable is file-native-model vs. tool-native-server.

**Comparison metrics, locked before either is tuned:** repeat-correction rate, application-rate, capture-rate, context cost per run, rubric-quality delta, retrieval precision.

**Instrumentation held constant.** Both arms emit an identical **per-run event log** from the shared harness (the MCP arm already has `events.jsonl`; the file-native arm gets an equivalent from the harness — see §2). Git history alone cannot reconstruct application-rate (a run may read/apply learnings yet change no file) or capture-rate (a correction turn may be missed entirely), so these denominators come from the event log, not the commit trail — measured the same way on both sides.

Whichever wins, the choice is provable: if the skill wins, the product is radically simple; if the server wins, its complexity is justified by data.

---

## 6. When to pick this up

After the MCP server (main doc M0–M4) is built and delivering measurable value. At that point: build Implementation B to parity on the shared substrate, finalize the skill-specific organization (§2), stand up the shared showcase harness, and run the comparison (§5).
