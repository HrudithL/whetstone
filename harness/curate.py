"""Curate a raw Agent-SDK transcript into a human/site-consumable view (M6c).

``generate.py``'s ``AgentGenerator`` collects the *raw* transcript — every message the model
exchanged while producing a scenario's artifact, serialized to real nested JSON (see
``_message_to_dict``). That raw file is complete ground truth but noisy: it interleaves long
internal "thinking" deliberation and routine filesystem/shell tool calls with the handful of turns
that actually matter to a reader — a Whetstone MCP tool call (the load-bearing moment the showcase
exists to prove) or the final artifact being written.

:func:`curate_transcript` produces that reduced view. It never destroys the raw file (``run.py``
writes both ``transcript.json`` and ``transcript.curated.json`` alongside each other, the same
pattern as ``runs.jsonl``/``summary.json`` coexisting) and it never silently drops content — a
block that's cut is replaced with a structured ``{"type": "elided", ...}`` marker so a reader can
tell "intentionally omitted" apart from "genuinely short/empty".
"""

from __future__ import annotations

# Whetstone's MCP tools — kept in full wherever a tool-use/tool-result turn touches one of these,
# since that is precisely the load-bearing moment the showcase exists to demonstrate. Matched
# against the trailing `__`-segment of the tool's wire name (an MCP tool is typically namespaced
# as `mcp__<server>__<tool>`, e.g. `mcp__whetstone__recall`) so this doesn't hardcode the server
# name. NOTE: today's harness transcripts never actually contain these — `AgentGenerator` does not
# mount Whetstone as an MCP server for the live model; `harness/run.py` calls `recall`/`capture`/
# `metrics` directly in Python. This rule is forward-looking (a future harness revision, or a
# skill that itself invokes Whetstone) rather than dead code for the shape of today's data.
_WHETSTONE_TOOL_NAMES = frozenset({"attach", "recall", "capture", "revise", "metrics"})

# The final generated artifact / code-writing tool calls — always load-bearing (Edit for existing
# files; Write for a from-scratch build script or a web skill's index.html).
_ARTIFACT_TOOL_NAMES = frozenset({"Write", "Edit"})

# A "thinking" block at or under this length reads like a short, already-narrative decision note
# (the kind Part A's spec calls out as worth keeping) rather than genuine internal deliberation;
# above it, elide. Chosen against the observed range (100-2700+ chars per block in real runs).
_THINKING_ELIDE_THRESHOLD = 200

# A "text" block at or under this length reads like a brief, already-narrative aside; above it,
# elide. This is NOT just an assistant-verbosity guard: the SDK delivers a mounted Skill's full
# instructions (e.g. the ~7KB Great Tables SKILL.md body — see
# harness/out/great-tables/gtcars_hp_price/warm/transcript.json) as a plain **user** `TextBlock`,
# not a `tool_result` — so without this rule that multi-kilobyte payload would sail through
# `_curate_block` untouched via the catch-all `return block`, even though the surrounding `Skill`
# tool_use/tool_result turn is correctly elided. 500 chars comfortably covers a real short
# narrative note while catching any skill-instructions-sized dump.
_TEXT_ELIDE_THRESHOLD = 500


def _is_whetstone_tool(name: str) -> bool:
    """True if a tool_use/tool_result block's ``name`` is one of Whetstone's MCP tools."""
    return name.rsplit("__", 1)[-1] in _WHETSTONE_TOOL_NAMES


def _elide(reason: str, **extra: object) -> dict:
    """A structured "intentionally omitted" marker — never a bare ``"..."`` string.

    ``reason`` plus whatever non-content metadata (a tool name, an elided length) is safe to keep
    lets a renderer style an elision distinctly and a reader see *why* something is missing without
    reproducing the omitted content itself.
    """
    return {"type": "elided", "reason": reason, **extra}


def _curate_block(block: dict, kept_tool_use_ids: set[str]) -> dict:
    """One curated content block. Mutates ``kept_tool_use_ids`` when a tool_use is kept, so a
    later ``tool_result`` in the same or a subsequent message can be matched back to it."""
    btype = block.get("type")
    if btype == "thinking":
        text = block.get("thinking", "")
        if len(text) <= _THINKING_ELIDE_THRESHOLD:
            return block
        return _elide("internal reasoning", length=len(text))
    if btype == "text":
        text = block.get("text", "")
        if len(text) <= _TEXT_ELIDE_THRESHOLD:
            return block
        return _elide("long text", length=len(text))
    if btype == "tool_use":
        name = block.get("name", "")
        if _is_whetstone_tool(name) or name in _ARTIFACT_TOOL_NAMES:
            tool_use_id = block.get("id")
            if tool_use_id:
                kept_tool_use_ids.add(tool_use_id)
            return block
        return _elide("tool call", name=name)
    if btype == "tool_result":
        tool_use_id = block.get("tool_use_id", "")
        if tool_use_id in kept_tool_use_ids:
            return block
        return _elide("tool result")
    return block  # anything else (server tool blocks, ...): keep as-is


def curate_transcript(messages: list[dict]) -> list[dict]:
    """Reduce a raw (serialized) transcript to the moments a reader actually needs.

    ``messages`` is the JSON-able list ``generate._message_to_dict`` produces (each entry already
    type-tagged real nested JSON — never a stringified repr). Only ``assistant``/``user`` messages
    carry narrative content; ``system``/``result`` messages (the init banner, any surviving
    progress pings, the final cost/turns summary) are plumbing, not story, and are dropped
    entirely from the curated view — they stay intact in the raw ``transcript.json``.

    Within a kept message, content blocks are curated by :func:`_curate_block`: Whetstone-tool and
    Write/Edit tool_use/tool_result turns are kept in full; short assistant/user text and short
    "thinking" blocks are kept in full; long text/"thinking" and any other tool_use/tool_result
    (Read/Bash/Glob/Grep/Skill — routine plumbing) are replaced with a structured elision marker.

    A ``UserMessage`` also carries a top-level ``tool_use_result`` field — the CLI's own duplicate
    copy of its tool result (observed for Read/Bash: the same CSV/file/stdout payload the
    corresponding ``ToolResultBlock.content`` already holds). Whenever a message's
    ``tool_use_result`` duplicates a ``tool_result`` block that got elided, it is elided too —
    otherwise the "omitted" payload would still be sitting right there under a different key.

    Processes ``messages`` in order (a tool_result normally arrives in a later message than its
    tool_use), so a kept tool_use's id is known by the time its matching tool_result is reached.
    """
    kept_tool_use_ids: set[str] = set()
    curated: list[dict] = []
    for msg in messages:
        if msg.get("type") not in ("assistant", "user"):
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            curated.append(dict(msg))
            continue
        new_content = []
        any_tool_result_elided = False
        for block in content:
            new_block = _curate_block(block, kept_tool_use_ids)
            if block.get("type") == "tool_result" and new_block.get("type") == "elided":
                any_tool_result_elided = True
            new_content.append(new_block)
        new_msg = {**msg, "content": new_content}
        if any_tool_result_elided and new_msg.get("tool_use_result") is not None:
            new_msg["tool_use_result"] = _elide("tool result")
        curated.append(new_msg)
    return curated
