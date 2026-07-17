"""Tests for the embedding backends and cosine helper (HashingBackend only — no torch/network)."""

from __future__ import annotations

import math

import pytest

from whetstone.config import Config
from whetstone.embeddings import HashingBackend, cosine, make_backend


def test_hashing_backend_is_deterministic():
    a = HashingBackend(dim=64)
    b = HashingBackend(dim=64)
    text = "right-align currency columns and drop gridlines"
    assert a.embed([text]) == b.embed([text])
    # And stable across repeated calls on the same instance.
    assert a.embed([text, text]) == [a.embed([text])[0], a.embed([text])[0]]


def test_hashing_backend_dim_and_normalization():
    backend = HashingBackend(dim=128)
    assert backend.dim == 128
    vec = backend.embed(["some words here"])[0]
    assert len(vec) == 128
    norm = math.sqrt(sum(x * x for x in vec))
    assert norm == pytest.approx(1.0)


def test_hashing_backend_empty_text_is_zero_vector():
    vec = HashingBackend(dim=32).embed([""])[0]
    assert vec == [0.0] * 32


def test_cosine_correctness_on_a_fixture():
    assert cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)
    assert cosine([3.0, 4.0], [3.0, 4.0]) == pytest.approx(1.0)  # not unit-length
    assert cosine([0.0, 0.0], [1.0, 1.0]) == 0.0  # zero vector -> 0, no divide-by-zero


def test_similar_texts_are_closer_than_dissimilar():
    backend = HashingBackend(dim=256)
    q = backend.embed(["currency column number formatting and alignment"])[0]
    near = backend.embed(["align the currency columns and format the numbers"])[0]
    far = backend.embed(["completely unrelated bash scripting for log parsing"])[0]
    assert cosine(q, near) > cosine(q, far)


def test_factory_selects_hashing_by_default():
    backend = make_backend(Config())
    assert isinstance(backend, HashingBackend)
    assert backend.dim == 384


def test_factory_respects_embedding_dim():
    backend = make_backend(Config(embedding_dim=64))
    assert isinstance(backend, HashingBackend)
    assert backend.dim == 64
