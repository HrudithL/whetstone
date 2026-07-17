"""Entry dataclasses for the two stores (see LEARNING_SKILLS_DESIGN.md §4.3, §5.1).

Both stores share ``id``, ``title``, ``scope``, ``provenance``, and a prose ``body``. Learnings
additionally carry the scoring inputs ``recurrence``/``first_seen``/``last_seen``. Issues have no
scoring fields — they are all equally mandatory.

``weight`` is a *derived* 0-1 priority (from ``recurrence`` and recency) and is deliberately NOT a
field here: it is never stored on disk. It is computed on read in a later milestone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class LearningEntry:
    """A soft, weighted, decaying preference. Ids look like ``L12``."""

    id: str
    title: str
    body: str
    scope: str
    provenance: str
    recurrence: int
    first_seen: date
    last_seen: date


@dataclass
class IssueEntry:
    """An objective, mandatory, permanent rule. Ids look like ``I3``."""

    id: str
    title: str
    body: str
    scope: str
    provenance: str
