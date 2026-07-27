"""Out-of-band store maintenance — the ``compact`` pass (§7 "Distill & reconcile").

Compaction is a periodic janitorial sweep that keeps a store lean. It is NOT one of the five MCP
tools (attach/recall/capture/revise/metrics); it runs out-of-band via ``whetstone compact <skill>``
or by calling :func:`compact` directly. The whole pass runs under the per-store write lock and, in
order (§7, §5.4, §15):

1. **Dedupe** — collapse near-duplicate same-scope entries (cosine >= ``dedup_similarity``) into
   one. This is a batch version of capture-time dedup: for learnings the survivor's recurrence
   sums the collapsed counts and its dates widen (earliest ``first_seen``, latest ``last_seen``);
   for issues (no scoring fields) the near-duplicate blocks are simply dropped, keeping one.
2. **Merge overlapping scopes** (anti-fragmentation, §5.4) — merge two same-polarity scopes when
   their centroids OR their name/phrase embeddings are within the configured ε. The smaller scope's
   entries are folded into the larger (which keeps its phrase as the canonical name); each moved
   entry's ``scope`` field is rewritten and the emptied source file removed. Done per-polarity.
3. **Retire stale learnings** (§15) — drop learnings whose derived §4.4 ``weight`` (evaluated at
   ``today``) falls below ``retire_weight_threshold``. **Issues are NEVER auto-retired** (§7).

After mutating the markdown the index is rebuilt, the store is git-committed once (a single
``compact: …`` commit), and a ``compaction`` telemetry event is emitted — but only when the pass
actually changed something, so a no-op compaction on a clean store leaves no commit or event behind.

Retired/collapsed ids are recorded via :func:`record_id` before their entries leave the markdown, so
compaction never reuses an id (the same no-reuse guarantee ``remove_entry`` gives).

**M5a — behavioral mining (advisory).** On top of that *structural* pass, ``compact`` also *mines*
the store's ``events.jsonl`` for behavioral health signals — learnings that earned promotion
(``harden``), scopes with capture churn (``bad_capture``), learnings that decayed out of use
(``stale``), and unresolved conflicts (``conflict_residue``). These findings are **advisory only**:
they are reported (returned in the summary + written to a git-ignored ``compact-report.md``), never
auto-applied. Enacting one is a manual ``revise``/``whetstone`` call. Only the safe structural
subset above ever mutates automatically — the same conservatism ``compact`` has always had.

**``compact --all``** (``compact(all_skills=True)``) runs the per-skill pass over every registered
skill, then *detects* near-duplicate learnings that recur across ``global_skill_count`` distinct
skills. Per §M7a, this is **advisory-only**: ``--all`` never writes to the global store itself —
promotion (moving something into a broader/more-permanent status) always asks a human, and that
rule applies here too, not just at single-entry ``whetstone promote``. Each detected cluster is
reported as a ``global_candidate`` finding (same shape family as the M5a mining findings below),
naming a representative entry and the exact ``whetstone promote <skill> <id> --cluster`` command
that enacts it. Enacting one is :func:`whetstone.promotion.promote_cluster` — the writer half of
the global layer now lives there, invoked deliberately rather than run automatically by ``--all``.

TODO (§5.4): scope-merge/anti-fragmentation should also happen incrementally at capture time, so the
store never drifts far between compactions. This slice implements it only in the batch pass; the
capture-time variant is future work.
"""

from __future__ import annotations

import shlex
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import UTC, date, datetime

from .config import Config, load_config
from .embeddings import cosine, get_backend
from .scoring import weight
from .store import index
from .store.access import (
    load_issues,
    load_learnings,
    record_id,
    remove_entry,
    save_issue,
    save_learning,
)
from .store.index import _centroid, entry_text
from .store.layout import (
    StoreLocation,
    commit_store,
    ensure_store,
    read_registry,
    store_location,
    store_write_lock,
)
from .store.markdown import (
    parse_issues,
    parse_learnings,
    write_issues,
    write_learnings,
)
from .store.slug import scope_filename
from .telemetry import emit_compaction, read_events

_REPORT_NAME = "compact-report.md"


