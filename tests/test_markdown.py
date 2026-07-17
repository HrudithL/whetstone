"""Round-trip and contract tests for the markdown store format."""

from __future__ import annotations

from datetime import date

import pytest

from whetstone.store import (
    IssueEntry,
    LearningEntry,
    parse_issues,
    parse_learnings,
    serialize_issues,
    serialize_learnings,
    write_issues,
    write_learnings,
)
from whetstone.store.markdown import MarkdownParseError


def _learning(**kw) -> LearningEntry:
    defaults = dict(
        id="L12",
        title="Right-align currency columns",
        body="Right-align currency columns and drop vertical gridlines.",
        scope="currency columns",
        provenance="\"2026-07-10 — 'make the revenue column right-aligned'\"",
        recurrence=4,
        first_seen=date(2026, 5, 1),
        last_seen=date(2026, 7, 10),
    )
    defaults.update(kw)
    return LearningEntry(**defaults)


def _issue(**kw) -> IssueEntry:
    defaults = dict(
        id="I3",
        title="Never band tiny tables",
        body="Never apply heavy row banding to tables under 10 rows.",
        scope="small tables",
        provenance="\"2026-07-01 — 'stop striping that little table'\"",
    )
    defaults.update(kw)
    return IssueEntry(**defaults)


def test_learning_round_trip_stable():
    entries = [_learning(), _learning(id="L13", title="Muted palette", scope="color palette")]
    text = serialize_learnings(entries)
    once = parse_learnings(text)
    twice = parse_learnings(serialize_learnings(once))
    assert once == entries
    assert twice == entries


def test_issue_round_trip_stable():
    entries = [_issue(), _issue(id="I4", title="No emoji", scope="tone")]
    text = serialize_issues(entries)
    once = parse_issues(text)
    twice = parse_issues(serialize_issues(once))
    assert once == entries
    assert twice == entries


def test_multi_paragraph_body_preserved():
    body = "First paragraph explaining the taste.\n\nSecond paragraph with the why.\n\nThird."
    entry = _learning(body=body)
    parsed = parse_learnings(serialize_learnings([entry]))
    assert parsed[0].body == body


def test_unicode_body_and_scope():
    entry = _learning(
        title="Café tables — flair",
        body="Prefer typographic dashes — en/em — and curly quotes “like this”. 数字も。",
        scope="café · naïve façade",
    )
    parsed = parse_learnings(serialize_learnings([entry]))
    assert parsed[0] == entry


def test_issues_have_no_scoring_fields():
    text = serialize_issues([_issue()])
    assert "recurrence" not in text
    assert "first_seen" not in text
    assert "last_seen" not in text
    # Missing (optional-for-issues) scoring fields still round-trip.
    assert parse_issues(text)[0] == _issue()


def test_weight_is_never_serialized():
    assert "weight" not in serialize_learnings([_learning()])
    assert "weight" not in serialize_issues([_issue()])


def test_empty_store_serializes_empty():
    assert serialize_learnings([]) == ""
    assert serialize_issues([]) == ""
    assert parse_learnings("") == []
    assert parse_issues("") == []


def test_atomic_write_round_trip(tmp_path):
    path = tmp_path / "learnings" / "currency-columns.md"
    write_learnings(path, [_learning()])
    assert path.exists()
    assert parse_learnings(path.read_text(encoding="utf-8")) == [_learning()]

    ipath = tmp_path / "issues" / "small-tables.md"
    write_issues(ipath, [_issue()])
    assert parse_issues(ipath.read_text(encoding="utf-8")) == [_issue()]


def test_malformed_no_heading_separator_raises():
    with pytest.raises(MarkdownParseError, match="heading must be"):
        parse_learnings("## L1 just a title without separator\n- scope: x\n")


def test_malformed_missing_metadata_raises():
    text = "## L1 · Title\n- scope: currency\n\nbody\n"
    with pytest.raises(MarkdownParseError, match="missing metadata"):
        parse_learnings(text)


def test_malformed_bad_bullet_raises():
    text = "## L1 · Title\n- this bullet has no colon\n\nbody\n"
    with pytest.raises(MarkdownParseError, match="key: value"):
        parse_learnings(text)


def test_malformed_content_before_heading_raises():
    with pytest.raises(MarkdownParseError, match="before first"):
        parse_learnings("stray text\n## L1 · Title\n- scope: x\n")


def test_malformed_bad_date_raises():
    text = (
        "## L1 · Title\n- recurrence: 1\n- first_seen: not-a-date\n"
        "- last_seen: 2026-01-01\n- scope: x\n- provenance: y\n\nbody\n"
    )
    with pytest.raises(MarkdownParseError, match="first_seen"):
        parse_learnings(text)


def test_metadata_newline_injection_is_neutralized():
    # A scope/provenance carrying a newline (or a forged bullet / heading) must not create extra
    # metadata or a bogus block when read back — it is collapsed to a single line on write.
    evil = _learning(scope="currency\n- provenance: spoofed\n## L99 · injected")
    text = serialize_learnings([evil])
    back = parse_learnings(text)
    assert len(back) == 1
    assert "\n" not in back[0].scope
    assert back[0].scope == "currency - provenance: spoofed ## L99 · injected"
    assert back[0].provenance == evil.provenance  # the real provenance is untouched


def test_title_newline_is_neutralized():
    evil = _learning(title="Title\n## L99 · forged")
    back = parse_learnings(serialize_learnings([evil]))
    assert len(back) == 1
    assert back[0].title == "Title ## L99 · forged"
