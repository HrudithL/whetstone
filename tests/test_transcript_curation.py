"""M6c — the showcase harness's transcript serialization + curation (pure data transformation).

`harness/generate.py`'s `_message_to_dict` used to fall back to stringified Python reprs
(`{k: str(v) for k, v in val.items()}` / `repr(msg)`) for Agent-SDK message/content-block
dataclasses it didn't natively serialize. These tests build tiny, real `claude_agent_sdk`
dataclass instances (not mocks) and assert the fixed serializer produces real nested JSON, that
the noisy `thinking_tokens` progress pings are recognized for dropping, and that
`harness.curate.curate_transcript` reduces a raw transcript to the load-bearing turns.

The showcase harness is internal/command-only and lives under `harness/` (not the installed
package); its deps (`pyyaml`, `claude-agent-sdk`) are the `[showcase]` extra, absent from both CI
jobs (`test` / `test-embeddings`, see `.github/workflows/ci.yml`). `importorskip` keeps this module
collectable everywhere, same pattern as `tests/test_calibration.py`.
"""

from __future__ import annotations

import pytest

pytest.importorskip("yaml")
sdk = pytest.importorskip("claude_agent_sdk")
generate = pytest.importorskip("harness.generate")
curate = pytest.importorskip("harness.curate")


# --------------------------------------------------------------------------- _message_to_dict


def test_text_block_serializes_to_real_dict():
    block = sdk.TextBlock(text="applying the burnt-orange accent")
    assert generate._to_jsonable(block) == {
        "type": "text",
        "text": "applying the burnt-orange accent",
    }


def test_tool_use_block_input_is_a_real_dict_not_a_string():
    block = sdk.ToolUseBlock(id="tu_1", name="Write", input={"file_path": "table.py", "n": 3})
    out = generate._to_jsonable(block)
    assert out["type"] == "tool_use"
    assert out["input"] == {"file_path": "table.py", "n": 3}
    assert isinstance(out["input"], dict)  # NOT a stringified repr


def test_thinking_block_serializes_with_both_fields():
    block = sdk.ThinkingBlock(thinking="considering column order", signature="sig-abc")
    assert generate._to_jsonable(block) == {
        "type": "thinking",
        "thinking": "considering column order",
        "signature": "sig-abc",
    }


def test_assistant_message_nests_real_content_blocks():
    msg = sdk.AssistantMessage(
        content=[
            sdk.TextBlock(text="using fmt_currency for price"),
            sdk.ToolUseBlock(id="tu_2", name="Read", input={"file_path": "gtcars.csv"}),
        ],
        model="claude-x",
    )
    out = generate._message_to_dict(msg)
    assert out["type"] == "assistant"
    assert out["model"] == "claude-x"
    assert out["content"] == [
        {"type": "text", "text": "using fmt_currency for price"},
        {"type": "tool_use", "id": "tu_2", "name": "Read", "input": {"file_path": "gtcars.csv"}},
    ]
    # the old fallback produced a *string* like "[TextBlock(text=...), ToolUseBlock(...)]"
    assert isinstance(out["content"], list)
    assert all(isinstance(b, dict) for b in out["content"])


def test_tool_result_block_content_round_trips():
    msg = sdk.UserMessage(
        content=[sdk.ToolResultBlock(tool_use_id="tu_2", content="42,gtcars.csv", is_error=False)]
    )
    out = generate._message_to_dict(msg)
    assert out["type"] == "user"
    assert out["content"] == [
        {
            "type": "tool_result",
            "tool_use_id": "tu_2",
            "content": "42,gtcars.csv",
            "is_error": False,
        }
    ]


def test_system_message_thinking_tokens_ping_serializes_and_is_flagged():
    msg = sdk.SystemMessage(subtype="thinking_tokens", data={"token_count": 100})
    out = generate._message_to_dict(msg)
    assert out == {"type": "system", "subtype": "thinking_tokens", "data": {"token_count": 100}}
    assert generate._is_progress_ping(out) is True


def test_non_ping_system_message_is_not_flagged():
    msg = sdk.SystemMessage(subtype="init", data={"cwd": "/tmp"})
    out = generate._message_to_dict(msg)
    assert generate._is_progress_ping(out) is False


# --------------------------------------------------------------------------- curate_transcript


def _assistant(*blocks):
    return generate._message_to_dict(sdk.AssistantMessage(content=list(blocks), model="claude-x"))


def _user(*blocks):
    return generate._message_to_dict(sdk.UserMessage(content=list(blocks)))


def test_curate_keeps_whetstone_tool_turns_in_full():
    long_thinking = "x" * 500
    raw = [
        _assistant(
            sdk.ThinkingBlock(thinking=long_thinking, signature="s1"),
            sdk.ToolUseBlock(
                id="tu_recall", name="mcp__whetstone__recall", input={"skill": "great-tables"}
            ),
        ),
        _user(sdk.ToolResultBlock(tool_use_id="tu_recall", content="ok")),
    ]
    curated = curate.curate_transcript(raw)
    assistant_content = curated[0]["content"]
    assert assistant_content[0]["type"] == "elided"
    assert assistant_content[0]["reason"] == "internal reasoning"
    assert assistant_content[0]["length"] == 500
    assert assistant_content[1] == {
        "type": "tool_use",
        "id": "tu_recall",
        "name": "mcp__whetstone__recall",
        "input": {"skill": "great-tables"},
    }
    assert curated[1]["content"] == [
        {"type": "tool_result", "tool_use_id": "tu_recall", "content": "ok", "is_error": None}
    ]


def test_curate_elides_routine_tool_calls_and_short_thinking_survives():
    raw = [
        _assistant(
            sdk.TextBlock(text="reading the input data"),
            sdk.ThinkingBlock(thinking="short note", signature="s2"),
            sdk.ToolUseBlock(id="tu_read", name="Read", input={"file_path": "gtcars.csv"}),
        ),
        _user(sdk.ToolResultBlock(tool_use_id="tu_read", content="...csv contents...")),
    ]
    curated = curate.curate_transcript(raw)
    assistant_content = curated[0]["content"]
    assert assistant_content[0] == {"type": "text", "text": "reading the input data"}
    assert assistant_content[1] == {
        "type": "thinking",
        "thinking": "short note",
        "signature": "s2",
    }
    assert assistant_content[2] == {"type": "elided", "reason": "tool call", "name": "Read"}
    assert curated[1]["content"] == [{"type": "elided", "reason": "tool result"}]


def test_curate_keeps_artifact_write_calls():
    raw = [
        _assistant(
            sdk.ToolUseBlock(id="tu_write", name="Write", input={"file_path": "table.py"}),
        ),
        _user(sdk.ToolResultBlock(tool_use_id="tu_write", content="")),
    ]
    curated = curate.curate_transcript(raw)
    assert curated[0]["content"][0]["type"] == "tool_use"
    assert curated[0]["content"][0]["name"] == "Write"
    assert curated[1]["content"][0]["type"] == "tool_result"


def test_curate_drops_system_and_result_messages():
    raw = [
        generate._message_to_dict(sdk.SystemMessage(subtype="init", data={})),
        _assistant(sdk.TextBlock(text="done")),
        generate._message_to_dict(
            sdk.ResultMessage(
                subtype="success",
                duration_ms=1,
                duration_api_ms=1,
                is_error=False,
                num_turns=1,
                session_id="s1",
            )
        ),
    ]
    curated = curate.curate_transcript(raw)
    assert len(curated) == 1
    assert curated[0]["type"] == "assistant"
