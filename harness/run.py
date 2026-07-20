"""Showcase runner (M3): ``python -m harness.run``.

For each scenario, drive the learned-layer loop against **real Whetstone** and write the committed
artifacts the site reads:

1. **COLD** (run 1): recall an empty store, generate a table, check which preferences it honored
   (usually none — that is the "before").
2. **SEED**: replay the scenario's scripted feedback through ``capture`` — the user correcting the
   skill after seeing the cold output. Each preference becomes a tracked learning/issue.
3. **WARM** (runs 2..N): recall the now-seeded store, inject the learned layer, regenerate, and
   re-check. After each warm run, reinforce the learnings (a repeat correction) so their
   weight/recurrence grows — the value-over-time signal. Stop once every preference has been honored
   for ``--stick-streak`` consecutive runs (or ``--max-runs`` is hit).

Generation is pluggable (see ``generate.py``): ``--stub`` (default, deterministic, no API spend,
verifies the whole pipeline) or ``--agent`` (the live Claude Agent SDK, for the real artifact run).
The runner itself always exercises real Whetstone, so the recall payloads, weights, and events are
genuine either way.

Outputs per scenario under ``out/<name>/``: ``cold/table.py`` (+ png/transcript for the agent),
``warm/table.py``, ``recall.json`` (verbatim final learned layer), ``diff.txt``, and ``runs.jsonl``
(per-run honored map + weight/recurrence snapshots — the input to the metrics slice).
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import config
from .generate import (
    AgentGenerator,
    GenerationResult,
    Generator,
    StubGenerator,
    format_learned_layer,
    honors,
)
from .schema import Scenario, load_scenarios

SCENARIOS_DIR = config.HARNESS_ROOT / "scenarios"
OUT_ROOT = config.HARNESS_ROOT / "out"
SKILL_DIR = config.HARNESS_ROOT / "skill" / "great-tables"

DEFAULT_MAX_RUNS = 5
DEFAULT_STICK_STREAK = 2


def elaborated_intent(scenario: Scenario) -> str:
    """A recall ``intent`` that elaborates the task's styling dimensions (per recall's contract).

    Deliberately generic — it names the *dimensions* a table decision spans, not the answers — so
    retrieval must match the seeded scopes rather than being handed them.
    """
    return (
        f"Styling a great-tables display table for this task: {scenario.prompt.strip()} "
        "Consider column alignment, number formatting, currency formatting, percentage formatting, "
        "color palette and encoding, column grouping and spanners, row ordering, and table density."
    )


def _recall(skill: str, intent: str) -> dict:
    from whetstone.server import recall

    return recall(skill=skill, intent=intent)


def _capture(
    skill: str, polarity: str, body: str, scope: str, provenance: str, run_id: str | None
) -> dict:
    from whetstone.server import capture

    # Forward the recall run_id so the capture event is associated with the run that recalled — the
    # telemetry the metrics slice reads to tie corrections/reinforcements to runs.
    return capture(
        skill=skill, polarity=polarity, body=body, scope=scope, provenance=provenance,
        run_id=run_id,
    )


def _store_dir(skill: str) -> Path:
    """The real on-disk store directory for ``skill`` (Whetstone slugs it as ``<name>-<hash>``)."""
    from whetstone.config import load_config
    from whetstone.store.layout import store_location

    return store_location(skill, load_config()).path


def _reset_store(skill: str) -> None:
    """Delete a scenario's per-skill store so its COLD run sees a genuinely empty store.

    Whetstone resolves the store through ``skill_slug`` (``<name>-<hash>``), so deleting
    ``.store/<name>`` would miss it and leave stale entries that corrupt the cold baseline.
    """
    shutil.rmtree(_store_dir(skill), ignore_errors=True)


def _weight_recurrence(payload: dict, entry_id: str) -> tuple[float | None, int | None]:
    """The (weight, recurrence) of ``entry_id`` in a recall ``payload``, or (None, None) if absent.

    Absent means retrieval did not surface the entry this run — recorded honestly as null, never
    back-filled.
    """
    for x in payload.get("learnings", []):
        if x.get("id") == entry_id:
            return x.get("weight"), x.get("recurrence")
    for x in payload.get("issues", []):
        if x.get("id") == entry_id:
            return None, x.get("recurrence")  # issues are unweighted
    return None, None


@dataclass
class _Work:
    """A disposable generation workdir seeded with the scenario's data file under its basename."""

    dir: Path

    def __enter__(self) -> Path:
        return self.dir

    def __exit__(self, *exc: object) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)


