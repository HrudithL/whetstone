"""The store layer owns the scope-normalization invariant (§5.1).

`capture`/`revise` normalize scope at the tool boundary, but `access.py` normalizes again at every
write so the filename hash and the stored `scope:` field can never diverge even if a raw scope
reaches a store helper directly (a future caller forgetting the boundary call).
"""

from __future__ import annotations

from conftest import make_issue, make_learning
from whetstone.store.access import (
    load_issues,
    load_learnings,
    save_issue,
    save_learning,
    update_learning_prose,
)
from whetstone.store.slug import normalize_scope, scope_filename

_RAW = "  currency   columns\n"  # stray whitespace/newline; normalizes to "currency columns"
_CANON = "currency columns"


def test_save_learning_normalizes_scope_for_file_and_field(store):
    save_learning(store, make_learning("L1", "Right-align currency columns.", _RAW))

    # Filed under the canonical filename, not one derived from the raw scope.
    assert (store.learnings_dir / scope_filename(_CANON)).exists()
    assert not (store.learnings_dir / scope_filename(_RAW)).exists()

    # The stored scope field is canonical, so re-deriving the filename from it lands on the same
    # file (hash and stored scope never diverge) — unlike hashing the raw, un-normalized scope.
    (loaded,) = load_learnings(store)
    assert loaded.scope == _CANON
    assert scope_filename(loaded.scope) == scope_filename(_CANON)
    assert scope_filename(_RAW) != scope_filename(_CANON)  # raw would have hashed differently


def test_save_issue_normalizes_scope_for_file_and_field(store):
    save_issue(store, make_issue("I1", "Never right-align currency columns.", _RAW))

    assert (store.issues_dir / scope_filename(_CANON)).exists()
    (loaded,) = load_issues(store)
    assert loaded.scope == _CANON == normalize_scope(_RAW)


def test_update_learning_prose_normalizes_scope_on_move(store):
    save_learning(store, make_learning("L1", "Right-align currency columns.", _CANON))
    # Move to a raw form of the SAME canonical scope: must not create a second file / stale copy.
    update_learning_prose(store, "L1", title="t", body="Right-align currency columns.", scope=_RAW)

    entries = load_learnings(store)
    assert [e.scope for e in entries] == [_CANON]
    assert len(list(store.learnings_dir.glob("*.md"))) == 1
