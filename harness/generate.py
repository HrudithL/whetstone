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


# Shell tokens that reach the network or install packages — denied so a committed artifact run is
# reproducible and offline. Local inspection and running `table.py` (python ...) stay allowed.
_NETWORK_BASH_TOKENS = (
    "curl", "wget", "nc ", "ncat", "ssh", "scp", "sftp", "telnet",
    "pip install", "pip3 install", "pip download", "uv pip", "conda install",
    "npm ", "npx ", "pnpm", "yarn", "apt", "apt-get", "brew ", "gem install",
    "git clone", "git pull", "git fetch", "git remote",
)


def bash_command_is_networked(command: str) -> bool:
    """True if a Bash ``command`` looks like it fetches remote state or installs packages.

    Whitespace is collapsed first so ``pip  install`` / ``git   clone`` (Bash treats runs of
    whitespace as one separator) can't slip past the space-bearing tokens.
    """
    low = re.sub(r"\s+", " ", command.lower())
    return any(tok in low for tok in _NETWORK_BASH_TOKENS)


async def _deny_networked_bash(tool_name, tool_input, _ctx):  # noqa: ANN001 - SDK callback shape
    """``can_use_tool`` callback: deny network/install Bash, allow everything else.

    Bash is not auto-approved (it is kept out of ``allowed_tools``), so this gate runs for every
    shell command. WebSearch/WebFetch are already disallowed at the tool level; this closes the
    shell escape hatch (``curl``/``pip install``/...) that would otherwise make generation depend on
    external state.
    """
    from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

    if tool_name == "Bash":
        command = (tool_input or {}).get("command", "") or ""
        if bash_command_is_networked(command):
            return PermissionResultDeny(
                message="network/install shell commands are disabled for reproducible generation"
            )
    return PermissionResultAllow()


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
        lines += [")", 'table.gtsave("table.png")', ""]
        code = "\n".join(lines)
        (workdir / "table.py").write_text(code, encoding="utf-8")
        # A minimal, self-contained HTML table so the triptych can render a stub run natively too.
        applied = [p.id for p in scenario.preferences if p.scope in learned_layer]
        rows = "".join(f"<li>{pid}</li>" for pid in applied) or "<li>(none)</li>"
        html = (
            f"<table class='gt_table'><thead><tr><th>{scenario.name} (stub)</th></tr></thead>"
            f"<tbody><tr><td>preferences applied:<ul>{rows}</ul></td></tr></tbody></table>"
        )
        (workdir / "table.html").write_text(html, encoding="utf-8")
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
            '`table.gtsave("table.png")`). Also write the table\'s self-contained HTML to '
            '`table.html` via `<your GT object>.as_raw_html()` so it can be embedded natively. '
            "Run the script to confirm it works.",
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
        # committed artifact run reproducible and free of external state. `Skill` MUST stay in the
        # base `tools` list: `skills=[...]` only appends Skill(name) to the auto-approve set, so
        # dropping Skill from `tools` would make the mounted great-tables skill uninvokable.
        fs_tools = ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Skill"]
        # Auto-approve everything except Bash; Bash is gated by `can_use_tool` so a bare shell can't
        # `curl`/`pip install` around the WebSearch/WebFetch denial. (An unscoped `Bash` in
        # allowed_tools would auto-approve the whole tool.)
        auto_approve = [t for t in fs_tools if t != "Bash"]
        options = ClaudeAgentOptions(
            skills=[skill_name],
            setting_sources=["project"],
            tools=fs_tools,
            allowed_tools=auto_approve,
            disallowed_tools=["WebSearch", "WebFetch"],
            can_use_tool=_deny_networked_bash,
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
        # The before/after artifacts require BOTH a rendered PNG and the native HTML (the triptych's
        # native-table proof). Fail loudly if either is missing rather than silently committing an
        # incomplete set / degrading to a screenshot.
        for artifact, hint in (
            ("table.png", "did the script run? is a headless Chrome available for gtsave?"),
            ("table.html", "did the script write <GT>.as_raw_html() to table.html?"),
        ):
            f = workdir / artifact
            # Require a non-empty artifact. For table.html require non-WHITESPACE content too: a
            # whitespace-only file passes a size check but the triptych ignores it (native.strip()
            # is falsy) and silently falls back to the PNG screenshot.
            ok = f.is_file() and f.stat().st_size > 0
            if ok and artifact.endswith(".html"):
                ok = bool(f.read_text(encoding="utf-8", errors="ignore").strip())
            if not ok:
                raise RuntimeError(
                    f"{scenario.name}: agent produced table.py but no non-empty {artifact} in "
                    f"{workdir} ({hint})"
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
