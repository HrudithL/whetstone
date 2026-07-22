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

Outputs per scenario under ``out/<skill>/<name>/``: ``cold/<primary>`` (+ the skill's render
artifacts / transcript for the agent), ``warm/<primary>``, ``recall.json`` (verbatim final learned
layer), ``diff.txt``, and ``runs.jsonl`` (per-run honored map + weight/recurrence snapshots — the
input to the metrics slice). The primary artifact and render set come from the skill's
:class:`~harness.skills.SkillSpec` (``table.py`` for great-tables, ``index.html`` for a web skill).
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
from .skills import SkillSpec, get_spec

SCENARIOS_DIR = config.HARNESS_ROOT / "scenarios"
OUT_ROOT = config.HARNESS_ROOT / "out"
SKILL_ROOT = config.HARNESS_ROOT / "skill"

DEFAULT_MAX_RUNS = 5
DEFAULT_STICK_STREAK = 2


def elaborated_intent(scenario: Scenario, spec: SkillSpec) -> str:
    """A recall ``intent`` that elaborates the task's styling dimensions (per recall's contract).

    Deliberately generic — it names the *dimensions* a decision spans, not the answers — so
    retrieval must match the seeded scopes rather than being handed them. The lead phrase and the
    dimensions come from the scenario's :class:`~harness.skills.SkillSpec`.
    """
    return (
        f"Styling {spec.intent_lead} for this task: {scenario.prompt.strip()} "
        f"Consider {spec.intent_dimensions}."
    )


def store_id(scenario: Scenario) -> str:
    """The Whetstone ``skill`` id for a scenario's isolated store: ``<skill>-<scenario>``.

    Keyed by skill (the store dirs group by skill) yet unique per scenario, so each scenario's
    COLD run still sees a genuinely empty store — a literally-shared per-skill store would let one
    scenario's seeded learnings pollute another's cold baseline. Slugified by Whetstone into
    ``<skill>-<scenario>-<hash>`` under the gitignored ``.store/``.
    """
    return f"{scenario.skill}-{scenario.name}"


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


def _metrics(skill: str) -> dict:
    from whetstone.server import metrics

    return metrics(skill=skill)


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
    src = (config.HARNESS_ROOT / scenario.data).resolve()
    if not src.is_file():
        # Fail before spending a live generation on a prompt that claims the data is present.
        raise FileNotFoundError(
            f"{scenario.name}: data file not found: {scenario.data} (resolved {src})"
        )
    d = Path(tempfile.mkdtemp(prefix=f"whetstone-showcase-{scenario.name}-"))
    shutil.copy2(src, d / src.name)
    return _Work(d)


def _persist(
    result: GenerationResult, spec: SkillSpec, workdir: Path, phase_dir: Path
) -> None:
    """Copy the generated artifacts out of the (soon-deleted) workdir into ``phase_dir``."""
    phase_dir.mkdir(parents=True, exist_ok=True)
    (phase_dir / spec.output).write_text(result.code, encoding="utf-8")
    # Capture the skill's rendered artifacts from the workdir before it is torn down (e.g.
    # great-tables' table.png raster + native table.html; a slide skill's deck.pptx). Best-effort:
    # the stub does not produce them, and the agent path has already fail-loud-checked them.
    for artifact in spec.required_artifacts:
        src = workdir / artifact
        if src.is_file():
            shutil.copy2(src, phase_dir / artifact)
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
    """Run the cold→seed→warm loop for one scenario; write ``out/<skill>/<name>/`` and return a
    summary.

    Artifacts are written to a staging dir and swapped into ``out/<skill>/<name>`` **only after the
    whole scenario succeeds**, so a mid-run failure (e.g. the agent renders no PNG, or the API
    aborts) leaves the previously committed artifacts intact rather than half-deleted.
    """
    # Validate the data file BEFORE anything destructive: _reset_store() deletes the per-scenario
    # store, so a missing CSV must fail here rather than after wiping a prior run's telemetry.
    src = (config.HARNESS_ROOT / scenario.data).resolve()
    if not src.is_file():
        raise FileNotFoundError(
            f"{scenario.name}: data file not found: {scenario.data} (resolved {src})"
        )

    _reset_store(store_id(scenario))
    stage = Path(tempfile.mkdtemp(prefix=f"whetstone-stage-{scenario.name}-"))
    try:
        summary = _run_scenario_into(
            scenario, generator, stage, max_runs=max_runs, stick_streak=stick_streak
        )
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    _swap_into_place(stage, out_root / scenario.skill / scenario.name)
    return summary


