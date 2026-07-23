# Great Docs spike — auto-generated `/docs` reference site

**Branch:** `spike/great-docs-site` · **Date:** 2026-07-22 · **great-docs:** 0.15.0 · **Quarto:** 1.9.38 · **Python:** 3.12

This is a **spike**: evaluate [great-docs](https://posit-dev.github.io/great-docs/) (Posit's
Quarto-based documentation generator for Python packages) as the source of a reference site hosted at
`<site>/docs`, alongside the existing Quarto *showcase* site at the root. It records exactly what was
run, what worked, and what did not, so the decision is auditable and the build is reproducible.

The guiding question the spike had to answer honestly: **great-docs documents a Python *package's*
public API + CLI. Whetstone's value is the MCP server, not a Python API, and we do not care to
document the harness or internals. How much of Whetstone can great-docs actually document well?**

## TL;DR

- **The headline result flips the prior assumption.** great-docs 0.15.0 has **native MCP awareness**:
  with *zero* manual config it discovered the FastMCP server's five `@mcp.tool()` functions
  (`attach`, `recall`, `capture`, `revise`, `metrics`) and generated a dedicated **"MCP Reference"**
  section — each tool rendered as a JSON tool-call signature with its full docstring. This is exactly
  the product's real interface, so the tool documents the part we *do* care about.
- **The Python API reference is empty — by design, and that is fine.** `src/whetstone/__init__.py`
  sets `__all__ = ["__version__"]`, so `great-docs scan` finds 1 export (a version string). All the
  store/retrieval/scoring modules are internal implementation we explicitly don't want to publish.
- **CLI auto-docs do not apply.** great-docs' CLI support targets **Click** command objects.
  Whetstone's CLI (`whetstone serve` / `whetstone compact <skill>`) is hand-rolled `argv` parsing in
  `server.main()`, so there is nothing for great-docs to introspect. Documented in prose instead.
- **Subpath hosting at `/docs` works** (relative asset offsets). SEO files (`sitemap.xml` /
  `robots.txt` / canonical) read a *separate* key, `seo.canonical.base_url` — now set (see Gap 1).
- **Integration is the real work.** GitHub Pages serves one site per repo, and `great-docs
  setup-github-pages` would write a *second*, conflicting deploy workflow. Instead, the existing
  `pages.yml` was extended to build both and assemble one artifact (root showcase + great-docs at
  `/docs/`).

## Reproduce

Prerequisites: Quarto on PATH (`quarto --version` → 1.9.38 here) and the dev venv.

```sh
# 1. Install great-docs (added as the [docs] extra on this branch)
.venv/bin/pip install -e ".[docs]"          # or: .venv/bin/pip install great-docs

# 2. See what great-docs can document BEFORE generating anything
.venv/bin/great-docs scan                    # -> "Using __all__ with 1 exports" (just __version__)

# 3. Bootstrap config (already committed as great-docs.yml on this branch)
.venv/bin/great-docs init                    # writes great-docs.yml

# 4. Build the reference site (ephemeral output under great-docs/, git-ignored)
QUARTO_PYTHON=.venv/bin/python .venv/bin/great-docs build
#   -> great-docs/_site/  (open great-docs/_site/index.html)

# 5. Preview locally
QUARTO_PYTHON=.venv/bin/python .venv/bin/great-docs preview
```

`great-docs.yml` is the committed source of truth. The generated `great-docs/` tree (Quarto sources
+ `_site`) is **ephemeral and git-ignored** — it is rebuilt by `great-docs build` in CI, never
committed.

## What works ✅

| Capability | Result |
|---|---|
| **MCP tool reference (auto)** | All 5 `@mcp.tool()` functions detected with no config → `great-docs/_site/reference/mcp/{attach,recall,capture,revise,metrics}.html` + an MCP index. Signatures shown as JSON tool calls; docstrings rendered. The generated `_quarto.yml` sets `data-gd-ref-sections="api,mcp"` and a full "MCP Reference" sidebar. |
| **Landing page from README** | `index.qmd` is built from `README.md`, with an auto sidebar: PyPI + source links, `Requires`/`Provides-Extra` from `pyproject.toml`, author card, MIT license badge. |
| **License + Contributing pages** | `LICENSE` and `CONTRIBUTING.md` picked up automatically → `license.html`, `contributing.html`. |
| **`.well-known/mcp.json` manifest** | Auto-generates an MCP server manifest listing all 5 tools + descriptions (see Gap 3 for the one inaccuracy). |
| **Agent-skill export** | Generates an installable agent "skill" (`.well-known/agent-skills/…/SKILL.md`, `skills.html`) with `npx skills add …` / Codex install snippets. |
| **SEO / sitemap / robots** | `sitemap.xml`, `robots.txt`, dark-mode toggle, GitHub widget, copy-code, keyboard nav — all injected. |
| **Subpath relocation** | Nested pages use relative offsets (`quarto:offset` = `../../`), so the tree drops under `/docs/` without rewriting asset paths. |

## What does not apply / fails ❌

