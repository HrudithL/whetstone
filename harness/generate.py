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
import os
import re
import shutil
import sys
import tokenize
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from . import config
from .schema import Check, Preference, Scenario
from .skills import SkillSpec, get_spec


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


def _python_for_check(code: str) -> str:
    """``code`` reduced to executable Python — comments AND docstrings gone.

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


# HTML/CSS comment forms: strip them (replacing with a space so neighbours can't merge into a false
# match) so an agent's explanatory `<!-- avoid box-shadow -->` or `/* no rounded corners */` cannot
# fool a `*_absent` check. `#` is NOT a comment in HTML/CSS (it is an id selector / hex colour), so
# unlike Python it must never be split on.
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
# Whole <script> blocks are dropped before matching: a check measures the rendered markup/CSS, not
# scripting, and JS `//` line comments (which the block/HTML comment strippers miss) must not let
# `// use #FF6B00` satisfy a presence check — or a scripted value defeat an absence check.
_SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script\s*>", re.DOTALL | re.IGNORECASE)


def _html_for_check(code: str) -> str:
    """``code`` (HTML/CSS) with ``<script>`` blocks and ``<!-- -->``/``/* */`` comments removed."""
    code = _SCRIPT_RE.sub(" ", code)
    code = _HTML_COMMENT_RE.sub(" ", code)
    return _BLOCK_COMMENT_RE.sub(" ", code)


def code_for_check(code: str, language: str = "python") -> str:
    """Normalize a primary-output artifact for checking, per its skill's ``check_language``.

    Comments (and, for Python, docstrings) are stripped so an agent's *explanatory* prose can never
    satisfy or defeat a check — only the real output does. Unknown languages pass through unchanged.
    """
    if language == "python":
        return _python_for_check(code)
    if language == "html":
        return _html_for_check(code)
    return code


def honors(code: str, check: Check, language: str = "python") -> bool:
    """Does ``code`` satisfy ``check``? The runner's one source of truth for "was it applied?".

    Runs against :func:`code_for_check` output (comments/docstrings removed per ``language``) so
    only the real output counts. ``*_absent`` kinds assert absence; the others assert presence.
    """
    src = code_for_check(code, language)
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

    Handles the small regex vocabulary the scenarios use: a leading inline-flag group (``(?i)``),
    ``\\s*``/``\\s+``, a single character *range* class (``[1-9]`` -> ``1``), and escaped literals.
    The stub asserts the result actually matches, so an unsupported pattern fails loudly rather than
    silently producing a non-honoring line.
    """
    s = re.sub(r"^\(\?[a-zA-Z]+\)", "", pattern)  # drop a leading (?i)/(?is)/... flag group
    s = s.replace(r"\s*", "").replace(r"\s+", " ")
    s = re.sub(r"\[([^\]^-])-[^\]]\]", r"\1", s)  # single range class -> its first char
    s = re.sub(r"\\(.)", r"\1", s)  # unescape \X -> X
    return s


def _first_literal(pattern: str) -> str:
    """A literal matching the first alternative of ``pattern`` (drops leading inline flags)."""
    p = re.sub(r"^\(\?[a-zA-Z]+\)", "", pattern)  # strip a leading (?i)/(?is)/... flag group
    return _regex_sample(p.split("|", 1)[0])


_ABSENT_KINDS = ("code_absent", "regex_absent")


def _stub_token(check: Check, presence: bool) -> str:
    """The literal to embed so ``check`` matches (``presence``) or is triggered (absence-violation).

    Literal patterns embed verbatim; regex patterns get a best-effort matching literal — the full
    sample for a presence check, or the first alternative for an absence-violation.
    """
    if check.kind in ("code_contains", "code_absent"):
        return check.pattern
    return _regex_sample(check.pattern) if presence else _first_literal(check.pattern)


def _stub_carrier(pref: Preference, honor: bool, language: str, n: int) -> str | None:
    """One line of stub primary-output for ``pref``, or ``None`` to emit nothing.

    Mirrors ``honors`` so the checker agrees with the stub: for an *absent* check a violation
    *emits* the forbidden token and honoring emits nothing; for a *presence* check honoring emits a
    matching token and a violation emits nothing. The token is embedded as a string literal in a
    language-appropriate carrier — a Python assignment (survives AST-unparse) or a CSS declaration —
    since the stub output is only ever *checked* (via :func:`code_for_check`), never executed.
    """
    absent = pref.check.kind in _ABSENT_KINDS
    if absent == honor:  # honoring an absent check, or violating a presence check → emit nothing
        return None
    token = _stub_token(pref.check, presence=not absent)
    if language == "python":
        return f"_pref_{n} = [{token!r}]  # {pref.id}"
    if language == "html":
        return f"  .p-{n} {{ content: {token!r}; }}"
    return token  # unknown language: bare literal is enough for a substring/regex check


