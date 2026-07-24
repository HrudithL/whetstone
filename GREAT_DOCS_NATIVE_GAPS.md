# great-docs, native and unassisted — what it gets wrong for an MCP server

**Branch:** `great-docs-native` · **Date:** 2026-07-24 · **great-docs:** 0.15.0 · **Quarto:** 1.9.38 · **Python:** 3.12

## What this branch is

`main` ships a *fixed-up* `/docs` reference site: our `great-docs.yml` was hand-tuned, `pages.yml`
runs a post-build script to synthesize files great-docs forgot, and a README link was rewritten to
silence a build warning. That work is real, but it hides how much of the reference site great-docs
actually produces on its own.

This branch **reverts every one of those interventions** so `/docs` shows *exactly* what
`great-docs build` emits out of the box for this project — nothing added, nothing patched. It is a
diagnostic, not a shipping candidate. Concretely, versus `main`:

| Reverted here | What it was on `main` | Effect |
| --- | --- | --- |
| `great-docs.yml` | had `site_url` + `seo.canonical.base_url` pinned to the `/docs` subpath | regenerated with `great-docs init --force` → the genuine default (both keys commented out) |
| `.github/workflows/pages.yml` | ran `gen_llms_txt.py` after the build and asserted the files exist | now a bare `great-docs build` + assemble, no post-processing |
| `.github/scripts/gen_llms_txt.py` | synthesized `llms.txt` / `llms-full.txt` from `mcp.json` | **deleted** |
| `README.md` | `LEARNING_SKILLS_DESIGN.md` linked as an absolute GitHub URL | reverted to the natural repo-relative link |

Everything else needed to *deploy* the native output at `/docs` (the build step, the `[docs]` extra,
the `great-docs/` gitignore) is kept, because the point is to look at the deployed native site.

**None of the gaps below are fixed here — that is the point.** Every one is recorded with the exact
command and output that produced it, so it is reproducible and can be filed upstream.

### Reproduce

```sh
python3.12 -m venv .venv
.venv/bin/pip install -e ".[docs]"          # great-docs 0.15.0
.venv/bin/great-docs init --force            # regenerate the genuine default great-docs.yml
QUARTO_PYTHON=.venv/bin/python .venv/bin/great-docs build
open great-docs/_site/index.html
```

---

## What native great-docs gets *right* (so the gaps are in context)

Credit where due — with zero config great-docs does a lot, and the parts it nails are exactly why
it's worth pushing on the rest:

- **It discovers the MCP server without being told.** `great-docs build` found all five
  `@mcp.tool()` functions in `src/whetstone/server.py` and built a dedicated **MCP Reference** section
  (`reference/mcp/{attach,recall,capture,revise,metrics}.html`) plus an index. For a tool whose
  *entire* public interface is MCP, this is the feature that matters, and it's automatic.
- **The landing page is a faithful render of the README** — value proposition, install ladder
  (pipx / pip / uvx), host registration, the recall→capture loop, the embeddings extra. It reads well.
- **`package-info.html`** reconstructs the dependency tree (runtime + every extra) with PyPI
  last-published dates.
- **`changelog.html`** is pulled live from GitHub Releases (`v0.1.0`, 2026-07-23, with install snippet).
- **A machine-readable `.well-known/mcp.json`** is emitted describing the server, transport, run
  command, and all five tools with descriptions — the right *idea* for agent discovery.
- **An agent skill export** (`skills.html` + `.well-known/agent-skills/`, `skill.md`), search index,
  dark mode, keyboard nav, SEO/sitemap machinery. The scaffolding is all there.

The problem is not that great-docs ignores MCP servers. It's that its data model, its templates, and
its auxiliary tooling are all built around a **Python package with a numpy-docstring public API**, and
an MCP-only project falls through the cracks of every one of those assumptions.

---

## The gaps

Grouped by area, most-impactful first. Each gap: **what we saw**, the **evidence**, **why it matters
for a project like ours**, and **what great-docs would need to do**.

---

### A. The MCP tool reference — the core deliverable — is under-rendered

This is the one section that documents Whetstone's actual product, so its quality ceiling is the
whole tool's value for us. Native output has four distinct defects here.

#### A1. Prose docstrings yield "No description" for *every* parameter

**What we saw.** On `reference/mcp/recall.html`, the Parameters block is:

```
skill : string          required
intent : string         required
learnings_k : any       No description.
```

Every parameter is listed by name and (sometimes) type, but **none has a description**. The optional
one is explicitly labelled *"No description."*

**Why.** great-docs extracts per-parameter docs from a numpy/google/sphinx **`Parameters:` section**.
Whetstone's tool docstrings are deliberately written as *dense prose aimed at an agent* — the whole
docstring explains when to call the tool and how the arguments interact — not as a structured
`Parameters` block. great-docs has no section to pull from, so it renders the signature and gives up
on descriptions.