| Item | Why |
|---|---|
| **Python API reference** | Empty: `__all__ = ["__version__"]`. `great-docs scan` → "1 export". Intentional — internals (store/retrieval/scoring/…) are not a public API and we don't want them published. |
| **CLI auto-docs** | great-docs expects a **Click** command object (`cli.module` / `cli.name`). Whetstone's `serve`/`compact` CLI is manual `argv` parsing in `server.main()`. No auto command tree; covered in prose only. |
| **`init` interactivity in CI** | `great-docs init` prompts (`Add 'great-docs/' to .gitignore? [Y/n]`) and errors on EOF when non-interactive. Fine — `init` is a one-time local bootstrap; CI only runs `build`. `great-docs/` is git-ignored on this branch regardless. |

## Gaps found 🐞 — and their resolution

All four were addressed on the follow-up branch `whetstone-great-docs-fixes`.

1. **`sitemap.xml` + `robots.txt` + `<link rel=canonical>` ignored `site_url`.** They are generated
   from a **separate** config key, `seo.canonical.base_url`, *not* `site_url`. Left unset, great-docs
   derived a repo URL with the wrong owner casing (`HrudithL`) and no `/docs/` subpath. **FIXED** by
   setting `seo.canonical.base_url: "https://hrudithl.github.io/whetstone/docs/"` in `great-docs.yml`.
   Verified: sitemap `<loc>`, robots `Sitemap:`, and per-page canonical links all now use the correct
   host + subpath.
2. **Landing page links `llms.txt` / `llms-full.txt` that `build` did not emit → dead links.** Root
   cause (in `great_docs/core.py`): the landing template appends these links *unconditionally*, but
   `_generate_llms_txt` returns early unless `_quarto.yml` has a populated **`api-reference`** section.
   Whetstone has an *MCP* reference, not a Python api-reference, so no file is written, and there is no
   config toggle to hide the links. **Upstream great-docs limitation for MCP-only packages.**
   Worked around by synthesizing both files from the build's own `.well-known/mcp.json`
   (`.github/scripts/gen_llms_txt.py`, run in the deploy pipeline). Verified both land in
   `_deploy/docs/` so the links resolve.
3. **~~`.well-known/mcp.json` run command is wrong~~ — NOT A BUG (this spike doc was mistaken).** The
   manifest advertises `python -m whetstone.server`, and `src/whetstone/server.py` **does** have
   `if __name__ == "__main__": main()`, so that command starts the stdio server correctly (verified:
   clean start, exit 0 on stdin EOF). No change needed; claim corrected here.
4. **Broken-link warning `WARN: Unable to resolve link target: LEARNING_SKILLS_DESIGN.md`** — the
   README (source of the landing page) used a repo-relative link. **FIXED** by making it an absolute
   GitHub blob URL (still correct on GitHub); the warning is gone.

## Hosting at `<site>/docs` — the integration

**Constraint:** one GitHub Pages site per repo. The repo already deploys the Quarto *showcase* to the
Pages **root** via `.github/workflows/pages.yml`. Running `great-docs setup-github-pages` would write
a *second* workflow (`.github/workflows/docs.yml`) that also deploys to Pages → the two would fight
over the single Pages artifact. **So `setup-github-pages` is deliberately NOT used.**

**Solution (implemented on this branch):** extend the existing `pages.yml` to build both and assemble
one artifact:

```
_deploy/                <- uploaded to Pages
├── index.html          <- existing Quarto showcase (site root)
├── methodology.html
├── metrics.html
├── triptych.html
└── docs/               <- great-docs output (great-docs/_site/*)
    ├── index.html
    ├── reference/mcp/{attach,recall,capture,revise,metrics}.html
    ├── license.html · contributing.html · skills.html
    └── .well-known/{mcp.json, agent-skills/…}
```

`site_url` in `great-docs.yml` is `https://hrudithl.github.io/whetstone/docs/`. Deployed and verified
live after the initial merge; the gap fixes below refine it.

## Changes — initial spike (merged, PR #28)

- `great-docs.yml` — committed config (module `whetstone`, numpy parser, `site_url` = the `/docs`
  subpath). Source of truth; `reference:` intentionally empty.
- `.github/workflows/pages.yml` — build root showcase **and** great-docs, assemble `_deploy/`
  (great-docs at `/docs`), upload the combined artifact.
- `pyproject.toml` — new `[docs]` extra (`great-docs>=0.15`).
- `.gitignore` — ignore the ephemeral `great-docs/` build dir (config stays committed).

## Changes — gap fixes (branch `whetstone-great-docs-fixes`)

- `great-docs.yml` — add `seo.canonical.base_url` = the `/docs` subpath (Gap 1).
- `README.md` — `LEARNING_SKILLS_DESIGN.md` link → absolute GitHub URL (Gap 4).
- `.github/scripts/gen_llms_txt.py` + a `pages.yml` step — synthesize `llms.txt` / `llms-full.txt`
  from the built `mcp.json` so the landing links resolve (Gap 2 workaround).
- This doc — corrected Gap 3 (not a bug).

## Recommendation

great-docs is a **good fit for a `/docs` reference site** specifically because of its MCP-tool
auto-detection — it documents Whetstone's actual interface, not its irrelevant Python internals, with
almost no authoring. Gaps 1, 2, and 4 are resolved and Gap 3 was a false alarm. The one remaining
nice-to-have (not blocking): a short prose CLI page (`serve` / `compact`), since CLI auto-docs target
Click and don't apply here. The Gap 2 llms shim should be retired if great-docs later emits llms files
for MCP-only packages (worth reporting upstream, given great-docs is a Posit tool).
