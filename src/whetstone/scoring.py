"""Derived learning weight (§4.4). Issues are unranked and never scored.

M1 ships only the recurrence-saturating term::

    r = 1 - 1 / (1 + max(recurrence, 0))
    weight = r

TODO(M2): add the recency/decay model (§4.4) — ``recency = exp(-ln2 * Δdays / H)`` and
``weight = r * recency`` when decay is on, with the half-life/decay toggles from config. This module
is the seam: ``weight_for`` gains ``last_seen``/config args then, and callers keep using it.
"""

from __future__ import annotations


def recurrence_term(recurrence: int) -> float:
    """The saturating map of a learning's recurrence count to ``[0, 1)`` — ``r`` in §4.4."""
    return 1.0 - 1.0 / (1.0 + max(recurrence, 0))


def weight_for(recurrence: int) -> float:
    """A learning's 0-1 ``weight``. M1: recurrence-only (no recency/decay yet — see module TODO)."""
    return recurrence_term(recurrence)