def compact(
    skill: str | None = None,
    *,
    all_skills: bool = False,
    today: date | None = None,
    config: Config | None = None,
) -> dict:
    """Run the compaction maintenance pass (§7) + M5a behavioral mining; return a summary.

    ``today`` is the reference date for the recency decay used to score learnings for retirement
    (§4.4); it defaults to the current UTC date and is injectable so tests are deterministic. The
    per-skill pass runs under that store's write lock and commits at most once. With
    ``all_skills=True`` every registered skill is compacted, and cross-skill clusters (learnings
    recurring across ``>= global_skill_count`` distinct skills) are reported — under the returned
    ``global_candidates`` key — as advisory findings, the same M5a finding shape as the per-skill
    behavioral mining below; ``skill`` is then ignored. This is **advisory only** (§M7a): ``--all``
    never writes to the global store or retires anything itself. Enacting one reported cluster is
    an explicit, separate call: ``whetstone promote <skill> <id> --cluster`` (or
    :func:`whetstone.promotion.promote_cluster` directly), naming the finding's representative.
    """
    if config is None:
        config = load_config()
    if today is None:
        today = datetime.now(UTC).date()
    if all_skills:
        return _compact_all(config, today)
    if skill is None:
        raise ValueError("compact requires a skill name (or all_skills=True)")
    return _compact_one(skill, config, today)


def _compact_one(skill: str, config: Config, today: date) -> dict:
    """The single-skill pass: safe structural auto-apply + the advisory behavioral report."""
    ensure_store(skill, config)
    loc = store_location(skill, config)
    backend = get_backend(config)

    with store_write_lock(loc):
        deduped = _dedup(loc, backend, config, "learning") + _dedup(loc, backend, config, "issue")
        merged = _merge_scopes(loc, backend, config, "learning") + _merge_scopes(
            loc, backend, config, "issue"
        )
        retired = _retire_stale_learnings(loc, config, today)

        changed = deduped + merged + retired
        committed = False
        if changed:
            index.rebuild_index(loc, backend)
            commit_store(
                loc,
                f"compact: deduped {deduped}, merged {merged} scope(s), retired {retired}",
            )
            emit_compaction(loc, retired=retired, merged_scopes=merged, deduped=deduped)
            committed = True

        # Behavioral mining reads the post-structural markdown + the event log (advisory only —
        # nothing below mutates the store). Done under the lock so it sees a consistent snapshot.
        findings = _mine(loc, config)

    report_path = _write_report(loc, skill, findings)

    return {
        "skill": skill,
        "deduped": deduped,
        "merged_scopes": merged,
        "retired": retired,
        "committed": committed,
        "findings": findings,
        "report_path": report_path,
    }


def _compact_all(config: Config, today: date) -> dict:
    """Compact every registered skill, then report (never write) cross-skill promotion candidates.

    §M7a: cross-skill promotion is advisory-only here — detected clusters come back as
    ``global_candidate`` findings under the ``global_candidates`` key; nothing is written to the
    global store by this path. A human enacts one deliberately via
    ``whetstone promote <skill> <id> --cluster`` (or :func:`whetstone.promotion.promote_cluster`).
    """
    skills = sorted(read_registry(config))
    per_skill = {s: _compact_one(s, config, today) for s in skills}
    backend = get_backend(config)
    global_candidates = _global_candidate_findings(skills, config, backend)
    return {"all": True, "skills": per_skill, "global_candidates": global_candidates}


# --------------------------------------------------------------------------- dedupe (step 1)


