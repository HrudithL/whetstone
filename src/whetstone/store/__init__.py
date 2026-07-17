"""On-disk store: entry schema, scope slugging, and the markdown block contract."""

from .entries import IssueEntry, LearningEntry
from .markdown import (
    MarkdownParseError,
    parse_issues,
    parse_learnings,
    serialize_issues,
    serialize_learnings,
    write_issues,
    write_learnings,
)
from .slug import base_slug, scope_filename

__all__ = [
    "IssueEntry",
    "LearningEntry",
    "MarkdownParseError",
    "base_slug",
    "scope_filename",
    "parse_issues",
    "parse_learnings",
    "serialize_issues",
    "serialize_learnings",
    "write_issues",
    "write_learnings",
]
