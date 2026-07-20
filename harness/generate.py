"""Table generation for the showcase runner (M3).

The runner needs, per run, a ``table.py`` produced *either* with an empty Whetstone store (COLD) or
with the recalled learned layer injected (WARM). This module abstracts that behind
:class:`Generator` so the orchestration in ``run.py`` is identical however the code was produced:

* :class:`AgentGenerator` drives the **live** model via the Claude Agent SDK with the great-tables
  skill mounted — the real, paid path used to produce the committed artifacts.
* :class:`StubGenerator` is **deterministic and free**: it fabricates a ``table.py`` that honors
  exactly the preferences present in the injected learned layer. It exercises the entire pipeline
  (seed → recall → check → iterate → write ``out/``) against *real* Whetstone without any API spend,
  so the orchestration can be verified in CI-free local runs and before the real generation.

Also holds the two pure helpers shared across the runner: :func:`honors` (does a ``table.py``
satisfy a preference's ``check``?) and :func:`format_learned_layer` (render a ``recall`` payload
into the instruction block injected on WARM runs — the same text saved verbatim for the triptych).
"""

from __future__ import annotations

import ast
import io
import re
import shutil
import tokenize
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .schema import Check, Preference, Scenario


@dataclass
class GenerationResult:
    """One generated ``table.py`` plus whatever provenance the generator can supply."""

    code: str
    transcript: list = field(default_factory=list)  # raw model messages; empty for the stub


