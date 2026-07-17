"""Derived learning weight (§4.4). Issues are unranked and never scored.

Two base signals; everything else is derived (§4.4). With ``Δ`` = days since ``last_seen`` and ``H``
= the configured half-life in days::

    r        = 1 - 1 / (1 + max(recurrence, 0))   # saturating map of the count (trust/stability)
    recency  = exp(-ln2 * Δ / H)                  # freshness in (0, 1]
    weight   = r * recency   (decay ON, default)  |  r   (decay OFF)

``recency == 0.5`` exactly when ``Δ == H``. Decay is configurable for learnings (ON but slow by
default, ``H`` = 180-day half-life); issues never decay (they have no ``last_seen``/``weight``).
"""

from __future__ import annotations

from datetime import date
from math import exp, log

_LN2 = log(2.0)


def recurrence_term(recurrence: int) -> float:
    """The saturating map of a learning's recurrence count to ``[0, 1)`` — ``r`` in §4.4."""
    return 1.0 - 1.0 / (1.0 + max(recurrence, 0))


def recency(last_seen: date, today: date, half_life_days: int) -> float:
    """Freshness in ``(0, 1]`` — ``exp(-ln2 · Δ / H)``; exactly ``0.5`` when ``Δ == H``.

    ``Δ`` is days since ``last_seen``, clamped to ``≥ 0`` so a future ``last_seen`` (clock skew /
    manual edit) cannot push freshness above 1. A non-positive ``half_life_days`` is treated as
    no-decay (returns ``1.0``) rather than dividing by zero.
    """
    if half_life_days <= 0:
        return 1.0
    delta = max(0, (today - last_seen).days)
    return exp(-_LN2 * delta / half_life_days)


def weight_for(recurrence: int) -> float:
    """A learning's recurrence-only term ``r`` (no recency). The recency-aware model is
    :func:`weight`; this remains for callers that only need the saturating count map."""
    return recurrence_term(recurrence)


def weight(
    recurrence: int,
    last_seen: date,
    today: date,
    *,
    decay: bool,
    half_life_days: int,
) -> float:
    """A learning's 0-1 ``weight`` (§4.4): ``r × recency`` when ``decay`` else ``r``."""
    r = recurrence_term(recurrence)
    if not decay:
        return r
    return r * recency(last_seen, today, half_life_days)
