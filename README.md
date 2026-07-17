# Whetstone

A local [MCP](https://modelcontextprotocol.io) server that lets any skill learn from use.

Whetstone attaches to an existing skill and maintains a git-tracked, per-skill store of what a
user likes (`LEARNINGS`) and what the skill got wrong (`ISSUES`), so the skill can improve from
ordinary use without a benchmark, dataset, or eval harness. See
[`LEARNING_SKILLS_DESIGN.md`](./LEARNING_SKILLS_DESIGN.md) for the full design.

This is **milestone M0 — attach + store**: the scope-organized markdown store and the `attach`
tool. The `recall`, `capture`, `revise`, and `metrics` tools land in later milestones.

## Install

Requires Python 3.11+.

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

## Run

Start the stdio MCP server:

```sh
.venv/bin/whetstone
```

Register it with an MCP host (e.g. Claude Code) under the server id `whetstone`, pointing the
command at the `whetstone` entry point above.

## Storage

Per-skill stores live under the XDG data dir, defaulting to
`~/.local/share/whetstone/<skill-slug>/`, and are overridable via the `WHETSTONE_STORE_ROOT`
environment variable or `store_root` in `~/.config/whetstone/config.toml`. Each store is its own
git repository:

```
<store-root>/<skill-slug>/
  learnings/<scope-slug>.md   source of truth, grouped by scope
  issues/<scope-slug>.md      source of truth, grouped by scope
  .git/                       version history of the markdown
```

## Development

```sh
.venv/bin/ruff check .
.venv/bin/pytest
```
