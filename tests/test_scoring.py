"""Tests for the §4.4 scoring model: recurrence term, recency decay, and the combined weight."""

from __future__ import annotations

from datetime import date

from whetstone.scoring import recency, recurrence_term, weight, weight_for


def test_recurrence_term_saturates():
    assert recurrence_term(0) == 0.0
    assert recurrence_term(1) == 0.5
    assert recurrence_term(3) == 0.75
    # Negative recurrence is clamped to 0.
    assert recurrence_term(-5) == 0.0
    # weight_for is the recurrence-only term.
    assert weight_for(3) == 0.75


def test_recency_is_half_at_one_half_life():
    today = date(2026, 7, 1)
    last_seen = date(2026, 7, 1)
    assert recency(last_seen, today, 180) == 1.0  # Δ == 0 -> fresh
    half_life_ago = date(2026, 1, 2)  # exactly 180 days before 2026-07-01
    assert (today - half_life_ago).days == 180
    assert recency(half_life_ago, today, 180) == 0.5  # Δ == H -> exactly 0.5


def test_recency_clamps_future_last_seen_to_zero_delta():
    today = date(2026, 7, 1)
    future = date(2026, 8, 1)  # last_seen after today (clock skew / manual edit)
    assert recency(future, today, 180) == 1.0  # Δ clamped to 0, never > 1


def test_recency_non_positive_half_life_is_no_decay():
    today = date(2026, 7, 1)
    old = date(2020, 1, 1)
    assert recency(old, today, 0) == 1.0
    assert recency(old, today, -30) == 1.0


def test_weight_decay_off_is_recurrence_only():
    today = date(2026, 7, 1)
    stale = date(2020, 1, 1)
    # Decay off -> weight == r regardless of how old last_seen is.
    assert weight(3, stale, today, decay=False, half_life_days=180) == 0.75


def test_weight_decay_on_is_r_times_recency():
    today = date(2026, 7, 1)
    half_life_ago = date(2026, 1, 2)  # Δ == 180 == H -> recency 0.5
    r = recurrence_term(3)
    expected = r * 0.5
    got = weight(3, half_life_ago, today, decay=True, half_life_days=180)
    assert got == expected
    assert got == 0.375


def test_weight_fresh_learning_out_weighs_stale_at_same_recurrence():
    today = date(2026, 7, 1)
    fresh = weight(5, date(2026, 7, 1), today, decay=True, half_life_days=180)
    stale = weight(5, date(2025, 7, 1), today, decay=True, half_life_days=180)
    assert fresh > stale
