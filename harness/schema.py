"""Scenario schema for the showcase harness (M3).

A *scenario* pairs one great-tables task (borrowed from the sibling ``gtskill`` corpus) with one or
more **subjective preferences** we want the learned layer to pick up and keep honoring. The
preferences are deliberately arbitrary and need no justification (e.g. "negatives in parentheses,
not a minus"); the showcase's whole job is to prove that such a preference, once corrected, is
*tracked* and *re-applied on later runs* — not to argue it is the right choice.

This module is the contract between the scenario files (``harness/scenarios/*.yaml``), the runner
(slice 3), and the site (which only reads ``harness/out/``). It defines the dataclasses and a loader
that fails loudly on a malformed or incomplete scenario. It contains **no run logic** — no tool
driving, no generation, no scoring.

Scenario YAML shape
-------------------
.. code-block:: yaml

    name: sp500_monthly_performance   # unique slug; also the out/ subdir and the store skill id
    difficulty: hard                  # easy | medium | hard  (mirrors the gtskill corpus)
    prompt: >                         # the natural-language task, verbatim from gtskill
      Make a table of the S&P 500 data showing monthly performance ...
    data: data/sp500.csv              # CSV path, relative to the harness root
    preferences:                      # one or more; each a taste we expect to be learned
      - id: negatives-parens          # unique within the scenario; used in out/ + metric rows
        polarity: learning            # learning (soft/decaying taste) | issue (hard rule)
        scope: number formatting      # the Whetstone scope the entry is filed under
        body: >                       # the distilled rule, in the skill's own words
          Show negative values in parentheses, e.g. (1,234), not with a minus sign.
        feedback: >                   # scripted user correction, replayed via capture/revise
          Don't use minus signs for negatives - wrap them in parentheses instead.
        check:                        # deterministic test for "did the output honor this?"
          kind: code_contains         # code_contains | code_absent | regex
          pattern: accounting         # substring or regex; interpretation is the runner's (slice 3)

``metrics.json`` shape (produced by slice 4, read by the dashboard)
------------------------------------------------------------------
.. code-block:: json

    {
      "backend": "sentence-transformers",
      "generated_at": "2026-07-20T00:00:00Z",
      "scenarios": {
        "sp500_monthly_performance": {
          "preferences": {
            "negatives-parens": {
              "runs_to_stick": 2,
              "value_over_time": [
                {"run": 1, "weight": null, "recurrence": 0},
                {"run": 2, "weight": 0.50, "recurrence": 1},
                {"run": 3, "weight": 0.71, "recurrence": 2}
              ]
            }
          }
        }
      },
      "usage_kpis": { "...": "the ordinary-usage KPIs from whetstone metrics, verbatim or null" }
    }

Any metric a scenario cannot support honestly stays ``null`` with a sibling ``note`` field, exactly
as ``whetstone.metrics`` does today. Nothing here is ever hand-set.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import yaml

DIFFICULTIES = ("easy", "medium", "hard")
POLARITIES = ("learning", "issue")
CHECK_KINDS = ("code_contains", "code_absent", "regex")

# ``name`` and preference ``id`` become a filesystem path component (``out/<name>/``) and the store
# skill id, so they must be plain slugs — no separators, no ``.``/``..``, no embedded whitespace or
# newlines that would let one scenario write outside its directory or collide with another. Matched
# with ``fullmatch`` (below), so a trailing newline like ``"foo\n"`` is rejected, not accepted.
_SLUG_RE = re.compile(r"[a-z0-9]+(?:[_-][a-z0-9]+)*")


class ScenarioError(ValueError):
    """Raised when a scenario file is missing required fields or has an invalid value."""


@dataclass(frozen=True)
class Check:
    """A deterministic test for whether a generated table honored a preference.

    ``kind`` selects how ``pattern`` is applied to the generated ``table.py`` source; the actual
    matching is the runner's job (slice 3). The schema only guarantees the fields are present/valid.
    """

    kind: str
    pattern: str


@dataclass(frozen=True)
class Preference:
    """One subjective taste (or hard rule) the learned layer is expected to capture and re-apply."""

    id: str
    polarity: str  # "learning" | "issue"
    scope: str
    body: str
    feedback: str
    check: Check


@dataclass(frozen=True)
class Scenario:
    """A great-tables task plus the preferences the showcase drives through the learned layer."""

    name: str
    difficulty: str
    prompt: str
    data: str
    preferences: tuple[Preference, ...]


def _require(mapping: object, key: str, where: str, typ: type) -> object:
    """Return ``mapping[key]`` after checking it exists, has type ``typ`` (str: non-empty)."""
    if not isinstance(mapping, dict):
        raise ScenarioError(f"{where}: expected a mapping, got {type(mapping).__name__}")
    if key not in mapping:
        raise ScenarioError(f"{where}: missing required field {key!r}")
    value = mapping[key]
    if not isinstance(value, typ):
        raise ScenarioError(
            f"{where}: field {key!r} must be {typ.__name__}, got {type(value).__name__}"
        )
    if typ is str and not value.strip():
        raise ScenarioError(f"{where}: field {key!r} must not be empty")
    return value


def _require_slug(mapping: object, key: str, where: str) -> str:
    """Like :func:`_require` for a str, but also enforce the ``_SLUG_RE`` path-safe slug shape."""
    value = _require(mapping, key, where, str)
    assert isinstance(value, str)
    if not _SLUG_RE.fullmatch(value):
        raise ScenarioError(
            f"{where}: field {key!r} must be a slug (lowercase letters/digits, '-'/'_' "
            f"separators), got {value!r}"
        )
    return value


def _require_relpath(mapping: object, key: str, where: str) -> str:
    """Like :func:`_require` for a str, but reject absolute paths and ``..`` traversal.

    ``data`` is documented as a CSV path *relative to the harness root*; an absolute path or a
    ``../..`` escape would let a scenario read uncommitted local files, so reject those at load
    time rather than letting the runner discover it after a paid model run.
    """
    value = _require(mapping, key, where, str)
    assert isinstance(value, str)
    parts = PurePosixPath(value).parts
    if value.startswith(("/", "~", "\\")) or PurePosixPath(value).is_absolute() or ".." in parts:
        raise ScenarioError(
            f"{where}: field {key!r} must be a relative path under the harness root "
            f"(no leading '/'/'~', no '..'), got {value!r}"
        )
    return value


def _parse_check(raw: object, where: str) -> Check:
    kind = _require(raw, "kind", where, str)
    if kind not in CHECK_KINDS:
        raise ScenarioError(f"{where}: check.kind must be one of {CHECK_KINDS}, got {kind!r}")
    pattern = _require(raw, "pattern", where, str)
    if kind == "regex":
        # Compile now so a broken pattern fails at load time, not after the runner has spent API
        # calls generating artifacts.
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ScenarioError(f"{where}: check.pattern is not a valid regex: {exc}") from exc
    return Check(kind=kind, pattern=pattern)


def _parse_preference(raw: object, where: str) -> Preference:
    pref_id = _require_slug(raw, "id", where)
    where = f"{where} (preference {pref_id!r})"
    polarity = _require(raw, "polarity", where, str)
    if polarity not in POLARITIES:
        raise ScenarioError(f"{where}: polarity must be one of {POLARITIES}, got {polarity!r}")
    return Preference(
        id=pref_id,
        polarity=polarity,
        scope=_require(raw, "scope", where, str),
        body=_require(raw, "body", where, str),
        feedback=_require(raw, "feedback", where, str),
        check=_parse_check(_require(raw, "check", where, dict), f"{where} check"),
    )


def parse_scenario(raw: object, source: str) -> Scenario:
    """Validate a parsed mapping into a :class:`Scenario`. Raises :class:`ScenarioError`."""
    name = _require_slug(raw, "name", source)
    where = f"{source} (scenario {name!r})"
    difficulty = _require(raw, "difficulty", where, str)
    if difficulty not in DIFFICULTIES:
        raise ScenarioError(
            f"{where}: difficulty must be one of {DIFFICULTIES}, got {difficulty!r}"
        )

    prefs_raw = _require(raw, "preferences", where, list)
    if not prefs_raw:
        raise ScenarioError(f"{where}: 'preferences' must list at least one preference")

    preferences = tuple(
        _parse_preference(p, f"{where} preferences[{i}]") for i, p in enumerate(prefs_raw)
    )
    seen: set[str] = set()
    for pref in preferences:
        if pref.id in seen:
            raise ScenarioError(f"{where}: duplicate preference id {pref.id!r}")
        seen.add(pref.id)

    return Scenario(
        name=name,
        difficulty=difficulty,
        prompt=_require(raw, "prompt", where, str),
        data=_require_relpath(raw, "data", where),
        preferences=preferences,
    )


def load_scenario(path: Path) -> Scenario:
    """Load and validate one scenario YAML file. Raises :class:`ScenarioError` on any problem."""
    text = path.read_text(encoding="utf-8")
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ScenarioError(f"{path}: not valid YAML: {exc}") from exc
    if raw is None:
        raise ScenarioError(f"{path}: file is empty")
    return parse_scenario(raw, str(path))


def load_scenarios(directory: Path) -> list[Scenario]:
    """Load every ``*.yaml`` scenario in ``directory``, sorted by name. Empty dir returns ``[]``.

    Scenario ``name`` is the ``out/`` subdirectory and store skill id, so it must be unique across
    files — two scenarios sharing a name would overwrite each other's artifacts. Raises
    :class:`ScenarioError` on a collision.
    """
    scenarios: list[Scenario] = []
    by_name: dict[str, Path] = {}
    for path in sorted(directory.glob("*.yaml")):
        scenario = load_scenario(path)
        if scenario.name in by_name:
            raise ScenarioError(
                f"{path}: scenario name {scenario.name!r} already used by {by_name[scenario.name]}"
            )
        by_name[scenario.name] = path
        scenarios.append(scenario)
    # Order by declared scenario name (not filesystem path), so renaming/prefixing a file does not
    # reshuffle artifact/metric ordering downstream.
    scenarios.sort(key=lambda s: s.name)
    return scenarios
