#!/usr/bin/env python3
"""Check governance rules for new or modified ``deprecate_parameter`` decorators.

Compare ``HEAD`` with the merge base of ``--base-ref``. A
``deprecate_parameter(...)`` call is checked when it is new or its arguments
changed. An identical call in the base version of the same file is left alone,
including when Git reports that file as a rename or a copy.

Recognized calls are direct decorators (``@deprecate_parameter(...)``),
assignment aliases (``alias = deprecate_parameter(...)``), and immediate
wrappers (``deprecate_parameter(...)(func)``).

Rules that this repository does not spell out mechanically:

- Match a call whose name or attribute is ``deprecate_parameter``. Import
  aliases of that name are not resolved.
- ``start_version`` must normalize to the major.minor prefix of the first
  module-level ``__version__`` string in ``src/skimage/__init__.py`` at HEAD
  (``0.27.0rc2.dev0`` -> ``0.27``). Literal ``X.Y`` and ``X.Y.0`` both normalize
  to ``X.Y``. Any other literal, and any dynamic value, is rejected.
- ``stop_version`` is normalized the same way and must match a ``Version X.Y``
  heading in ``TODO.txt`` at HEAD. That section must contain the parameter
  name in backticks.
- The deprecated name must be a string literal. Other arguments, such as
  ``template``, may be dynamic.
- Blobs come from Git, not the uncommitted worktree. Only changed ``*.py`` files
  under ``src/skimage/`` and ``src/_skimage2/`` are inspected. Fixtures under
  ``tests/``, tooling under ``acme/``, and other trees are ignored.
- Copy pairing uses Git's similarity check (``--find-copies --find-copies-harder``).
  A new module that Git does not pair with a source is treated as an addition,
  and its calls are checked as new. A copy or rename into production from
  outside ``src/skimage/`` and ``src/_skimage2/`` is also treated as an
  addition, so historical fixtures cannot be grandfathered by moving them.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

VERSION_PATH = "src/skimage/__init__.py"
TODO_PATH = "TODO.txt"
_DECORATOR = "deprecate_parameter"
_PRODUCTION_PREFIXES = ("src/skimage/", "src/_skimage2/")
_VERSION_HEADING = re.compile(r"^Version (\d+\.\d+)\s*$")
_UNDERLINE = re.compile(r"-{3,}\s*$")
_MAJOR_MINOR = re.compile(r"^(\d+)\.(\d+)")
_VERSION_LITERAL = re.compile(r"^(\d+)\.(\d+)(?:\.0)?$")


class InspectionError(Exception):
    """Git output or a repository blob could not be inspected."""


@dataclass(frozen=True)
class DecoratorFact:
    """One ``deprecate_parameter(...)`` decorator call."""

    line: int
    parameter: str | None
    start_version: str | None
    stop_version: str | None
    problems: tuple[str, ...]
    fingerprint: str


def main(argv: list[str] | None = None) -> int:
    """Return 0 on success and 1 when governance or Git inspection fails."""
    parser = argparse.ArgumentParser(
        description=(
            "Validate deprecate_parameter decorators introduced or modified "
            "between the merge base of a Git ref and HEAD."
        )
    )
    parser.add_argument(
        "--base-ref",
        required=True,
        help="Git ref used to compute the merge base against HEAD.",
    )
    args = parser.parse_args(argv)
    code, diagnostics = check_repository(Path.cwd(), args.base_ref)
    if diagnostics:
        print("\n".join(diagnostics))
    print(
        "deprecation governance check passed"
        if code == 0
        else "deprecation governance check failed"
    )
    return code


def check_repository(cwd: Path, base_ref: str) -> tuple[int, list[str]]:
    """Return an exit code and diagnostics for one repository."""
    try:
        root = _repository_root(cwd)
        merge_base = (
            _stdout(
                root,
                ["merge-base", "--", base_ref, "HEAD"],
                f"compute the merge base of {base_ref!r} and HEAD",
            )
            .decode()
            .strip()
        )
        current = major_minor_version(_blob(root, "HEAD", VERSION_PATH))
        if current is None:
            raise InspectionError(
                "unable to inspect diff: "
                f"{VERSION_PATH} has no module-level __version__ string "
                "beginning with major.minor"
            )
        sections = todo_sections(_blob(root, "HEAD", TODO_PATH))
        diagnostics: list[str] = []
        for head_path, base_path in _changed_python_files(root, merge_base):
            diagnostics.extend(
                _check_file(root, merge_base, head_path, base_path, current, sections)
            )
    except InspectionError as exc:
        return 1, [str(exc)]
    return (1, diagnostics) if diagnostics else (0, [])


def major_minor_version(source: str) -> str | None:
    """Return the ``major.minor`` prefix of the first ``__version__`` assignment."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        names = [target.id for target in node.targets if isinstance(target, ast.Name)]
        if "__version__" not in names:
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            match = _MAJOR_MINOR.match(node.value.value)
            if match is None:
                return None
            return f"{match.group(1)}.{match.group(2)}"
        return None
    return None


