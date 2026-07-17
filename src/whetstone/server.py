"""The Whetstone MCP server.

Milestone M0 exposes exactly one tool, ``attach``. The stores it creates are consumed by the
``recall``/``capture``/``revise``/``metrics`` tools in later milestones. ``main()`` runs the
server over stdio.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .store.layout import attach_skill

mcp = FastMCP("whetstone")


@mcp.tool()
def attach(skill: str, path: str | None = None) -> dict:
    """Register a skill so Whetstone tracks its learned layer.

    Optional setup: scaffolds a git-tracked, scope-organized store for ``skill`` and records it in
    the registry. Idempotent — attaching an already-attached skill is a no-op that reports
    ``already_attached``. ``recall``/``capture`` create a store lazily if you skip this. ``path`` is
    an optional reference to the target skill's location, recorded as provenance.

    Returns a summary: ``skill``, ``slug``, ``path`` (store dir), ``created`` (bool), ``status``.
    """
    return attach_skill(skill, skill_path=path)


def main() -> None:
    """Console entry point: run the stdio MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