**Why it matters.** For an MCP tool the docstring *is the contract the model reads*. A reference that
shows the argument names but "No description" for each throws away the most important half. And the
fix "just write numpy `Parameters:` sections" is at odds with how good MCP tool docstrings are
written — they're prose for a reason.

**What great-docs needs.** Either (a) render the full prose docstring body prominently (it does show
it above the params, but truncated/reflowed — see A2), and stop emitting a hollow "Parameters" table
that reads as *missing* documentation; or (b) parse inline argument mentions from prose; or (c) offer
an MCP-aware mode that treats the docstring as the primary artifact rather than something to be
strip-mined for a `Parameters:` grammar.

#### A2. RST inline literals (`` ``code`` ``) render as raw double back-ticks

**What we saw.** The rendered recall page contains, literally:

> Pass \`\`intent\`\` as a concrete, ELABORATED description … each with a 0-1 \`\`weight\`\` …

The double back-ticks are printed verbatim instead of becoming `<code>` spans.

**Why.** The docstrings use RST-style ` ``double-backtick`` ` interpreted-text (a completely standard
Python convention). With `parser: numpy`, great-docs/griffe passes that text through without
converting RST inline markup to Markdown/HTML code spans.

**Why it matters.** Every tool page is peppered with `` ``skill`` ``, `` ``run_id`` ``,
`` ``already_attached`` `` etc. showing raw back-ticks. It looks broken, and it's pervasive because
good tool docstrings reference their own field names constantly.

**What great-docs needs.** Convert RST inline roles/literals (at minimum ` `` `` ` and `` :code: ``)
when the numpy parser is active, or document that docstrings must be authored in Markdown.

#### A3. Optional-parameter type annotations are dropped (`learnings_k : any`)

**What we saw.** `recall(skill: str, intent: str, learnings_k: int | None = None)` renders as
`skill : string`, `intent : string`, but `learnings_k : any`.

**Why.** The two required, annotated-with-a-plain-type params come through, but the optional
`int | None` param is flattened to `any`. The union/`Optional` annotation on a defaulted parameter is
lost somewhere between the FastMCP `@mcp.tool()` wrapper and great-docs' introspection.

**Why it matters.** "any" is actively wrong — it tells the model the field is untyped when it's a
nullable int. Type fidelity is the reason to auto-generate a reference at all.

**What great-docs needs.** Read the tool's JSON Schema (FastMCP already computes one from the
annotations) rather than re-introspecting the wrapped function, so `int | None` survives.

#### A4. Returns are prose-only; the JSON signature is placeholder-only

**What we saw.** The generated call signature is:

```json
{ "tool": "recall", "arguments": { "skill": ..., "intent": ..., "learnings_k": ... } }
```

— literal `...` for every value, no types inline, no example. The rich return contract (`learnings`,
`issues`, `how_to_use`, `capture_contract`, `run_id`) exists only as reflowed prose, with no
structured Returns rendering.

**What great-docs needs.** Fill argument slots with types or example values from the schema, and give
tool returns the same structured treatment a function's `Returns:` gets.

#### A5. All five tools land in one undifferentiated "General" group

**What we saw.** `reference/mcp/index.html` lists attach / capture / metrics / recall / revise under a
single **General** heading, alphabetized.

**Why it matters.** These tools are a *lifecycle* (attach → recall → capture → revise; metrics is
out-of-band). Native output has no way to express that grouping/order for MCP tools — the `reference:`
config that reorders a Python API doesn't apply to the MCP section.

**What great-docs needs.** Let `reference:`-style grouping/ordering/descriptions apply to MCP tools too.

---

### B. The machine-readable / agent-facing outputs are wrong or missing

An MCP server's *second* audience is other agents. Native great-docs emits agent artifacts, but the
ones it emits contain errors and the ones it promises don't exist.

#### B1. `.well-known/mcp.json` advertises an install extra that does not exist

**What we saw.** The generated manifest:

```json
"installation": {
  "package": "whetstone-mcp",
  "install": "pip install whetstone-mcp[mcp]",
  "repository": "https://github.com/HrudithL/whetstone"
}
```

**The `[mcp]` extra does not exist.** `pyproject.toml` defines exactly four extras — `dev`,
`embeddings`, `showcase`, `docs`. Running the advertised command prints
`WARNING: whetstone-mcp does not provide the extra 'mcp'` and installs the bare package.

**Why.** great-docs hard-codes / guesses an `[<something>]` extra for an MCP package instead of
reading the actual optional-dependency table.

**Why it matters.** This is the exact string an agent parses to install the server, and it's a
fabricated command. Worse than a missing field.

**What great-docs needs.** Derive the install command from real project metadata — no extra unless one
exists (and if one is required, let the project declare which).

#### B2. `llms.txt` / `llms-full.txt` are linked everywhere but never generated

**What we saw.** The landing page and the exported `SKILL.md` both link `llms.txt` and
`llms-full.txt`:

```
Skills   llms.txt   llms-full.txt          (landing "AI / Agents" sidebar)
- [llms.txt](llms.txt) — Indexed API reference for LLMs      (SKILL.md)
- [llms-full.txt](llms-full.txt) — Comprehensive documentation for LLMs
```

Neither file exists in `great-docs/_site/` (`ls llms*.txt` → no matches). **Dead links, on the
AI-agent entry points specifically.**

**Why.** great-docs writes `llms.txt` only when the package has a populated **Python `api-reference`**.
Whetstone's reference is *MCP*, not Python, so the generator skips the files but the templates still
link them unconditionally — and there is no toggle. (This is precisely the upstream gap the deleted
`gen_llms_txt.py` was working around.)

**Why it matters.** `llms.txt` is *the* convention for exposing docs to LLMs. For an
MCP-server-that-serves-agents, having those be the broken links is the worst possible place for them.

**What great-docs needs.** Generate `llms.txt` from whatever reference exists (MCP tools are perfect
source material), or don't emit the links when it won't emit the files.

#### B3. great-docs' own `check-links` does not catch B2

**What we saw.** `great-docs check-links` → **"✅ All links are valid!"** — while the landing page
ships dead `llms.txt` links.

**Why.** The link checker crawls source `.qmd`/`.md` files and external URLs; it doesn't validate the
unconditional links injected by the *landing/skill templates* at render time.

**Why it matters.** The one native tool that should have caught B2 reports a clean bill of health,
so nothing warns you.

**What great-docs needs.** Check the generated `_site` output, including template-injected links, not
just authored source.

#### B4. The skill export is named `package` and its install commands don't work

**What we saw.** `.well-known/agent-skills/index.json` names the skill `"package"`, and
`skills.html` offers three install methods, all pointing at **github.com blob URLs**:

```
npx skills add https://github.com/HrudithL/whetstone/
curl -O https://github.com/HrudithL/whetstone/skill.md
Fetch the skill file at https://github.com/HrudithL/whetstone/skill.md and follow the instructions.
```

- The skill name `package` is a generic placeholder, not `whetstone`.
- `curl -O https://github.com/HrudithL/whetstone/skill.md` downloads GitHub's **HTML page**, not the
  file — that path 404s / returns repo chrome. The real `skill.md` is served by the docs *site*.