def todo_sections(source: str) -> dict[str, str]:
    """Map ``X.Y`` to the body under a ``Version X.Y`` heading."""
    lines = source.splitlines()
    sections: dict[str, list[str]] = {}
    index = 0
    while index < len(lines):
        heading = _VERSION_HEADING.match(lines[index])
        if heading is None or not _underlined(lines, index):
            index += 1
            continue
        version = heading.group(1)
        index += 2
        body: list[str] = []
        while index < len(lines) and not _underlined(lines, index):
            body.append(lines[index])
            index += 1
        sections.setdefault(version, []).append("\n".join(body))
    return {version: "\n".join(parts) for version, parts in sections.items()}


def extract_decorators(source: str) -> list[DecoratorFact]:
    """Return every ``deprecate_parameter(...)`` call.

    Direct decorators, ``alias = deprecate_parameter(...)``, and
    ``deprecate_parameter(...)(func)`` are the same kind of call. Each call is
    recorded once, at the call itself.
    """
    facts: list[DecoratorFact] = []
    for node in ast.walk(ast.parse(source)):
        call = _deprecate_call(node)
        if call is not None:
            facts.append(_fact(call))
    facts.sort(key=lambda fact: fact.line)
    return facts


def new_or_modified(
    base_source: str,
    head_source: str,
    base: list[DecoratorFact],
    head: list[DecoratorFact],
) -> list[DecoratorFact]:
    """Return head calls that are not the same AST call as a base call.

    Pairing follows the text diff, not names or the first identical AST.
    An unchanged call still matches after a function, method, or alias rename,
    and after its line number shifts. A call is new when its line was inserted,
    or when its arguments changed. Identical decorators on same-named functions,
    stacked decorators, and methods of different classes stay separate because
    only unchanged lines that still belong to the same def or class are paired.
    """
    base_lines = base_source.splitlines()
    head_lines = head_source.splitlines()
    equal_map, head_kind, replaces = _line_alignment(base_lines, head_lines)
    matched_base: set[int] = set()
    matched_head: set[int] = set()
    head_by_line = {fact.line: index for index, fact in enumerate(head)}

    for base_index, base_fact in enumerate(base):
        head_line = equal_map.get(base_fact.line)
        if head_line is None:
            continue
        head_index = head_by_line.get(head_line)
        if head_index is None:
            continue
        if head[head_index].fingerprint != base_fact.fingerprint:
            continue
        # A copied decorator line can sit on a new function while the original
        # function's decorator was edited. Require the same def or class.
        # Calls inside a function body are not decorators of the next def.
        if _is_decorator_line(base_lines, base_fact.line) or _is_decorator_line(
            head_lines, head_line
        ):
            if not _statements_correspond(
                base_fact.line,
                head_line,
                base_lines,
                head_lines,
                equal_map,
                replaces,
            ):
                continue
        matched_base.add(base_index)
        matched_head.add(head_index)

    # In-place edits that keep the call AST (an alias rename on the same line)
    # are not insertions. Pair those leftovers one-for-one, in order.
    leftover_base: dict[str, list[int]] = {}
    for base_index, base_fact in enumerate(base):
        if base_index not in matched_base:
            leftover_base.setdefault(base_fact.fingerprint, []).append(base_index)

    introduced: list[DecoratorFact] = []
    for head_index, head_fact in enumerate(head):
        if head_index in matched_head:
            continue
        if head_kind.get(head_fact.line) == "replace":
            bucket = leftover_base.get(head_fact.fingerprint)
            if bucket:
                bucket.pop(0)
                continue
        introduced.append(head_fact)
    return introduced