def _dedup(loc: StoreLocation, backend, config: Config, polarity: str) -> int:
    """Collapse near-duplicate same-scope entries into one; return how many were removed.

    Works per scope file (each file holds exactly one scope). Within a file, greedily assign each
    entry to the first representative it is within ``dedup_similarity`` of, else it starts a new
    representative. For learnings the representative absorbs the duplicate's recurrence/dates; for
    issues the duplicate is just dropped. Removed ids are recorded so they are never reused.
    """
    if polarity == "learning":
        directory, parse, write = loc.learnings_dir, parse_learnings, write_learnings
    else:
        directory, parse, write = loc.issues_dir, parse_issues, write_issues

    deduped = 0
    for path in sorted(directory.glob("*.md")):
        entries = parse(path.read_text(encoding="utf-8"))
        if len(entries) < 2:
            continue
        vectors = backend.embed([entry_text(e.title, e.body) for e in entries])
        reps: list[list] = []  # [entry, vector] pairs kept as representatives
        removed = 0
        for entry, vec in zip(entries, vectors, strict=True):
            match = next(
                (r for r in reps if cosine(vec, r[1]) >= config.dedup_similarity), None
            )
            if match is None:
                reps.append([entry, vec])
                continue
            if polarity == "learning":
                match[0] = _absorb_learning(match[0], entry)
            record_id(loc, entry.id)  # remember the id before it leaves the markdown (no reuse)
            removed += 1
        if removed:
            write(path, [r[0] for r in reps])
            deduped += removed
    return deduped


def _absorb_learning(survivor, other):
    """Fold ``other`` into ``survivor``: sum recurrence, widen the date span (earliest first_seen,
    latest last_seen). The survivor's prose/scope/id/provenance are kept."""
    return replace(
        survivor,
        recurrence=survivor.recurrence + other.recurrence,
        first_seen=min(survivor.first_seen, other.first_seen),
        last_seen=max(survivor.last_seen, other.last_seen),
    )


# --------------------------------------------------------------------------- merge scopes (step 2)