def _stub_document(spec: SkillSpec, scenario: Scenario, carriers: list[str]) -> str:
    """Wrap the per-preference ``carriers`` in a minimal doc in the skill's primary language."""
    body = "\n".join(carriers)
    if spec.check_language == "html":
        return (
            "<!doctype html>\n<html><head><meta charset='utf-8'>\n<style>\n"
            f"{body}\n</style></head>\n<body><h1>stub: {scenario.name}</h1></body></html>\n"
        )
    if spec.check_language == "python":
        return f"# stub {spec.output} for {scenario.name!r} (skill {spec.name!r})\n{body}\n"
    return body + "\n"


@dataclass
class StubGenerator:
    """Deterministic generator: honors exactly the preferences the recalled layer actually surfaced.

    A preference counts as "in the learned layer" when its ``scope`` appears in the rendered
    ``learned_layer`` — i.e. ``recall`` genuinely retrieved that entry this run. So a COLD run
    (empty layer) honors nothing → every positive check fails and every ``code_absent`` check is
    violated (a realistically wrong "before"); a WARM run honors precisely the retrieved
    preferences, and one retrieval never surfaced honestly stays un-applied. No model, no cost.

    Output is the skill's primary artifact in its own language (Python ``table.py`` / ``deck.py``,
    an HTML ``index.html``); the stub does NOT produce a skill's heavy ``required_artifacts``
    (rendered PNG, real .pptx) — those need the live ``--agent`` path. A ``--stub`` run only
    verifies the seed→recall→check→iterate→write pipeline against real Whetstone.
    """

    name: str = "stub"

    def generate(
        self, scenario: Scenario, learned_layer: str, workdir: Path
    ) -> GenerationResult:
        spec = get_spec(scenario.skill)
        carriers: list[str] = []
        for n, pref in enumerate(scenario.preferences):
            honored = pref.scope in learned_layer
            line = _stub_carrier(pref, honored, spec.check_language, n)
            if line is not None:
                carriers.append(line)
        code = _stub_document(spec, scenario, carriers)
        (workdir / spec.output).write_text(code, encoding="utf-8")
        return GenerationResult(code=code)


# --------------------------------------------------------------------------------------------------
# Live Agent-SDK generator (paid) — used only for the real artifact-generation run.
# --------------------------------------------------------------------------------------------------


def _artifact_ok(path: Path) -> bool:
    """True if ``path`` is a non-empty file — and, for HTML, has non-WHITESPACE content.

    A whitespace-only ``.html`` passes a size check but renders as nothing (the triptych's
    ``native.strip()`` is falsy), so reject it here rather than commit a blank before/after panel.
    """
    if not (path.is_file() and path.stat().st_size > 0):
        return False
    if path.suffix.lower() in (".html", ".htm"):
        return bool(path.read_text(encoding="utf-8", errors="ignore").strip())
    return True


# Fetch-on-load remote references. A self-contained showcase artifact must inline everything, so a
# committed run stays reproducible/offline and the docs iframe never fetches external state (the
# prompt already says "no external assets, no CDN"). Targets resources that load automatically —
# `src=`, a `<link>` stylesheet/font/icon href, CSS `url(...)`, `@import` — NOT a navigational
# `<a href="https://...">`, which does not fetch on load.
_REMOTE_REF_RE = re.compile(
    r"""(?xi)
      (?: \b src \s*=\s* ["']? (?:https?:)?// )
    | (?: < link \b [^>]*? \b href \s*=\s* ["']? (?:https?:)?// )
    | (?: \b url \( \s* ["']? (?:https?:)?// )
    | (?: @import \s+ (?: url \( \s* )? ["']? (?:https?:)?// )
    """
)


def _html_remote_refs(html: str) -> list[str]:
    """Snippets of any fetch-on-load remote reference in ``html`` (empty list if self-contained)."""
    return [m.group(0)[:60] for m in _REMOTE_REF_RE.finditer(html)]