- `npx skills add …/whetstone/` points at the repo root, not the skill.

**Why.** With `site_url` unset (native default), great-docs falls back to the GitHub remote for the
skill's base URL — the wrong host for fetching built artifacts.

**What great-docs needs.** Point skill-install commands at the deployed docs site (where `skill.md`
actually lives), infer the subpath, and derive the skill name from the project, not "package".

---

### C. URLs, canonicalization, and SEO are wrong out of the box

Every absolute URL great-docs generates is wrong in the same two ways: **wrong host casing** and
**no subpath awareness**.

#### C1. Canonical / OpenGraph URLs use the wrong host and drop the subpath

**What we saw.** `index.html`:

```html
<link rel="canonical" href="https://HrudithL.github.io/whetstone/">
<meta property="og:url" content="https://HrudithL.github.io/whetstone">
```

Two problems: **`HrudithL`** (the GitHub *username* casing) — but `*.github.io` hostnames are
lowercased by GitHub, so the canonical host is `hrudithl.github.io`; and the site actually deploys at
`…/whetstone/**docs/**`, which is absent.

**Why.** Native great-docs derives the host from the git remote's owner string verbatim, and with
`site_url` commented out it has no subpath to honor.

#### C2. `sitemap.xml` — all 12 URLs wrong

```xml
<loc>https://HrudithL.github.io/whetstone/</loc>
<loc>https://HrudithL.github.io/whetstone/reference/mcp/attach.html</loc>
…
```

Wrong host casing, and no `/docs`. Every sitemap entry points at a URL that doesn't exist.

#### C3. `robots.txt` — wrong sitemap URL

```
Sitemap: https://HrudithL.github.io/whetstone/sitemap.xml
```

Same two defects.

#### C4. The config makes this a trap: two different keys

Fixing C1–C3 is *not* just setting `site_url`. On `main` we discovered `site_url` alone doesn't move
the canonical/sitemap/robots — those read a **separate** key, `seo.canonical.base_url`. Native output
sets neither, and the `init` template surfaces only `site_url` (with `seo` entirely absent), so the
obvious fix silently doesn't work.