def _make_workdir(scenario: Scenario) -> _Work:
    d = Path(tempfile.mkdtemp(prefix=f"whetstone-showcase-{scenario.name}-"))
    src = (config.HARNESS_ROOT / scenario.data).resolve()
    if src.is_file():
        shutil.copy2(src, d / src.name)
    return _Work(d)


def _persist(result: GenerationResult, workdir: Path, phase_dir: Path) -> None:
    """Copy the generated artifacts out of the (soon-deleted) workdir into ``phase_dir``."""
    phase_dir.mkdir(parents=True, exist_ok=True)
    (phase_dir / "table.py").write_text(result.code, encoding="utf-8")
    # The live agent renders table.png in the workdir; capture it before the workdir is torn down.
    png = workdir / "table.png"
    if png.is_file():
        shutil.copy2(png, phase_dir / "table.png")
    if result.transcript:
        (phase_dir / "transcript.json").write_text(
            json.dumps(result.transcript, indent=2), encoding="utf-8"
        )


def run_scenario(
    scenario: Scenario,
    generator: Generator,
    *,
    max_runs: int = DEFAULT_MAX_RUNS,
    stick_streak: int = DEFAULT_STICK_STREAK,
    out_root: Path = OUT_ROOT,
) -> dict:
    """Run the cold→seed→warm loop for one scenario; write ``out/<name>/`` and return a summary."""
    _reset_store(scenario.name)
    out_dir = out_root / scenario.name
    # Clear any prior generation so committed artifacts never mix two runs (stale png/transcript).
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    intent = elaborated_intent(scenario)
    prefs = scenario.preferences
    runs: list[dict] = []
    cold_code = warm_code = ""
    final_recall: dict = {"learnings": [], "issues": []}

    # ---- COLD (run 1): empty store, nothing injected -------------------------------------------
    # Recall anyway (the model consults the skill and finds nothing) so the cold run is a real,
    # empty-payload recall event; its run_id ties the seeding corrections to this run.
    cold_recall = _recall(scenario.name, intent)
    cold_run_id = cold_recall.get("run_id")
    with _make_workdir(scenario) as wd:
        cold = generator.generate(scenario, "", wd)
        _persist(cold, wd, out_dir / "cold")
    cold_code = cold.code
    runs.append(
        {
            "run": 1,
            "phase": "cold",
            "honored": {p.id: honors(cold.code, p.check) for p in prefs},
            "weights": {p.id: None for p in prefs},
            "recurrence": {p.id: None for p in prefs},
        }
    )

    # ---- SEED: the user corrects the skill after the cold output --------------------------------
    entry_ids: dict[str, str | None] = {}
    for p in prefs:
        res = _capture(
            scenario.name, p.polarity, p.body, p.scope, f"showcase:{scenario.name}", cold_run_id
        )
        entry_ids[p.id] = res.get("entry_id")

    # ---- WARM (runs 2..N): recall + inject + regenerate + reinforce -----------------------------
    run_no = 1
    while run_no < max_runs:
        run_no += 1
        payload = _recall(scenario.name, intent)
        final_recall = payload
        warm_run_id = payload.get("run_id")
        learned = format_learned_layer(payload)
        with _make_workdir(scenario) as wd:
            warm = generator.generate(scenario, learned, wd)
            _persist(warm, wd, out_dir / "warm")
        warm_code = warm.code
        weights, recurrence, honored = {}, {}, {}
        for p in prefs:
            w, r = _weight_recurrence(payload, entry_ids.get(p.id) or "")
            weights[p.id], recurrence[p.id] = w, r
            honored[p.id] = honors(warm.code, p.check)
        runs.append(
            {"run": run_no, "phase": "warm", "honored": honored,
             "weights": weights, "recurrence": recurrence}
        )
        # Reinforce the learnings (a repeat correction) so value-over-time grows next run.
        for p in prefs:
            if p.polarity == "learning":
                _capture(
                    scenario.name, p.polarity, p.body, p.scope,
                    f"showcase:{scenario.name}", warm_run_id,
                )
        if _all_stuck(runs, prefs, stick_streak):
            break

    _write_outputs(out_dir, scenario, prefs, runs, cold_code, warm_code, final_recall)
    return {
        "scenario": scenario.name,
        "runs": len(runs),
        "runs_to_stick": {p.id: _runs_to_stick(runs, p.id) for p in prefs},
    }


