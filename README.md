# Whetstone

A local [MCP](https://modelcontextprotocol.io) server that lets any skill learn from use.

Whetstone attaches to an existing skill and maintains a git-tracked, per-skill store of what a
user likes (`LEARNINGS`) and what the skill got wrong (`ISSUES`), so the skill can improve from
ordinary use without a benchmark, dataset, or eval harness. See
[`LEARNING_SKILLS_DESIGN.md`](./LEARNING_SKILLS_DESIGN.md) for the full design.

## Install

Requires Python 3.11+. The base install is light and dependency-free at retrieval time: it uses a
small, deterministic `hashing` embedding backend (no torch, no network).

```sh
pipx install whetstone-mcp
# or: uvx whetstone-mcp
# or: pip install whetstone-mcp
```

Register it with an MCP host (e.g. Claude Code):

```sh
claude mcp add whetstone -- uvx whetstone-mcp
```

This installs two equivalent console scripts — `whetstone` (primary, used throughout this README)
and `whetstone-mcp` (so `uvx whetstone-mcp` / `pipx run whetstone-mcp` resolve without needing the
short name).

For higher-quality embeddings, install the optional extra and set
`embedding_backend = "sentence-transformers"` in config:

```sh
pipx install "whetstone-mcp[embeddings]"   # pulls in sentence-transformers
```

### From source (contributors)

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

```sh
.venv/bin/pip install -e '.[embeddings]'   # pulls in sentence-transformers
```

## Run

Start the stdio MCP server:

```sh
whetstone            # PyPI install
.venv/bin/whetstone   # from-source dev install
```

Register it with an MCP host (e.g. Claude Code) under the server id `whetstone`, pointing the
command at the `whetstone` entry point above.

## Tools

The server exposes five MCP tools:

- **`attach`** — register a skill so Whetstone tracks its learned layer (scaffolds the store).
- **`recall`** — at the start of a task, retrieve the learnings (weighted preferences) and issues
  (mandatory constraints) relevant to an *elaborated* intent.
- **`capture`** — the moment you act on new user feedback, distill it into a scoped, deduped entry
  (a preference → a learning; an always/never rule → an issue).
- **`revise`** — reinforce / weaken / remove / promote / demote an entry `recall` already showed
  (by id); confirmation-gated.
- **`metrics`** — reporting only: the §11 KPIs per skill from each store's `events.jsonl`.

### Maintenance

Store compaction (retiring stale learnings, merging near-duplicate scopes) is deliberately **not**
an MCP tool — it is out-of-band maintenance, run from the command line:

```sh
whetstone compact <skill>            # PyPI install
.venv/bin/whetstone compact <skill>  # from-source dev install
```

## Storage & config

Per-skill stores live under the XDG data dir, defaulting to
`~/.local/share/whetstone/<skill-slug>/`, overridable via the `WHETSTONE_STORE_ROOT` environment
variable or `store_root` in the config file. Configuration is read from
`~/.config/whetstone/config.toml` (XDG config dir); every key also has a `WHETSTONE_*` env
override. Each store is its own git repository:

```
<store-root>/<skill-slug>/
  learnings/<scope-slug>.md   source of truth, grouped by scope
  issues/<scope-slug>.md      source of truth, grouped by scope
  next_ids.json               per-store monotonic id counters
  index.sqlite                derived embedding cache (rebuildable, git-ignored)
  events.jsonl                per-run telemetry for metrics (git-ignored)
  .git/                       version history of the markdown
```

## Development

```sh
.venv/bin/ruff check .
.venv/bin/pytest
```
