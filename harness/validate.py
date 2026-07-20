"""Validate the authored scenarios: ``python -m harness.validate``.

Loads every ``harness/scenarios/*.yaml`` through the schema (so missing/invalid fields fail loudly)
and checks each scenario's ``data`` file actually exists under the harness root. Prints a one-line
summary per scenario and exits non-zero on any problem. This is a convenience/CI-free check — it is
not wired into the engine's pytest suite (the harness stays separate from CI).
"""

from __future__ import annotations

import sys

from .config import HARNESS_ROOT
from .schema import ScenarioError, load_scenarios

SCENARIOS_DIR = HARNESS_ROOT / "scenarios"


def main() -> int:
    try:
        scenarios = load_scenarios(SCENARIOS_DIR)
    except ScenarioError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1

    if not scenarios:
        print(f"no scenarios found in {SCENARIOS_DIR}", file=sys.stderr)
        return 1

    ok = True
    for s in scenarios:
        data_path = (HARNESS_ROOT / s.data).resolve()
        missing = not data_path.is_file()
        # Defense in depth: the schema already forbids traversal, but confirm the resolved path
        # stayed under the harness root before reporting it as present.
        escaped = HARNESS_ROOT.resolve() not in data_path.parents
        prefs = ", ".join(f"{p.id}({p.polarity})" for p in s.preferences)
        if missing or escaped:
            ok = False
            reason = "data file missing" if missing else "data path escapes harness root"
            print(f"FAIL  {s.name:32} [{s.difficulty:6}] {reason}: {s.data}")
        else:
            print(f"ok    {s.name:32} [{s.difficulty:6}] {len(s.preferences)} pref(s): {prefs}")

    print(f"\n{len(scenarios)} scenario(s) checked.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