def _line_alignment(
    base_lines: list[str], head_lines: list[str]
) -> tuple[dict[int, int], dict[int, str], list[tuple[int, int, int, int]]]:
    """Map unchanged base lines to head lines, and classify each head line.

    Replace hunks are ``(base_start, base_end, head_start, head_end)``, inclusive.
    """
    matcher = difflib.SequenceMatcher(a=base_lines, b=head_lines, autojunk=False)
    equal_map: dict[int, int] = {}
    head_kind: dict[int, str] = {}
    replaces: list[tuple[int, int, int, int]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                equal_map[i1 + 1 + offset] = j1 + 1 + offset
                head_kind[j1 + 1 + offset] = "equal"
        elif tag == "insert":
            for line in range(j1 + 1, j2 + 1):
                head_kind[line] = "insert"
        elif tag == "replace":
            for line in range(j1 + 1, j2 + 1):
                head_kind[line] = "replace"
            if i2 > i1 and j2 > j1:
                replaces.append((i1 + 1, i2, j1 + 1, j2))
    return equal_map, head_kind, replaces


def _statements_correspond(
    base_line: int,
    head_line: int,
    base_lines: list[str],
    head_lines: list[str],
    equal_map: dict[int, int],
    replaces: list[tuple[int, int, int, int]],
) -> bool:
    """True when both calls decorate the same surviving def or class."""
    base_stmt = _statement_line(base_lines, base_line)
    head_stmt = _statement_line(head_lines, head_line)
    if base_stmt is None and head_stmt is None:
        return True
    if base_stmt is None or head_stmt is None:
        return False
    if equal_map.get(base_stmt) == head_stmt:
        return True
    return any(
        start_base <= base_stmt <= end_base and start_head <= head_stmt <= end_head
        for start_base, end_base, start_head, end_head in replaces
    )


def _is_decorator_line(lines: list[str], line: int) -> bool:
    return lines[line - 1].lstrip().startswith("@")


def _statement_line(lines: list[str], after_line: int) -> int | None:
    """Return the next ``def`` or ``class`` line after a 1-based call line."""
    for index in range(after_line, len(lines)):
        text = lines[index].lstrip()
        if text.startswith(("def ", "class ", "async def ")):
            return index + 1
    return None


def validate_decorator(
    path: str,
    fact: DecoratorFact,
    current: str,
    sections: dict[str, str],
) -> list[str]:
    """Return diagnostics for one new or modified decorator."""

    def report(reason: str) -> str:
        shown = "<unknown>" if fact.parameter is None else repr(fact.parameter)
        return f"{path}:{fact.line}: parameter {shown}: {reason}"

    if fact.problems:
        return [report(problem) for problem in fact.problems]

    diagnostics: list[str] = []
    if fact.start_version != current:
        diagnostics.append(
            report(
                f"start_version {fact.start_version!r} does not match the repository "
                f"version {current} declared in {VERSION_PATH}"
            )
        )
    section = sections.get(fact.stop_version or "")
    if section is None:
        diagnostics.append(
            report(
                f"stop_version {fact.stop_version!r} has no matching "
                f"'Version {fact.stop_version}' section in {TODO_PATH}"
            )
        )
    elif f"`{fact.parameter}`" not in section:
        diagnostics.append(
            report(
                f"{TODO_PATH} section 'Version {fact.stop_version}' does not "
                f"mention `{fact.parameter}` in backticks"
            )
        )
    return diagnostics


def _check_file(
    root: Path,
    merge_base: str,
    head_path: str,
    base_path: str | None,
    current: str,
    sections: dict[str, str],
) -> list[str]:
    head_source = _blob(root, "HEAD", head_path)
    base_source = "" if base_path is None else _blob(root, merge_base, base_path)
    try:
        base_facts = extract_decorators(base_source)
    except SyntaxError as exc:
        return [
            _parse_diagnostic(
                base_path or head_path,
                exc,
                "unable to parse the base version of the file",
            )
        ]
    try:
        head_facts = extract_decorators(head_source)
    except SyntaxError as exc:
        return [_parse_diagnostic(head_path, exc, "unable to parse Python file")]

    diagnostics: list[str] = []
    for fact in new_or_modified(base_source, head_source, base_facts, head_facts):
        diagnostics.extend(validate_decorator(head_path, fact, current, sections))
    return diagnostics


def _fact(call: ast.Call) -> DecoratorFact:
    problems: list[str] = []
    if any(isinstance(arg, ast.Starred) for arg in call.args):
        problems.append(
            "starred positional arguments are unsupported; "
            "pass the deprecated parameter name as a string literal"
        )
    if any(keyword.arg is None for keyword in call.keywords):
        problems.append(
            "starred keyword arguments are unsupported; "
            "pass start_version and stop_version as string literals"
        )

    keywords = {keyword.arg: keyword.value for keyword in call.keywords if keyword.arg}
    positional = [arg for arg in call.args if not isinstance(arg, ast.Starred)]
    parameter = _parameter(keywords, positional, problems)
    return DecoratorFact(
        line=call.lineno,
        parameter=parameter,
        start_version=_required_version(keywords, "start_version", problems),
        stop_version=_required_version(keywords, "stop_version", problems),
        problems=tuple(problems),
        fingerprint=ast.dump(call, include_attributes=False),
    )


def _parameter(
    keywords: dict[str, ast.expr],
    positional: list[ast.expr],
    problems: list[str],
) -> str | None:
    if "deprecated_name" in keywords and positional:
        problems.append(
            "deprecated parameter name is passed both positionally and as deprecated_name"
        )
        return None
    node = keywords.get("deprecated_name")
    if node is None and positional:
        node = positional[0]
        if len(positional) > 1:
            problems.append(
                "only the deprecated parameter name may be positional; "
                "start_version and stop_version must be keyword string literals"
            )
    if node is None:
        problems.append("missing deprecated parameter name; expected a string literal")
        return None
    value = _string_literal(node)
    if value is None:
        problems.append(
            "deprecated parameter name is unsupported or dynamically computed; "
            "expected a string literal"
        )
    return value


def _required_version(
    keywords: dict[str, ast.expr], field: str, problems: list[str]
) -> str | None:
    if field not in keywords:
        problems.append(f"missing {field}; expected a keyword string literal")
        return None
    raw = _string_literal(keywords[field])
    if raw is None:
        problems.append(
            f"{field} is unsupported or dynamically computed; expected a string literal"
        )
        return None
    normalized = _normalize_version(raw)
    if normalized is None:
        problems.append(
            f"{field} {raw!r} is not a supported version literal; "
            "expected 'X.Y' or 'X.Y.0'"
        )
        return None
    return normalized


def _normalize_version(value: str) -> str | None:
    """Return ``major.minor`` for ``X.Y`` or ``X.Y.0``."""
    match = _VERSION_LITERAL.fullmatch(value)
    if match is None:
        return None
    return f"{match.group(1)}.{match.group(2)}"


def _string_literal(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _deprecate_call(decorator: ast.AST) -> ast.Call | None:
    if not isinstance(decorator, ast.Call):
        return None
    func = decorator.func
    if isinstance(func, ast.Name) and func.id == _DECORATOR:
        return decorator
    if isinstance(func, ast.Attribute) and func.attr == _DECORATOR:
        return decorator
    return None


def _parse_diagnostic(path: str, exc: SyntaxError, reason: str) -> str:
    return f"{path}:{exc.lineno or 1}: parameter <unknown>: {reason} ({exc.msg})"


def _underlined(lines: list[str], index: int) -> bool:
    return (
        bool(lines[index].strip())
        and index + 1 < len(lines)
        and _UNDERLINE.match(lines[index + 1]) is not None
    )


def _is_production_python(path: str) -> bool:
    return path.endswith(".py") and path.startswith(_PRODUCTION_PREFIXES)


def _changed_python_files(root: Path, merge_base: str) -> list[tuple[str, str | None]]:
    """Return ``(head path, base path)`` for changed production Python files.

    Only ``src/skimage/`` and ``src/_skimage2/`` are scanned. Added files have
    no base path. Renames and copies that stay inside production keep the old
    path so an unchanged call is not treated as new. A production destination
    whose Git source is outside those trees has no base path: its calls are
    new. ``--find-copies-harder`` lets Git use an unmodified file as the copy
    source. A new file Git does not pair stays an addition: similarity below
    Git's default threshold has no reliable source, and this checker does not
    guess one.
    """
    raw = _stdout(
        root,
        [
            "diff",
            "-z",
            "--name-status",
            "--find-renames",
            "--find-copies",
            "--find-copies-harder",
            merge_base,
            "HEAD",
        ],
        "list files changed since the merge base",
    )
    parts = raw.split(b"\0")
    if parts and parts[-1] == b"":
        parts.pop()

    pairs: list[tuple[str, str | None]] = []
    index = 0
    while index < len(parts):
        code = _decode_diff(parts[index])[:1]
        index += 1
        if code in {"R", "C"}:
            if index + 1 >= len(parts):
                raise InspectionError(
                    "unable to inspect diff: rename record in git diff is incomplete"
                )
            old_path = _decode_diff(parts[index])
            new_path = _decode_diff(parts[index + 1])
            index += 2
            if _is_production_python(new_path):
                base_path = old_path if _is_production_python(old_path) else None
                pairs.append((new_path, base_path))
            continue
        if index >= len(parts):
            raise InspectionError(
                "unable to inspect diff: git diff name-status record is incomplete"
            )
        path = _decode_diff(parts[index])
        index += 1
        if code == "D" or not _is_production_python(path):
            continue
        pairs.append((path, None if code == "A" else path))
    return pairs


def _repository_root(cwd: Path) -> Path:
    output = _stdout(cwd, ["rev-parse", "--show-toplevel"], "locate the git repository")
    return Path(output.decode().strip())


def _blob(root: Path, rev: str, path: str) -> str:
    raw = _stdout(root, ["show", f"{rev}:{path}"], f"read {path} at {rev}")
    try:
        return raw.decode("utf-8")
    except UnicodeError as exc:
        raise InspectionError(
            f"unable to inspect diff: {path!r} at {rev} is not valid UTF-8 ({exc})"
        ) from exc


def _stdout(cwd: Path, args: list[str], action: str) -> bytes:
    completed = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, check=False
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode(errors="replace").strip()
        suffix = f": {detail}" if detail else ""
        raise InspectionError(f"unable to inspect diff: cannot {action}{suffix}")
    return completed.stdout


def _decode_diff(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeError as exc:
        raise InspectionError(
            f"unable to inspect diff: diff output is not valid UTF-8 ({exc})"
        ) from exc


if __name__ == "__main__":
    sys.exit(main())
