# Whetstone

**Give any AI skill a memory of your taste — so you stop correcting the same things every session.**

Whetstone is a local [MCP](https://modelcontextprotocol.io) server that lets *any* skill improve
from ordinary use. It attaches to a skill you already use and keeps a git-tracked, per-skill store
of two things:

- **Learnings** — what you *like* (soft, weighted, decaying preferences — "negatives in parentheses",
  "warm palette, not green", "square corners").
- **Issues** — what the skill got *wrong* (hard rules it must never repeat).

At the start of a task it **recalls** the relevant ones and applies them; when you correct the
output, it **captures** the correction so it sticks next time. No benchmark, no dataset, no
fine-tuning — it learns from a *single* correction, immediately, and the whole memory is plain
markdown in a git repo you own.

> A skill is the **architecture** — shared, tested, canonical, the same for everyone. Whetstone is
> the **weights** — everything learned about *your* preferences, layered on at runtime and never
> baked into the skill.

## Why you'd use it

- **Corrections stick.** Tell it once; it's re-applied on every future run of that skill — you never
  re-explain the same preference.
- **Any skill, any MCP host.** It never modifies the skill; it adds a learned layer on top.
- **Transparent and yours.** Every preference is legible markdown, versioned in git — read it, edit
  it, `git revert` it. Nothing leaves your machine.
- **Light.** The base install pulls in only the MCP SDK and uses a deterministic hashing backend (no
  torch, no network); upgrade to embedding-based recall when you want.

---

## Install — from scratch

Requires **Python 3.11+**.

### 1. Install the server

```sh
pipx install whetstone-mcp      # recommended: isolated, puts `whetstone` on your PATH
# or:
pip install whetstone-mcp       # into the current environment
# or, run it without installing:
uvx whetstone-mcp
```

This installs two equivalent commands — `whetstone` (primary) and `whetstone-mcp`. Running either
starts the stdio MCP server; it waits for an MCP client, so you don't run it by hand — a host does.

### 2. Register it with your MCP host

Point your host at the server under the id `whetstone`. For [Claude Code](https://claude.com/claude-code):

```sh
claude mcp add whetstone -- whetstone            # if installed (pipx / pip)
claude mcp add whetstone -- uvx whetstone-mcp    # no install; uv fetches & runs on demand
```

Any other MCP host works too — configure a stdio server whose command matches how you installed it:
`whetstone` (pipx / pip), `uvx whetstone-mcp` (no install), or the venv's `.venv/bin/whetstone`
(from source).

### 3. Use it — the loop

Once registered, a skill (or your agent) uses Whetstone around each task:

1. **`recall`** at the start of a task → Whetstone returns the learnings + issues relevant to what
   you're doing, and the skill applies them.
2. You review the output and **correct** something.
3. **`capture`** turns that correction into a scoped entry — a preference becomes a *learning*, an
   "always/never" becomes an *issue*. Next time, `recall` surfaces it and it's applied automatically.

`attach` scaffolds a skill's store the first time it's used; `revise` lets you reinforce, weaken, or
remove an entry by id.

### Optional: higher-quality recall

The default `hashing` backend is deterministic and dependency-free. For embedding-based retrieval
(better matching of your intent to stored preferences):

```sh
pipx install "whetstone-mcp[embeddings]"          # fresh install, with the extra
pipx inject whetstone-mcp sentence-transformers   # add to an existing pipx install
pip install "whetstone-mcp[embeddings]"           # pip
```

then set `embedding_backend = "sentence-transformers"` in `~/.config/whetstone/config.toml`.

### From source (contributors)

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/whetstone            # run the server
```

---

## The tools

Whetstone exposes five MCP tools:

- **`attach`** — register a skill so Whetstone tracks its learned layer (scaffolds the store).
- **`recall`** — at task start, retrieve the learnings (weighted preferences) and issues (mandatory
  constraints) relevant to an *elaborated* intent.
- **`capture`** — the moment you act on feedback, distill it into a scoped, deduped entry.
- **`revise`** — reinforce / weaken / remove / promote / demote an entry `recall` showed (by id);
  confirmation-gated.
- **`metrics`** — reporting only: per-skill KPIs drawn from each store's event log.

Store compaction (retiring stale learnings, merging near-duplicate scopes) is deliberate out-of-band
maintenance, run from the command line rather than exposed as a tool:

```sh
whetstone compact <skill>
```

## Storage & config

Each skill's learned layer is its **own git repository** under the XDG data dir (default
`~/.local/share/whetstone/<skill-slug>/`; override with `WHETSTONE_STORE_ROOT` or `store_root` in
config):

```
<store-root>/<skill-slug>/
  learnings/<scope-slug>.md   your preferences, grouped by scope (source of truth)
  issues/<scope-slug>.md      hard rules, grouped by scope (source of truth)
  index.sqlite                derived embedding cache (rebuildable, git-ignored)
  events.jsonl                per-run telemetry for metrics (git-ignored)
  .git/                       full version history of the markdown
```

Configuration is read from `~/.config/whetstone/config.toml`; every key also has a `WHETSTONE_*`
environment override.

For the full design see
[`LEARNING_SKILLS_DESIGN.md`](https://github.com/HrudithL/whetstone/blob/main/LEARNING_SKILLS_DESIGN.md),
and the [showcase site](https://hrudithl.github.io/whetstone/) for the before/after proof across the
great-tables, frontend-design, and pptx skills.

## Development

```sh
.venv/bin/ruff check .
.venv/bin/pytest
```

---

## Why not just a skill — or another service?

Whetstone does one thing the alternatives don't: it turns *your ongoing corrections* into a
**legible, per-skill memory that's applied automatically** — without touching the skill or training
anything.

- **vs. editing the skill (`SKILL.md`) itself.** A skill is the shared, canonical *architecture* —
  the same for everyone. Your taste is personal, evolving, and sometimes deliberately against the
  skill's defaults. Hand-editing a skill for every preference doesn't scale, isn't retrieved by
  relevance, has no notion of weight / decay / priority or "always/never" promotion, and mutating a
  shared skill risks everyone who uses it. Whetstone leaves the skill untouched and layers your
  preferences on at runtime.
- **vs. a generic "memory" or RAG over past chats.** Those recall raw conversation text. Whetstone
  captures **distilled, scoped rules** with polarity — a *preference* (soft, weighted, decaying) vs.
  an *issue* (a hard, mandatory rule) — deduped and conflict-checked, then retrieved by your
  elaborated intent at the moment of use. It's structured to be *re-applied*, not just quoted back.
- **vs. fine-tuning or benchmark-driven optimizers** (evolutionary search, eval-ratcheting loops).
  No training run, no dataset, no eval harness required to operate — it learns from a *single*
  correction, online, from real critique. And the result is prose you can read, edit, diff, and
  `git revert`, not opaque weights trusted via a score. It optimizes for *your* taste and *not
  repeating mistakes*, across any medium — not a benchmark number.
- **vs. a hosted SaaS.** It's local and git-native: your preferences live in a repo you own —
  auditable, portable, private. Nothing leaves your machine.

The base skill is the architecture; Whetstone is the weights.