def _all_stuck(runs: list[dict], prefs, streak: int) -> bool:
    """True once every preference has been honored for the last ``streak`` runs."""
    if len(runs) < streak:
        return False
    tail = runs[-streak:]
    return all(all(r["honored"].get(p.id) for r in tail) for p in prefs)


def _runs_to_stick(runs: list[dict], pref_id: str) -> int | None:
    """First run number from which ``pref_id`` is honored through the end; ``None`` if never."""
    honored = [(r["run"], bool(r["honored"].get(pref_id))) for r in runs]
    for i, (run_no, ok) in enumerate(honored):
        if ok and all(h for _, h in honored[i:]):
            return run_no
    return None


def _write_outputs(
    out_dir: Path, scenario: Scenario, prefs, runs: list[dict], cold_code: str,
    warm_code: str, final_recall: dict,
) -> None:
    (out_dir / "recall.json").write_text(
        json.dumps(
            {"learnings": final_recall.get("learnings", []),
             "issues": final_recall.get("issues", [])},
            indent=2,
        ),
        encoding="utf-8",
    )
    diff = difflib.unified_diff(
        cold_code.splitlines(keepends=True), warm_code.splitlines(keepends=True),
        fromfile="cold/table.py", tofile="warm/table.py",
    )
    (out_dir / "diff.txt").write_text("".join(diff), encoding="utf-8")
    with (out_dir / "runs.jsonl").open("w", encoding="utf-8") as fh:
        for r in runs:
            fh.write(json.dumps(r) + "\n")


def _load_harness_env() -> None:
    """Load ``harness/.env`` (KEY=VALUE lines) into the environment for the documented workflow.

    ``--agent`` authenticates via ``ANTHROPIC_API_KEY``, which the harness README tells maintainers
    to put in ``harness/.env`` (gitignored). Existing environment vars win (``setdefault``), so an
    explicitly-exported key is never overridden.
    """
    env_file = config.HARNESS_ROOT / ".env"
    if not env_file.is_file():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        line = line.removeprefix("export ").strip()
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip("\"'"))


def _build_generator(args: argparse.Namespace) -> Generator:
    if args.agent:
        if not SKILL_DIR.is_dir():
            print(f"error: --agent needs a mounted skill at {SKILL_DIR}", file=sys.stderr)
            raise SystemExit(2)
        return AgentGenerator(skill_dir=SKILL_DIR, model=args.model)
    return StubGenerator()


def main() -> int:
    parser = argparse.ArgumentParser(description="Whetstone showcase runner (command-only).")
    parser.add_argument("--scenario", action="append", metavar="NAME",
                        help="Run only this scenario (repeatable). Default: all.")
    parser.add_argument("--agent", action="store_true",
                        help="Use the live Claude Agent SDK (paid). Default: the free stub.")
    parser.add_argument("--model", metavar="ID", default=None,
                        help="Model id for --agent (e.g. claude-haiku-4-5).")
    parser.add_argument("--max-runs", type=int, default=DEFAULT_MAX_RUNS)
    parser.add_argument("--stick-streak", type=int, default=DEFAULT_STICK_STREAK)
    args = parser.parse_args()

    # Load harness/.env (ANTHROPIC_API_KEY for --agent) before anything else, then pin the ST
    # backend + isolated store/config for the whole process before touching Whetstone.
    _load_harness_env()
    config.apply_showcase_env()

    scenarios = load_scenarios(SCENARIOS_DIR)
    if args.scenario:
        wanted = set(args.scenario)
        scenarios = [s for s in scenarios if s.name in wanted]
        missing = wanted - {s.name for s in scenarios}
        if missing:
            print(f"error: unknown scenario(s): {', '.join(sorted(missing))}", file=sys.stderr)
            return 2
    if not scenarios:
        print("error: no scenarios selected", file=sys.stderr)
        return 2

    generator = _build_generator(args)
    print(f"generator: {generator.name}  |  scenarios: {len(scenarios)}  |  out: {OUT_ROOT}")
    for s in scenarios:
        summary = run_scenario(
            s, generator, max_runs=args.max_runs, stick_streak=args.stick_streak
        )
        stick = ", ".join(f"{k}:{v}" for k, v in summary["runs_to_stick"].items())
        print(f"  {s.name:32} runs={summary['runs']}  runs_to_stick[{stick}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
