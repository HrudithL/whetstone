"""Embedding backends and the factory that selects one from config (§5.4).

Retrieval embeds the model's *elaborated intent* and compares it to per-scope and per-entry vectors.
The concrete embedder is pluggable behind :class:`EmbeddingBackend`:

- :class:`HashingBackend` — a small, deterministic, dependency-free feature-hashing embedder. It is
  the default so the base install stays light (no torch/network) and the whole test suite runs
  offline. Similarity is driven by shared word/char n-grams, which is enough for scope matching.
- :class:`SentenceTransformerBackend` — the design's chosen ``all-MiniLM-L6-v2`` model, imported
  lazily from the optional ``[embeddings]`` extra so importing this module never pulls torch.

All vectors are plain ``list[float]``; cosine similarity is brute-force (§5.4: no ANN library).
"""

from __future__ import annotations

import hashlib
import math
import re
import threading
from typing import Protocol, runtime_checkable

from .config import Config

_TOKEN = re.compile(r"[a-z0-9]+")
_CHAR_NGRAM = 3


@runtime_checkable
class EmbeddingBackend(Protocol):
    """A text -> fixed-width vector embedder."""

    @property
    def dim(self) -> int:
        """The dimensionality of the vectors this backend produces."""
        ...

    @property
    def model_id(self) -> str:
        """A stable identity of this embedder (backend + model). Feeds the index fingerprint so a
        different model of the same dimensionality invalidates a stale index instead of silently
        comparing incompatible vectors."""
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts into ``len(texts)`` vectors of length :attr:`dim`."""
        ...


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two equal-length vectors; ``0.0`` if either is the zero vector."""
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b, strict=False):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / math.sqrt(na * nb)


def _features(text: str) -> list[str]:
    """Word unigrams + word bigrams + character trigrams (with a namespace prefix each).

    Combining word and character n-grams gives useful overlap for both multi-word intents and short
    scope phrases (e.g. "currency" vs "currency columns" share char trigrams and a unigram).
    """
    tokens = _TOKEN.findall(text.lower())
    feats = [f"w:{t}" for t in tokens]
    feats += [f"b:{a}_{c}" for a, c in zip(tokens, tokens[1:], strict=False)]
    joined = " ".join(tokens)
    upper = len(joined) - _CHAR_NGRAM + 1
    feats += [f"c:{joined[i : i + _CHAR_NGRAM]}" for i in range(upper)]
    return feats


class HashingBackend:
    """Deterministic, dependency-free feature-hashing embedder (the default/test backend).

    Each feature is hashed (via ``md5``, so it is stable across processes — unlike the salted
    builtin ``hash``) to a bucket and a sign, accumulated, then L2-normalized. Identical input
    always yields the identical vector.
    """

    def __init__(self, dim: int = 384) -> None:
        if dim <= 0:
            raise ValueError(f"embedding dim must be positive, got {dim}")
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def model_id(self) -> str:
        return f"hashing:{self._dim}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self._dim
        for feat in _features(text):
            digest = hashlib.md5(feat.encode("utf-8")).digest()  # noqa: S324 - non-crypto use
            idx = int.from_bytes(digest[:4], "big") % self._dim
            sign = 1.0 if digest[4] & 1 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0.0:
            vec = [v / norm for v in vec]
        return vec


class SentenceTransformerBackend:
    """The design's ``all-MiniLM-L6-v2`` embedder, loaded lazily from the ``[embeddings]`` extra."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model_name = model_name
        self._model = None
        self._dim: int | None = None
        self._init_lock = threading.Lock()

    @property
    def model_id(self) -> str:
        # Available without loading the model, so the fingerprint reflects a model swap immediately.
        return f"sentence-transformers:{self._model_name}"

    def _ensure_model(self) -> None:
        # Double-checked locking so concurrent cold starts load the model exactly once. The model
        # is published to ``self._model`` only AFTER ``self._dim`` is set, so another thread that
        # sees ``_model is not None`` never observes a half-initialized state where ``dim`` is None.
        if self._model is not None:
            return
        with self._init_lock:
            if self._model is not None:
                return
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover - exercised only without the extra
                raise RuntimeError(
                    "The 'sentence-transformers' embedding backend requires the optional "
                    "dependency. Install it with: pip install 'whetstone-mcp[embeddings]', or set "
                    "WHETSTONE_EMBEDDING_BACKEND=hashing (embedding_backend='hashing' in config)."
                ) from exc
            model = SentenceTransformer(self._model_name)
            self._dim = int(model.get_sentence_embedding_dimension())
            self._model = model  # publish last: dim is guaranteed set before _model is visible

    @property
    def dim(self) -> int:
        self._ensure_model()
        assert self._dim is not None
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        self._ensure_model()
        assert self._model is not None
        vectors = self._model.encode(list(texts), normalize_embeddings=False)
        return [[float(x) for x in row] for row in vectors]


def make_backend(config: Config) -> EmbeddingBackend:
    """Construct the embedding backend selected by ``config`` (§5.4)."""
    if config.embedding_backend == "hashing":
        return HashingBackend(dim=config.embedding_dim)
    if config.embedding_backend == "sentence-transformers":
        return SentenceTransformerBackend(config.embedding_model)
    raise ValueError(f"unknown embedding_backend: {config.embedding_backend!r}")


# Process-lifetime cache keyed by the fields that determine the backend's identity/vectors. Building
# a backend per recall/capture would reload the sentence-transformers model (tens/hundreds of MB)
# every call; caching keeps it resident for the life of the process. Cleared only by process exit.
_BACKEND_CACHE: dict[tuple[str, str, int], EmbeddingBackend] = {}


def get_backend(config: Config) -> EmbeddingBackend:
    """Return a cached embedding backend for ``config`` (process-lifetime cache; see note above)."""
    key = (config.embedding_backend, config.embedding_model, config.embedding_dim)
    backend = _BACKEND_CACHE.get(key)
    if backend is None:
        backend = make_backend(config)
        _BACKEND_CACHE[key] = backend
    return backend