**Why it matters for us.** We deploy at a subpath (`/docs`, next to the Quarto showcase at `/`).
Subpath deployment is a first-class case for a *reference* site that lives beside a marketing site —
and it's exactly the case native output gets wrong at every URL.

**What great-docs needs.** Lowercase `*.github.io` hosts; infer the Pages subpath (or derive from a
single `site_url`); and collapse `site_url` vs `seo.canonical.base_url` into one source of truth.

---

### D. The auxiliary tooling doesn't understand MCP-only packages

#### D1. `great-docs lint` ignores MCP tools entirely

**What we saw.** `great-docs lint`:

```
Package: whetstone   Exports checked: 1
missing-docstring [1 error]
  ❌ __version__   Public export '__version__' has no docstring.
❌ 1 error(s), 0 warning(s)
```

It lints the **one** Python export (`__version__`) and flags it, while the five MCP tools — the
actual documented surface — are not linted at all.

**Why it matters.** `lint` is Python-API-centric; for an MCP-only package it produces a noise error
about a version string and zero signal about the tools. Its verdict is meaningless here.

**What great-docs needs.** Lint the MCP tool docstrings (missing description, missing return docs,
etc.) when that's the documented surface.

#### D2. No CLI reference (needs Click); Python API empty (by design)

Both **expected**, recorded for completeness:

- **CLI:** `Skipped (CLI not enabled)`. Whetstone's `serve` / `compact` CLI is hand-rolled `argv`
  parsing in `server.main()`, not a Click object, so there's nothing to introspect. *Acceptable* — but
  it means a project with a real CLI that isn't Click gets no CLI docs.
- **Python API:** `No documentable exports found — skipping API reference`. `__all__ = ["__version__"]`
  by design — the store/scoring internals are not public. *Correct behavior*, and the reason the whole
  value here rides on the MCP section (Area A).

---

### E. Build ergonomics

#### E1. README repo-relative links break in the landing render

**What we saw.** Reverting the README link to its natural `./LEARNING_SKILLS_DESIGN.md` reproduces:

```
[!!] WARN: Unable to resolve link target: LEARNING_SKILLS_DESIGN.md
```

**Why.** great-docs renders the README as the landing page but treats it as a docs-site source, so a
link to a repo file that isn't part of the docs site is "unresolvable." On `main` this was silenced by
rewriting the link to an absolute GitHub URL — a workaround, not a fix.

**Why it matters.** Every project's README links sibling repo files (`CONTRIBUTING.md`, design docs).
Out of the box each becomes a build warning, pushing you to distort the README for the doc tool.

**What great-docs needs.** Resolve repo-relative README links to their GitHub blob URL automatically
(it already knows the remote), instead of warning.

#### E2. `init` is interactive and one-shot

`great-docs init` refuses to run non-interactively (needs `--force` to regenerate) and prompts. Fine
for a local bootstrap, but it means CI can only ever run `build`, and there's no "regenerate default
config" that's safe to run unattended. Minor.

---

## Summary — what great-docs needs to document an MCP server well

The through-line: **great-docs' data model is "a Python package with a numpy-docstring public API."**
An MCP server is a *different shape* — its public surface is a set of tools with prose,
agent-oriented docstrings and a JSON-schema contract, deployed as a reference beside a marketing
site, consumed partly by other agents. It falls through the assumptions everywhere. To document a
project like ours, native great-docs would need to:

1. **Treat the MCP tool set as a first-class documented surface, not a bolt-on.** Read each tool's
   JSON Schema for accurate parameter types (A3) and structured returns (A4); render the prose
   docstring as the primary contract instead of strip-mining it for a `Parameters:` grammar and
   printing "No description" (A1); convert RST inline markup (A2); allow grouping/ordering (A5); and
   lint *those* docstrings (D1).
2. **Make the agent-facing artifacts correct.** No fabricated install extras in `mcp.json` (B1);
   generate `llms.txt` from the MCP reference or stop linking it (B2); make `check-links` validate the
   rendered output including template-injected links (B3); name and point the skill export correctly
   at the deployed site (B4).
3. **Get absolute URLs right for a subpath deployment.** Lowercase `*.github.io` hosts, infer the
   Pages subpath, and unify `site_url` / `seo.canonical.base_url` so canonical, OpenGraph, sitemap,
   and robots are correct without a hidden second key (C1–C4).
4. **Resolve README repo-relative links** instead of warning, so the source README doesn't have to be
   distorted for the doc build (E1).

Items 1 and 2 are the ones that decide whether great-docs is *good* at documenting an MCP server, as
opposed to merely aware that one exists. Native output today clears the "aware" bar impressively and
falls short of the "good" bar in exactly the places that are the product's real interface.