def _merge_scopes(loc: StoreLocation, backend, config: Config, polarity: str) -> int:
    """Merge overlapping same-polarity scopes (§5.4); return how many scopes were folded away.

    Two scopes overlap when their centroids are within ε_c OR their name/phrase embeddings are
    within ε_n. Overlap is grouped transitively (union-find); within each group the scope with most
    entries becomes canonical and the rest are folded into it (entries moved, ``scope`` field
    rewritten, emptied source files removed). Ids are unchanged by a move, so no id is retired here.
    """
    if polarity == "learning":
        entries = load_learnings(loc)
        directory, save = loc.learnings_dir, save_learning
    else:
        entries = load_issues(loc)
        directory, save = loc.issues_dir, save_issue

    by_scope: dict[str, list] = {}
    for entry in entries:
        by_scope.setdefault(entry.scope, []).append(entry)
    scopes = sorted(by_scope)
    if len(scopes) < 2:
        return 0

    name_vecs = backend.embed(scopes)
    centroids = [
        _centroid(backend.embed([entry_text(e.title, e.body) for e in by_scope[s]]), backend.dim)
        for s in scopes
    ]

    parent = list(range(len(scopes)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)

    for i in range(len(scopes)):
        for j in range(i + 1, len(scopes)):
            if (
                cosine(centroids[i], centroids[j]) >= config.scope_merge_centroid_eps
                or cosine(name_vecs[i], name_vecs[j]) >= config.scope_merge_name_eps
            ):
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(len(scopes)):
        groups.setdefault(find(i), []).append(i)

    merged = 0
    for members in groups.values():
        if len(members) < 2:
            continue
        # Canonical target: most entries wins, scope name breaks ties (deterministic).
        target = max(members, key=lambda i: (len(by_scope[scopes[i]]), scopes[i]))
        target_scope = scopes[target]
        for i in members:
            if i == target:
                continue
            source_scope = scopes[i]
            for entry in by_scope[source_scope]:
                save(loc, replace(entry, scope=target_scope))  # writes into the target scope file
            (directory / scope_filename(source_scope)).unlink(missing_ok=True)
            merged += 1
    return merged


# --------------------------------------------------------------------------- retire (step 3)


def _retire_stale_learnings(loc: StoreLocation, config: Config, today: date) -> int:
    """Remove learnings whose derived §4.4 weight (at ``today``) is below the retire threshold.

    Issues are never scored and never retired (§7) — only learnings are considered. Removal goes
    through :func:`remove_entry`, which records the id first so it is never reused.
    """
    retired = 0
    for entry in load_learnings(loc):
        w = weight(
            entry.recurrence,
            entry.last_seen,
            today,
            decay=config.learnings_decay,
            half_life_days=config.learnings_half_life_days,
        )
        if w < config.retire_weight_threshold:
            remove_entry(loc, entry.id)
            retired += 1
    return retired


# --------------------------------------------------------------------------- M5a behavioral mining


def _mine(loc: StoreLocation, config: Config) -> list[dict]:
    """Mine the event log for advisory behavioral findings (§M5a). Never mutates the store.

    Returns a list of findings, each a JSON-friendly dict: ``rule``, ``id``/``scope`` (as relevant),
    ``evidence`` (counts + a few example ``run_ids``), and ``enact`` (the exact command to act on
    it). All four rules are read-only: enacting any of them is a manual ``revise``/``whetstone``
    call.
    """
    events = read_events(loc)
    learnings = {e.id: e for e in load_learnings(loc)}
    issues = {e.id: e for e in load_issues(loc)}
    return (
        _mine_harden(events, learnings, config)
        + _mine_bad_capture(events, config)
        + _mine_stale(events, learnings, config)
        + _mine_conflict_residue(events, learnings, issues)
    )


def _reinforced_ids(events: list[dict]) -> set[str]:
    """Ids reinforced via either capture-dedup (``reinforced``) or ``revise(reinforce)``."""
    out: set[str] = set()
    for e in events:
        if e.get("type") == "capture" and e.get("status") == "reinforced":
            out.add(e.get("entry_id"))
        elif e.get("type") == "revise" and e.get("action") == "reinforce":
            out.add(e.get("entry_id"))
    return out


def _mine_harden(events: list[dict], learnings: dict, config: Config) -> list[dict]:
    """A still-present learning reinforced >= ``harden_reinforcements`` times and NEVER weakened →
    suggest promoting it to a mandatory issue (advisory; learning→issue is a polarity change)."""
    reinforce_runs: dict[str, list[str]] = defaultdict(list)
    weakened: set[str] = set()
    for e in events:
        eid = e.get("entry_id")
        if e.get("type") == "capture" and e.get("status") == "reinforced":
            reinforce_runs[eid].append(e.get("run_id"))
        elif e.get("type") == "revise":
            action = e.get("action")
            if action == "reinforce":
                reinforce_runs[eid].append(e.get("run_id"))
            elif action in ("weaken", "remove"):
                weakened.add(eid)

    findings = []
    for eid, runs in reinforce_runs.items():
        if eid in learnings and eid not in weakened and len(runs) >= config.harden_reinforcements:
            findings.append(
                {
                    "rule": "harden",
                    "id": eid,
                    "scope": learnings[eid].scope,
                    "evidence": {
                        "reinforcements": len(runs),
                        "run_ids": [r for r in runs if r][:3],
                    },
                    "enact": (
                        f"revise(skill, entry_id={eid!r}, action='promote', confirm='promote', "
                        "body='<objective Always/Never rule>')"
                    ),
                }
            )
    return findings


def _mine_bad_capture(events: list[dict], config: Config) -> list[dict]:
    """A scope with capture churn — repeated committed learnings AND >= 1 weaken/remove — the
    original capture was likely too broad or wrong. Advisory: propose reviewing the scope."""
    committed: Counter[str] = Counter()
    churn: Counter[str] = Counter()
    runs: dict[str, list[str]] = defaultdict(list)
    for e in events:
        scope = e.get("scope")
        if not scope:
            continue
        if (
            e.get("type") == "capture"
            and e.get("status") == "committed"
            and e.get("polarity") == "learning"
        ):
            committed[scope] += 1
            if e.get("run_id"):
                runs[scope].append(e["run_id"])
        elif e.get("type") == "revise" and e.get("action") in ("weaken", "remove"):
            churn[scope] += 1
            if e.get("run_id"):
                runs[scope].append(e["run_id"])

    findings = []
    for scope in sorted(set(committed) | set(churn)):
        if committed[scope] >= 2 and churn[scope] >= 1:
            findings.append(
                {
                    "rule": "bad_capture",
                    "id": None,
                    "scope": scope,
                    "evidence": {
                        "committed_learnings": committed[scope],
                        "weaken_or_remove": churn[scope],
                        "run_ids": runs[scope][:3],
                    },
                    "enact": (
                        f"review scope {scope!r}: repeated captures + corrections suggest it was "
                        "too broad — consolidate/reword via revise(...)"
                    ),
                }
            )
    return findings


def _mine_stale(events: list[dict], learnings: dict, config: Config) -> list[dict]:
    """Usage-based staleness (richer than pure decay): a present learning never reinforced that was
    either never surfaced across >= ``stale_runs`` recalls, or surfaced that often yet never
    reinforced → a retire nudge."""
    recalls = [e for e in events if e.get("type") == "recall"]
    total = len(recalls)
    returned: Counter[str] = Counter()
    for e in recalls:
        for lid in e.get("returned", {}).get("learnings", []):
            returned[lid] += 1
    reinforced = _reinforced_ids(events)

    findings = []
    for eid, entry in learnings.items():
        if eid in reinforced:
            continue
        seen = returned.get(eid, 0)
        if total >= config.stale_runs and seen == 0:
            reason = "never surfaced by recall across many runs"
        elif seen >= config.stale_runs:
            reason = "surfaced by recall many times but never reinforced"
        else:
            continue
        findings.append(
            {
                "rule": "stale",
                "id": eid,
                "scope": entry.scope,
                "evidence": {"recall_runs": total, "times_returned": seen, "reason": reason},
                "enact": (
                    f"let decay retire it, or revise(skill, entry_id={eid!r}, action='remove', "
                    "confirm=true)"
                ),
            }
        )
    return findings


_RESIDUE_STATUSES = ("conflict", "possible_contradiction")


def _mine_conflict_residue(events: list[dict], learnings: dict, issues: dict) -> list[dict]:
    """A capture that surfaced a ``conflict`` (cross-polarity) OR a ``possible_contradiction``
    (§M7c, same-polarity) against a still-present entry which was never LATER revised → an
    unresolved contradiction to decide on. Both are signal-only outcomes that write nothing, so
    without this they'd otherwise sit invisible forever — a `compact` report with no residue would
    wrongly look clean while one keeps blocking every recapture of the same wording.

    Order-sensitive by construction (``events`` is the append-ordered event log, §telemetry): a
    ``revise`` only resolves a residue finding it comes AFTER, not one that arrives later. An
    earlier version built a single flat "ever revised" id set irrespective of ordering, so a revise
    that happened BEFORE a later, still-unresolved conflict/contradiction on the same entry wrongly
    counted as having resolved it (round-5 Codex review finding). Walking the log in order and
    clearing/re-adding a pending finding on each relevant event fixes this precisely.
    """
    pending: dict[str, dict] = {}  # entry id -> the finding data, present only while unresolved
    for e in events:
        etype = e.get("type")
        if etype == "revise":
            pending.pop(e.get("entry_id"), None)  # any revise since resolves what was pending
            continue
        if etype != "capture" or e.get("status") not in _RESIDUE_STATUSES:
            continue
        wid = e.get("entry_id")
        if wid in learnings:
            scope = learnings[wid].scope
        elif wid in issues:
            scope = issues[wid].scope
        else:
            continue  # the entry it clashed with is gone — nothing left to resolve
        pending[wid] = {"run_id": e.get("run_id"), "scope": scope}
    return [
        {
            "rule": "conflict_residue",
            "id": wid,
            "scope": data["scope"],
            "evidence": {"run_id": data["run_id"]},
            "enact": f"resolve the unresolved conflict on {wid!r} via revise(...)",
        }
        for wid, data in pending.items()
    ]


def _write_report(loc: StoreLocation, skill: str, findings: list[dict]) -> str | None:
    """Write the advisory findings to the git-ignored ``compact-report.md``; return its path.

    A run with no findings removes any stale prior report and returns ``None`` (so the file never
    misrepresents an old pass). The report is never committed (per-store ``.gitignore``)."""
    path = loc.path / _REPORT_NAME
    if not findings:
        path.unlink(missing_ok=True)
        return None
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    lines = [
        f"# Whetstone compact report — {skill}",
        "",
        f"_Generated {stamp}._ These are **advisory** behavioral findings — nothing was "
        "auto-applied. Enact each with the command shown.",
        "",
    ]
    for f in findings:
        heading = f.get("scope") or f.get("id") or "—"
        lines.append(f"## `{f['rule']}` — {heading}")
        if f.get("id"):
            lines.append(f"- entry: `{f['id']}`")
        if f.get("scope"):
            lines.append(f"- scope: {f['scope']}")
        lines.append(f"- evidence: `{f['evidence']}`")
        lines.append(f"- enact: {f['enact']}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


# ----------------------------------------------------------- M5a/M7a cross-skill detection (--all)


def find_cross_skill_clusters(
    config: Config, backend, skills: list[str] | None = None
) -> list[list[tuple[str, object]]]:
    """Detect learnings that recur across >= ``config.global_skill_count`` distinct skills.

    Pure detection — never writes anything. Clustering mirrors dedup: cosine >= ``dedup_similarity``
    over the existing embedding backend, but only *across* skills (within-skill dupes are the
    per-skill dedup pass's job). Returns one list of ``(skill, entry)`` pairs per qualifying
    cluster. Shared by ``compact --all`` (which only reports these, see :func:`_compact_all`) and
    :func:`whetstone.promotion.promote_cluster` (which enacts exactly one, by hand).
    """
    if skills is None:
        skills = sorted(read_registry(config))

    items: list[tuple[str, object, list[float]]] = []  # (skill, entry, vector)
    for s in skills:
        loc = store_location(s, config)
        entries = load_learnings(loc)
        if not entries:
            continue
        vectors = backend.embed([entry_text(e.title, e.body) for e in entries])
        for entry, vec in zip(entries, vectors, strict=True):
            items.append((s, entry, vec))

    n = len(items)
    if n < 2:
        return []

    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)

    for i in range(n):
        for j in range(i + 1, n):
            if items[i][0] != items[j][0] and (
                cosine(items[i][2], items[j][2]) >= config.dedup_similarity
            ):
                union(i, j)

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)

    clusters: list[list[tuple[str, object]]] = []
    for members in groups.values():
        cluster = [(items[i][0], items[i][1]) for i in members]
        distinct = {s for s, _ in cluster}
        if len(distinct) < config.global_skill_count:
            continue
        clusters.append(cluster)
    return clusters