def _swap_into_place(stage: Path, out_dir: Path) -> None:
    """Install ``stage`` at ``out_dir``, keeping the old artifacts until the new ones are in place.

    The old directory is renamed aside first (a same-filesystem, near-atomic rename), the staged
    artifacts are moved in, and only then is the backup removed. If installing the new artifacts
    fails (e.g. a cross-filesystem ``shutil.move`` errors partway), the backup is restored, so the
    committed artifacts survive a failure during the swap itself — not just during generation.
    """
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    backup = out_dir.with_name(f"{out_dir.name}.old-{os.getpid()}")
    shutil.rmtree(backup, ignore_errors=True)
    had_old = out_dir.exists()
    if had_old:
        os.rename(out_dir, backup)
    try:
        shutil.move(str(stage), str(out_dir))
    except BaseException:
        shutil.rmtree(out_dir, ignore_errors=True)  # remove any partial install
        if had_old:
            os.rename(backup, out_dir)  # restore the previous artifacts
        raise
    if had_old:
        shutil.rmtree(backup, ignore_errors=True)


def _run_scenario_into(
    scenario: Scenario,
    generator: Generator,
    out_dir: Path,
    *,
    max_runs: int,
    stick_streak: int,
) -> dict:
    """The cold→seed→warm loop, writing all artifacts under ``out_dir`` (a staging dir)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    spec = get_spec(scenario.skill)
    skill = store_id(scenario)
    intent = elaborated_intent(scenario, spec)
    prefs = scenario.preferences
    runs: list[dict] = []
    cold_code = warm_code = ""
    final_recall: dict = {"learnings": [], "issues": []}

    # ---- COLD (run 1): empty store, nothing injected -------------------------------------------
    # Recall anyway (the model consults the skill and finds nothing) so the cold run is a real,
    # empty-payload recall event; its run_id ties the seeding corrections to this run.
    cold_recall = _recall(skill, intent)
    cold_run_id = cold_recall.get("run_id")
    with _make_workdir(scenario) as wd:
        cold = generator.generate(scenario, "", wd)
        _persist(cold, spec, wd, out_dir / "cold")
    cold_code = cold.code
    runs.append(
        {
            "run": 1,
            "phase": "cold",
            "honored": {p.id: honors(cold.code, p.check, spec.check_language) for p in prefs},
            "weights": {p.id: None for p in prefs},
            "recurrence": {p.id: None for p in prefs},
        }
    )

    # ---- SEED: the user corrects the skill after the cold output --------------------------------
    entry_ids: dict[str, str | None] = {}
    for p in prefs:
        res = _capture(
            skill, p.polarity, p.body, p.scope, f"showcase:{scenario.name}", cold_run_id
        )
        entry_ids[p.id] = res.get("entry_id")

    # ---- WARM (runs 2..N): recall + inject + regenerate + reinforce -----------------------------
    run_no = 1
    final_learned = ""
    while run_no < max_runs:
        run_no += 1
        payload = _recall(skill, intent)
        final_recall = payload
        warm_run_id = payload.get("run_id")
        learned = format_learned_layer(payload)
        final_learned = learned
        with _make_workdir(scenario) as wd:
            warm = generator.generate(scenario, learned, wd)
            _persist(warm, spec, wd, out_dir / "warm")
        warm_code = warm.code
        weights, recurrence, honored = {}, {}, {}
        for p in prefs:
            w, r = _weight_recurrence(payload, entry_ids.get(p.id) or "")
            weights[p.id], recurrence[p.id] = w, r
            honored[p.id] = honors(warm.code, p.check, spec.check_language)
        runs.append(
            {"run": run_no, "phase": "warm", "honored": honored,
             "weights": weights, "recurrence": recurrence}
        )
        # Reinforce the learnings (a repeat correction) so value-over-time grows next run.
        for p in prefs:
            if p.polarity == "learning":
                _capture(
                    skill, p.polarity, p.body, p.scope,
                    f"showcase:{scenario.name}", warm_run_id,
                )
        if _all_stuck(runs, prefs, stick_streak):
            break

    _write_outputs(out_dir, scenario, prefs, runs, cold_code, warm_code, final_recall)
    # The exact learned-layer text injected into the final warm run's prompt — this, not the raw
    # recall.json, is "what the model was told", so the triptych's middle panel renders it verbatim.
    (out_dir / "learned_layer.txt").write_text(final_learned, encoding="utf-8")
    summary = _scenario_summary(
        scenario, generator, runs, stick_streak, max_runs, usage_kpis=_metrics(skill)
    )
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _scenario_summary(
    scenario: Scenario, generator: Generator, runs: list[dict], stick_streak: int,
    max_runs: int, usage_kpis: dict,
) -> dict:
    """Per-scenario facts the metrics slice aggregates (committed as ``out/<name>/summary.json``).

    Carries the two headline metrics per preference — ``runs_to_stick`` and the value-over-time
    (weight/recurrence) trajectory — plus the cold baseline and the store's usage KPIs captured
    while the store still exists (``.store`` is gitignored, so this is the durable copy).
    """
    warm = [r for r in runs if r.get("phase") == "warm"]
    cold = next((r for r in runs if r.get("phase") == "cold"), None)
    prefs_out: dict[str, dict] = {}
    for p in scenario.preferences:
        prefs_out[p.id] = {
            "polarity": p.polarity,
            "scope": p.scope,
            "cold_honored": bool(cold["honored"].get(p.id)) if cold else None,
            "runs_to_stick": _runs_to_stick(runs, p.id, stick_streak),
            "value_over_time": [
                {"run": r["run"], "weight": r["weights"].get(p.id),
                 "recurrence": r["recurrence"].get(p.id)}
                for r in warm
            ],
        }
    return {
        "scenario": scenario.name,
        "skill": scenario.skill,
        "output": get_spec(scenario.skill).output,  # primary artifact filename (site reads it)
        "difficulty": scenario.difficulty,
        "generator": generator.name,
        "params": {"max_runs": max_runs, "stick_streak": stick_streak},
        "runs": len(runs),
        "preferences": prefs_out,
        "usage_kpis": usage_kpis,
    }


def _all_stuck(runs: list[dict], prefs, streak: int) -> bool:
    """True once every preference has been honored for the last ``streak`` **warm** runs.

    Only warm (post-seeding) runs count: a cold run that coincidentally satisfies a broad check must
    not contribute to "stuck", or a lucky before-state would end the loop before the learned layer
    has actually been applied ``streak`` times.
    """
    warm = [r for r in runs if r.get("phase") == "warm"]
    if len(warm) < streak:
        return False
    tail = warm[-streak:]
    return all(all(r["honored"].get(p.id) for r in tail) for p in prefs)


def _runs_to_stick(runs: list[dict], pref_id: str, stick_streak: int) -> int | None:
    """First **warm** run from which ``pref_id`` is honored to the end for ≥ ``stick_streak`` runs.

    Only warm (post-seeding) runs count — the cold baseline is excluded, so a cold run that happens
    to satisfy a broad check can't report the preference as stuck before it was even captured.
    ``None`` if it never stuck, including the truncated case where ``--max-runs`` was hit before the
    required consecutive-honored streak was reached.
    """
    warm = [r for r in runs if r.get("phase") == "warm"]
    honored = [(r["run"], bool(r["honored"].get(pref_id))) for r in warm]
    for i, (run_no, ok) in enumerate(honored):
        tail = honored[i:]
        if ok and len(tail) >= stick_streak and all(h for _, h in tail):
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
    # The skill dir is per-scenario now (a run may span several skills), so it is resolved inside
    # AgentGenerator per scenario; main() preflights each scenario's skill before any run.
    if args.agent:
        return AgentGenerator(model=args.model)
    return StubGenerator()


def _preflight_skills(scenarios: list[Scenario], *, need_dir: bool) -> str | None:
    """Return an error string if any scenario's skill lacks a SkillSpec (or, for ``--agent``, a
    vendored dir); ``None`` if all are runnable. Runs before any destructive work."""
    for s in scenarios:
        try:
            spec = get_spec(s.skill)
        except KeyError as exc:
            return f"{s.name}: {exc}"
        if need_dir and not (SKILL_ROOT / spec.name).is_dir():
            return f"{s.name}: --agent needs a mounted skill dir at {SKILL_ROOT / spec.name}"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Whetstone showcase runner (command-only).")
    parser.add_argument("--scenario", action="append", metavar="NAME",
                        help="Run only this scenario (repeatable). Default: all.")
    # Require an explicit mode: `python -m harness.run` alone must NOT silently pick a generator,
    # because a run clears out/<scenario>/ first — an accidental stub run would clobber the
    # committed real artifacts with synthetic table.py-only outputs.
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--agent", action="store_true",
                      help="Use the live Claude Agent SDK (paid) to produce the real artifacts.")
    mode.add_argument("--stub", action="store_true",
                      help="Use the deterministic free stub (pipeline verification only).")
    parser.add_argument("--model", metavar="ID", default=None,
                        help="Model id for --agent (e.g. claude-haiku-4-5).")
    parser.add_argument("--max-runs", type=int, default=DEFAULT_MAX_RUNS)
    parser.add_argument("--stick-streak", type=int, default=DEFAULT_STICK_STREAK)
    args = parser.parse_args()

    # Validate BEFORE any destructive work (run_scenario clears out/<scenario>/). max_runs must
    # allow at least one warm run (run 1 is always cold), else a run would wipe artifacts and write
    # no warm output / a diff against an empty string.
    if args.max_runs < 2:
        print("error: --max-runs must be >= 2 (run 1 is cold; warm needs >= 2)", file=sys.stderr)
        return 2
    if args.stick_streak < 1:
        print("error: --stick-streak must be >= 1", file=sys.stderr)
        return 2

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

    # Preflight the skill mapping before any destructive run (run_scenario resets each store).
    err = _preflight_skills(scenarios, need_dir=args.agent)
    if err:
        print(f"error: {err}", file=sys.stderr)
        return 2

    # Only --agent writes the committed artifacts. --stub is a verification-only run, so route BOTH
    # its output root AND its Whetstone store to throwaway temp dirs — a stub run must never
    # delete/replace the committed out/ artifacts, and (since run_scenario resets each scenario's
    # store) it must not wipe the real .store/events.jsonl telemetry a prior --agent run produced.
    if args.stub:
        out_root = Path(tempfile.mkdtemp(prefix="whetstone-stub-out-"))
        os.environ["WHETSTONE_STORE_ROOT"] = tempfile.mkdtemp(prefix="whetstone-stub-store-")
        print(f"stub mode: throwaway artifacts -> {out_root} (committed out/ + .store untouched)")
    else:
        out_root = OUT_ROOT

    generator = _build_generator(args)
    print(f"generator: {generator.name}  |  scenarios: {len(scenarios)}  |  out: {out_root}")
    for s in scenarios:
        summary = run_scenario(
            s, generator, max_runs=args.max_runs, stick_streak=args.stick_streak,
            out_root=out_root,
        )
        stick = ", ".join(f"{k}:{v['runs_to_stick']}" for k, v in summary["preferences"].items())
        print(f"  {s.name:32} runs={summary['runs']}  runs_to_stick[{stick}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