def _strip_docstrings(tree: ast.AST) -> None:
    """Drop docstrings (leading bare string-literal statements) from every scope in ``tree``."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            body = node.body
            first = body[0] if body else None
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                body[0] = ast.Pass() if len(body) == 1 else None  # placeholder; filtered next
                node.body = [s for s in body if s is not None]


def code_for_check(code: str) -> str:
    """Return ``code`` reduced to *executable* source for checking — comments AND docstrings gone.

    A live agent writes explanatory prose as comments and docstrings, so ``# avoid green`` or
    ``\"\"\"use fmt_currency\"\"\"`` must not fool the checks. Parsing to an AST and unparsing drops
    both while preserving string literals that are actually *arguments* (e.g. ``palette="green"``,
    which a ``code_absent: green`` check must still catch). If the agent's code doesn't parse, fall
    back to tokenize-based comment stripping (keeps ``#`` inside strings intact).
    """
    try:
        tree = ast.parse(code)
        _strip_docstrings(tree)
        return ast.unparse(tree)
    except (SyntaxError, ValueError):
        try:
            toks = [
                (t.type, t.string)
                for t in tokenize.generate_tokens(io.StringIO(code).readline)
                if t.type != tokenize.COMMENT
            ]
            return tokenize.untokenize(toks)
        except (tokenize.TokenError, IndentationError, ValueError):
            return "\n".join(line.split("#", 1)[0] for line in code.splitlines())


def honors(code: str, check: Check) -> bool:
    """Does ``code`` satisfy ``check``? The runner's one source of truth for "was it applied?".

    Runs against :func:`code_for_check` output (comments + docstrings removed) so only executable
    code counts. ``*_absent`` kinds assert the pattern is gone; the others assert it is present.
    """
    src = code_for_check(code)
    if check.kind == "code_contains":
        return check.pattern in src
    if check.kind == "code_absent":
        return check.pattern not in src
    if check.kind == "regex":
        return re.search(check.pattern, src) is not None
    if check.kind == "regex_absent":
        return re.search(check.pattern, src) is None
    raise ValueError(f"unknown check kind: {check.kind!r}")  # pragma: no cover - schema-guarded


def format_learned_layer(recall_payload: dict) -> str:
    """Render a ``recall`` payload into the instruction block injected on WARM runs.

    This is intentionally the verbatim learned layer — ids, scopes, weights, and rule/issue text —
    not a paraphrase: it is exactly what the model is told, and the triptych's middle panel shows
    the same content. Returns ``""`` for an empty store (a COLD run injects nothing).
    """
    learnings = recall_payload.get("learnings", [])
    issues = recall_payload.get("issues", [])
    if not learnings and not issues:
        return ""
    lines = [
        "You have a LEARNED LAYER of this user's preferences for this skill, captured from earlier "
        "runs. Apply ALL of it. Learnings are weighted tastes (higher weight = more established); "
        "issues are mandatory rules.",
        "",
    ]
    if learnings:
        lines.append("Learnings (preferences):")
        for x in learnings:
            w = x.get("weight")
            wtxt = f", weight {w:.2f}" if isinstance(w, int | float) else ""
            lines.append(f"  - [{x.get('id')}] ({x.get('scope')}{wtxt}) {x.get('rule')}")
    if issues:
        lines.append("Issues (mandatory constraints):")
        for x in issues:
            lines.append(f"  - [{x.get('id')}] ({x.get('scope')}) {x.get('rule')}")
    return "\n".join(lines)


class Generator(Protocol):
    """Produces a ``table.py`` for a scenario, optionally guided by an injected learned layer."""

    name: str

    def generate(
        self, scenario: Scenario, learned_layer: str, workdir: Path
    ) -> GenerationResult: ...


# --------------------------------------------------------------------------------------------------
# Deterministic stub (no API spend) — verifies the whole pipeline against real Whetstone.
# --------------------------------------------------------------------------------------------------


def _regex_sample(pattern: str) -> str:
    """Best-effort literal that satisfies ``pattern`` (stub-only; verified against real scenarios).

    Handles the small regex vocabulary the scenarios use (``\\s*``/``\\s+`` and escaped literals);
    the stub asserts the result actually matches, so an unsupported pattern fails loudly rather than
    silently producing a non-honoring line.
    """
    s = pattern.replace(r"\s*", "").replace(r"\s+", " ")
    s = re.sub(r"\\(.)", r"\1", s)  # unescape \X -> X
    return s


def _first_literal(pattern: str) -> str:
    """A literal matching the first alternative of ``pattern`` (drops leading inline flags)."""
    p = re.sub(r"^\(\?[a-zA-Z]+\)", "", pattern)  # strip a leading (?i)/(?is)/... flag group
    return _regex_sample(p.split("|", 1)[0])


_ABSENT_KINDS = ("code_absent", "regex_absent")


def _stub_line(pref: Preference, honor: bool) -> str | None:
    """The line a stubbed ``table.py`` emits for ``pref`` when honoring / violating it.

    Mirrors ``honors`` so the checker agrees with the stub: for an *absent* check a violation
    *emits* the forbidden token and honoring emits nothing; for a *presence* check honoring emits a
    matching token and a violation emits nothing.
    """
    check = pref.check
    if check.kind in _ABSENT_KINDS:
        if honor:
            return None
        token = check.pattern if check.kind == "code_absent" else _first_literal(check.pattern)
        return f"    .data_color(palette={token!r})  # {pref.id}"
    if not honor:
        return None
    token = check.pattern if check.kind == "code_contains" else _regex_sample(check.pattern)
    return f"    .{token if '(' in token else f'fmt({token})'}  # {pref.id}"


@dataclass
class StubGenerator:
    """Deterministic generator: honors exactly the preferences the recalled layer actually surfaced.

    A preference counts as "in the learned layer" when its ``scope`` appears in the rendered
    ``learned_layer`` — i.e. ``recall`` genuinely retrieved that entry this run. So a COLD run
    (empty layer) honors nothing → every positive check fails and every ``code_absent`` check is
    violated (a realistically wrong "before"); a WARM run honors precisely the retrieved
    preferences, and one retrieval never surfaced honestly stays un-applied. No model, no cost.
    """

    name: str = "stub"

    def generate(
        self, scenario: Scenario, learned_layer: str, workdir: Path
    ) -> GenerationResult:
        lines = [
            "import great_tables as gt",
            "import pandas as pd",
            "",
            f"df = pd.read_csv({scenario.data.split('/')[-1]!r})",
            "table = (",
            "    gt.GT(df)",
        ]
        for pref in scenario.preferences:
            honored = pref.scope in learned_layer
            emitted = _stub_line(pref, honored)
            if emitted is not None:
                lines.append(emitted)
        lines += [")", 'gt.GT.save(table, "table.png")', ""]
        code = "\n".join(lines)
        (workdir / "table.py").write_text(code, encoding="utf-8")
        return GenerationResult(code=code)


# --------------------------------------------------------------------------------------------------
# Live Agent-SDK generator (paid) — used only for the real artifact-generation run.
# --------------------------------------------------------------------------------------------------


@dataclass
class AgentGenerator:
    """Drive the live model via the Claude Agent SDK, great-tables skill mounted, to write table.py.

    Mirrors the sibling ``gtskill`` runner's SDK usage (skill mount + Read/Write/Bash tools, cwd =
    the run's workdir). Imported lazily so the stub path works without ``claude-agent-sdk``
    installed. Exercised during the real generation run (needs ``ANTHROPIC_API_KEY``); the stub
    covers CI-free verification.
    """

    skill_dir: Path
    model: str | None = None
    name: str = "agent"

    def generate(
        self, scenario: Scenario, learned_layer: str, workdir: Path
    ) -> GenerationResult:
        import anyio

        return anyio.run(self._generate, scenario, learned_layer, workdir)

    def _build_prompt(self, scenario: Scenario, learned_layer: str) -> str:
        data_name = scenario.data.split("/")[-1]
        parts = []
        if learned_layer:
            parts += [learned_layer, ""]
        parts += [
            scenario.prompt.strip(),
            "",
            f"The data is in `{data_name}` in the current directory. Write a Python script "
            "`table.py` that builds the requested table with `great_tables`, then render it to "
            "`table.png` with Great Tables' gtsave (the skill's mandatory renderer, "
            '`table.gtsave("table.png")`). Run the script to confirm it works.',
        ]
        return "\n".join(parts)

    async def _generate(
        self, scenario: Scenario, learned_layer: str, workdir: Path
    ) -> GenerationResult:
        from claude_agent_sdk import ClaudeAgentOptions, query  # lazy: only for the paid path

        # The SDK discovers *project* skills by name from the cwd's `.claude/skills/`. cwd is a temp
        # workdir, so mount the vendored skill into it and reference it by its directory name — a
        # bare filesystem path in `skills=` is not how the SDK resolves skills.
        skill_name = self.skill_dir.name
        mounted = workdir / ".claude" / "skills" / skill_name
        mounted.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self.skill_dir, mounted, dirs_exist_ok=True)

        # Restrict the capability set with `tools` (allowed_tools only auto-approves; it does not
        # limit). Confining generation to filesystem/shell tools — no WebSearch/WebFetch — keeps a
        # committed artifact run reproducible and free of external state.
        fs_tools = ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]
        options = ClaudeAgentOptions(
            skills=[skill_name],
            setting_sources=["project"],
            tools=fs_tools,
            allowed_tools=fs_tools,
            disallowed_tools=["WebSearch", "WebFetch"],
            cwd=str(workdir),
            permission_mode="default",
            model=self.model,
        )
        transcript: list = []
        prompt = self._build_prompt(scenario, learned_layer)
        async for msg in query(prompt=prompt, options=options):
            transcript.append(_message_to_dict(msg))
        table_py = workdir / "table.py"
        if not table_py.is_file():
            raise RuntimeError(f"{scenario.name}: agent did not write table.py in {workdir}")
        # The before/after artifacts require a rendered PNG. Fail loudly if the agent wrote the
        # script but it never rendered (e.g. it skipped running it, or Chrome is missing) rather
        # than silently committing an incomplete artifact set.
        if not (workdir / "table.png").is_file():
            raise RuntimeError(
                f"{scenario.name}: agent produced table.py but no rendered table.png in {workdir} "
                "(did the script run? is a headless Chrome available for gtsave?)"
            )
        return GenerationResult(code=table_py.read_text(encoding="utf-8"), transcript=transcript)


def _message_to_dict(msg: object) -> dict:
    """Best-effort JSON-able view of an Agent-SDK message for the saved transcript."""
    for attr in ("model_dump", "to_dict", "__dict__"):
        val = getattr(msg, attr, None)
        if callable(val):
            try:
                return dict(val())
            except Exception:  # pragma: no cover - defensive
                pass
        elif isinstance(val, dict):
            return {k: str(v) for k, v in val.items()}
    return {"repr": repr(msg)}  # pragma: no cover - defensive