def cluster_representative(cluster: list[tuple[str, object]]) -> tuple[str, object]:
    """Deterministic representative pick for a cluster: highest recurrence wins; skill then id
    break ties. Shared by ``compact --all``'s reporting and ``promote_cluster``'s enactment so both
    always agree on which entry a given cluster's finding names."""
    return max(cluster, key=lambda c: (c[1].recurrence, c[0], c[1].id))


def _global_candidate_findings(skills: list[str], config: Config, backend) -> list[dict]:
    """Shape each detected cross-skill cluster as an advisory ``global_candidate`` finding.

    Never writes anything (§M7a) — pairs with :func:`find_cross_skill_clusters` for detection and
    names the exact ``whetstone promote ... --cluster`` command a human runs to enact one.
    """
    findings = []
    for cluster in find_cross_skill_clusters(config, backend, skills=skills):
        rep_skill, rep_entry = cluster_representative(cluster)
        distinct = sorted({s for s, _ in cluster})
        findings.append(
            {
                "rule": "global_candidate",
                "representative": {"skill": rep_skill, "id": rep_entry.id},
                "skills": distinct,
                "evidence": {
                    "cluster_size": len(cluster),
                    "members": [{"skill": s, "id": e.id} for s, e in cluster],
                },
                # shlex.quote so a skill name containing whitespace or shell metacharacters still
                # yields a valid, safe, copy-pasteable command (a skill name is user-/model-chosen
                # free text, not guaranteed to be a bare shell token).
                "enact": (
                    f"whetstone promote {shlex.quote(rep_skill)} {shlex.quote(rep_entry.id)} "
                    "--cluster"
                ),
            }
        )
    return findings
