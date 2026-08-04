# Security Policy

## Supported Versions

Whetstone is pre-1.0 (currently `0.x`). Security fixes land on the latest released version; there is
no long-term support branch yet.

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities. Instead, use GitHub's
private reporting flow:

1. Go to the [Security tab](https://github.com/HrudithL/whetstone/security/advisories/new) of this
   repository.
2. Click "Report a vulnerability" and fill in the details (impact, reproduction steps, affected
   version).

You should expect an initial response within a few days. If the issue is confirmed, we'll work with
you on a fix and coordinated disclosure timeline before any public advisory is published.

## Scope notes

Whetstone is a **local** MCP server: it stores data on disk under your machine's data/config
directories and talks to your MCP host over stdio — it does not make outbound network calls itself
(the optional `sentence-transformers` embedding backend downloads a model from Hugging Face on first
use, per its own model-caching behavior). Reports involving the local git-tracked store, the MCP
tool surface, or the CLI maintenance commands (`compact`, `promote`, `export`/`import`, `doctor`) are
all in scope.