@dataclass
class AgentGenerator:
    """Drive the live model via the Claude Agent SDK, the scenario's skill mounted, to produce that
    skill's primary artifact.

    One generator serves every skill: the skill dir (``harness/skill/<skill>/``), the generation
    prompt, and the ``required_artifacts`` all come from the scenario's
    :class:`~harness.skills.SkillSpec`. Mirrors the sibling ``gtskill`` runner's SDK usage (skill
    mount + Read/Write/Bash tools, cwd = the run's workdir). Imported lazily so the stub path works
    without ``claude-agent-sdk`` installed. Exercised during the real generation run (needs
    ``ANTHROPIC_API_KEY``); the stub covers CI-free verification.
    """

    model: str | None = None
    name: str = "agent"

    def generate(
        self, scenario: Scenario, learned_layer: str, workdir: Path
    ) -> GenerationResult:
        import anyio

        spec = get_spec(scenario.skill)
        skill_dir = config.HARNESS_ROOT / "skill" / spec.name
        if not skill_dir.is_dir():
            raise FileNotFoundError(
                f"{scenario.name}: skill dir for {spec.name!r} not found: {skill_dir}"
            )
        return anyio.run(self._generate, scenario, spec, skill_dir, learned_layer, workdir)

    def _build_prompt(self, scenario: Scenario, spec: SkillSpec, learned_layer: str) -> str:
        data_name = scenario.data.split("/")[-1]
        parts = []
        if learned_layer:
            parts += [learned_layer, ""]
        # `.replace`, not `.format`: a skill's prompt_tail may contain literal `{`/`}` (CSS, code
        # snippets) that `str.format` would choke on; only the `{data}` token needs substituting.
        parts += [scenario.prompt.strip(), "", spec.prompt_tail.replace("{data}", data_name)]
        return "\n".join(parts)

    async def _generate(
        self,
        scenario: Scenario,
        spec: SkillSpec,
        skill_dir: Path,
        learned_layer: str,
        workdir: Path,
    ) -> GenerationResult:
        # lazy import: only the paid path needs the SDK
        from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

        # The SDK discovers *project* skills by name from the cwd's `.claude/skills/`. cwd is a temp
        # workdir, so mount the vendored skill into it and reference it by its directory name — a
        # bare filesystem path in `skills=` is not how the SDK resolves skills.
        skill_name = skill_dir.name
        mounted = workdir / ".claude" / "skills" / skill_name
        mounted.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(skill_dir, mounted, dirs_exist_ok=True)

        # Restrict the capability set with `tools` (allowed_tools only auto-approves; it does not
        # limit). Confining generation to filesystem/shell tools — no WebSearch/WebFetch — keeps a
        # committed artifact run reproducible and free of external state. `Skill` MUST stay in the
        # base `tools` list: `skills=[...]` only appends Skill(name) to the auto-approve set, so
        # dropping Skill from `tools` would make the mounted skill uninvokable.
        fs_tools = ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Skill"]
        # Auto-approve everything except Bash; Bash is gated by `can_use_tool` so a bare shell can't
        # `curl`/`pip install` around the WebSearch/WebFetch denial. (An unscoped `Bash` in
        # allowed_tools would auto-approve the whole tool.)
        auto_approve = [t for t in fs_tools if t != "Bash"]
        # The agent runs any generated script (e.g. `table.py`, `deck.py`) via its Bash tool. The
        # skills' render deps (`great_tables`/`nokap`, `python-pptx`, ...) live only in *this*
        # venv: the parent is launched as `.venv/bin/python`, which does NOT put `.venv/bin` on
        # PATH, so a bare `python3 script.py` would otherwise resolve to a system interpreter that
        # lacks them. Hand the subprocess an env with this venv's bin dir first on PATH so
        # `python`/`python3` deterministically import the showcase dependencies.
        child_env = config.subprocess_env()
        venv_bin = os.path.dirname(sys.executable)
        child_env["PATH"] = venv_bin + os.pathsep + child_env.get("PATH", "")
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
            env=child_env,
            # Each CLI->SDK message is one JSON line; the default 1 MiB cap overflows when a single
            # tool result carries a large payload (e.g. reading sp500.csv, ~918 KB, or emitting the
            # table's raw HTML). Raise it so a whole-file Read or HTML dump stays in one message.
            max_buffer_size=32 * 1024 * 1024,
        )
        transcript: list = []
        prompt = self._build_prompt(scenario, spec, learned_layer)

        # Setting `can_use_tool` requires the SDK's *bidirectional* streaming session: the
        # permission callback is served over a control channel that must stay open for the whole
        # run. A plain `query(prompt=str)` refuses ("callback requires streaming mode"), and
        # `query()` with a finite async-iterable prompt is worse — it closes stdin after the first
        # turn, tearing that control channel down, so every later tool call needing a verdict fails
        # with "AbortError: Stream closed" and the agent can never run its script (no artifacts).
        # `ClaudeSDKClient` holds the session open for the duration; `receive_response()` yields
        # until (and including) the terminating ResultMessage.
        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)
            async for msg in client.receive_response():
                transcript.append(_message_to_dict(msg))
        # The primary output must exist and be non-empty; when it IS the rendered artifact (a web
        # skill's index.html) require non-WHITESPACE content too — a whitespace-only file passes a
        # size check but renders as nothing and there are no required_artifacts to catch it later.
        primary = workdir / spec.output
        if not _artifact_ok(primary):
            raise RuntimeError(
                f"{scenario.name}: agent did not write a non-empty {spec.output} in {workdir}"
            )
        # Every declared render artifact must exist and be non-empty (the before/after proof), same
        # non-whitespace rule for HTML. Fail loudly, not silently commit an incomplete set.
        for artifact in spec.required_artifacts:
            if not _artifact_ok(workdir / artifact):
                raise RuntimeError(
                    f"{scenario.name}: agent wrote {spec.output} but no non-empty {artifact} in "
                    f"{workdir} (did the generated script run and produce it?)"
                )
        primary_text = primary.read_text(encoding="utf-8")
        # A self-contained showcase artifact must inline everything (the prompt says "no external
        # assets, no CDN"): reject an HTML output that fetches remote resources, so committed runs
        # stay reproducible/offline and the docs iframe never reaches the network.
        if spec.output.lower().endswith((".html", ".htm")):
            remote = _html_remote_refs(primary_text)
            if remote:
                raise RuntimeError(
                    f"{scenario.name}: {spec.output} references remote resources (must be "
                    f"self-contained): {remote[:3]}"
                )
        return GenerationResult(code=primary_text, transcript=transcript)


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
