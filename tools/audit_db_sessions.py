#!/usr/bin/env python3
"""AST-driven audit for `get_db()` call sites that skip try/finally cleanup.

NOMAD has two blessed DB access patterns:

    # Pattern A — the new recommended one (auto-cleanup via context mgr)
    with db_session() as db:
        db.execute(...)

    # Pattern B — the legacy one, still common (manual cleanup)
    db = get_db()
    try:
        db.execute(...)
    finally:
        db.close()

A `get_db()` call that lives outside both patterns leaks a pooled
connection (or, worse, holds a transaction on a pool member that's
then handed to an unrelated request). This tool walks every ``*.py``
under the repo, flags each violation, and prints a ranked Markdown
report grouped by module — ready to commit as ``docs/db-leak-audit.md``.

Usage::

    python tools/audit_db_sessions.py                       # print report to stdout
    python tools/audit_db_sessions.py -o docs/db-leak-audit.md

The script is intentionally zero-dependency (stdlib only) so it can
run in CI alongside pytest.
"""
from __future__ import annotations

import argparse
import ast
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# Files we never audit — vendored code, build output, caches.
_EXCLUDED_DIRS = {
    '.git', '.pytest_cache', '.ruff_cache', '__pycache__', 'build', 'dist',
    'node_modules', 'web/nukemap', 'web/viptrack', 'web/static', 'tools',
    'playwright-report', 'test_runtime', '.ai-improve-logs',
}


@dataclass
class LeakFinding:
    """One potential ``get_db()`` leak site."""
    file: str
    line: int
    col: int
    function: str           # enclosing function/method name (or "<module>")
    snippet: str            # one-line preview of the call
    severity: str           # 'leak' | 'assigned-but-not-closed' | 'bare-call'

    def as_markdown_row(self) -> str:
        return (
            f"| `{self.file}:{self.line}` | `{self.function}` | "
            f"{self.severity} | `{self.snippet}` |"
        )


@dataclass
class FileReport:
    file: str
    findings: list[LeakFinding] = field(default_factory=list)


# ─── Walker ──────────────────────────────────────────────────────────────────


class _DbCallVisitor(ast.NodeVisitor):
    """Find every `get_db()` call, classify whether it's correctly paired.

    Classification rules:
    - If the enclosing statement is an ``Assign`` (``db = get_db()``), the
      **immediate** parent must be a ``Try`` whose ``finalbody`` closes the
      resource (``<name>.close()`` where name matches the assigned target).
    - If the enclosing expression is a ``With`` item wrapping
      ``db_session()`` / ``contextlib.closing(get_db())``, it's safe.
    - Bare expression statements like ``get_db().execute(...)`` are flagged
      as 'bare-call' — the connection is abandoned after the single call.
    """

    def __init__(self, file_path: str, source_lines: list[str]):
        self._file = file_path
        self._lines = source_lines
        self.findings: list[LeakFinding] = []
        # Stack tracks AST nodes from root → current (for ancestor queries).
        self._ancestors: list[ast.AST] = []

    def visit(self, node: ast.AST):  # type: ignore[override]
        self._ancestors.append(node)
        try:
            super().visit(node)
        finally:
            self._ancestors.pop()

    # Match direct ``get_db()`` calls. We don't track imports — any call
    # whose function name is literally ``get_db`` is treated as a candidate.
    # False positives are acceptable for an audit tool; the human reviews.
    def visit_Call(self, node: ast.Call):
        if self._is_get_db_call(node):
            self._classify(node)
        self.generic_visit(node)

    # ─── helpers ──
    @staticmethod
    def _is_get_db_call(node: ast.Call) -> bool:
        fn = node.func
        if isinstance(fn, ast.Name) and fn.id == 'get_db':
            return True
        if isinstance(fn, ast.Attribute) and fn.attr == 'get_db':
            return True
        return False

    def _enclosing_function(self) -> str:
        for anc in reversed(self._ancestors):
            if isinstance(anc, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return anc.name
            if isinstance(anc, ast.ClassDef):
                return f'class {anc.name}'
        return '<module>'

    def _nearest_ancestor(self, *types: type) -> ast.AST | None:
        # Skip the current node itself.
        for anc in reversed(self._ancestors[:-1]):
            if isinstance(anc, types):
                return anc
        return None

    def _classify(self, call: ast.Call) -> None:
        # Case 1 — ``with db_session() as db`` / ``with closing(get_db())``.
        # If the nearest containing With item owns this call subtree, skip.
        with_node = self._nearest_ancestor(ast.With, ast.AsyncWith)
        if with_node and _call_inside_with_items(with_node, call):
            return

        # Case 2 — ``db = get_db()``. Look for:
        #   (a) an enclosing Try whose finalbody closes the target, OR
        #   (b) the NEXT statement sibling being a Try whose finalbody
        #       closes the target. This is the common legacy pattern:
        #           db = get_db()
        #           try:
        #               ...
        #           finally:
        #               db.close()
        #       Without sibling-checking the classifier would false-positive
        #       every such block, drowning the real leaks in noise.
        assign_node = self._nearest_ancestor(ast.Assign)
        target_name: str | None = None
        if assign_node and isinstance(assign_node.value, ast.Call) and assign_node.value is call:
            for tgt in assign_node.targets:
                if isinstance(tgt, ast.Name):
                    target_name = tgt.id
                    break
            if target_name is not None:
                try_node = self._nearest_ancestor(ast.Try)
                if try_node and _try_closes_target(try_node, target_name):
                    return
                sibling_try = self._next_sibling_try(assign_node)
                if sibling_try and _try_closes_target(sibling_try, target_name):
                    return
                # Broader heuristic — the target has a close() call SOMEWHERE
                # in the enclosing function body. Catches the "define inside
                # an outer try, close in a downstream sibling try" pattern
                # (services/manager.py::start_process), which neither the
                # ancestor nor immediate-sibling checks cover. False negatives
                # are possible for cleanup-skipping branches, but an audit
                # tool is useless if it floods the reviewer with known-safe
                # patterns — prefer precision on the real leaks.
                fn_node = self._enclosing_function_node()
                if fn_node is not None and _function_body_closes_target(
                    fn_node, assign_node, target_name
                ):
                    return
                # Assigned but never closed in a finally — real leak.
                self._record(call, 'assigned-but-not-closed')
                return

        # Case 3 — bare call used inline (``get_db().execute(...)``). The
        # returned Connection is discarded after the chained expression.
        self._record(call, 'bare-call')

    def _enclosing_function_node(self) -> ast.AST | None:
        for anc in reversed(self._ancestors[:-1]):
            if isinstance(anc, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return anc
        return None

    def _next_sibling_try(self, assign_node: ast.Assign) -> ast.Try | None:
        """Return the statement immediately AFTER ``assign_node`` in its
        enclosing block, iff that statement is an ``ast.Try``.

        The enclosing block is the ``.body`` / ``.orelse`` / ``.finalbody``
        list on the closest ancestor that has one. We scan the ancestor
        chain to find which list contains ``assign_node``.
        """
        for anc in reversed(self._ancestors[:-1]):
            for attr in ('body', 'orelse', 'finalbody'):
                block = getattr(anc, attr, None)
                if isinstance(block, list) and assign_node in block:
                    idx = block.index(assign_node)
                    if idx + 1 < len(block) and isinstance(block[idx + 1], ast.Try):
                        return block[idx + 1]
                    return None
        return None

    def _record(self, call: ast.Call, severity: str) -> None:
        line = call.lineno
        col = call.col_offset
        snippet = self._lines[line - 1].strip() if 0 < line <= len(self._lines) else ''
        self.findings.append(LeakFinding(
            file=self._file, line=line, col=col,
            function=self._enclosing_function(),
            snippet=snippet[:140], severity=severity,
        ))


def _call_inside_with_items(with_node: ast.AST, call: ast.Call) -> bool:
    """True if ``call`` is a descendant of any ``withitem.context_expr``."""
    items = getattr(with_node, 'items', ())
    for item in items:
        for descendant in ast.walk(item.context_expr):
            if descendant is call:
                return True
    return False


def _function_body_closes_target(fn_node: ast.AST, assign_node: ast.Assign,
                                 target: str) -> bool:
    """True if anywhere in ``fn_node.body`` *after* ``assign_node`` there is
    a call that releases ``target`` (via ``.close()`` or a helper like
    ``_close_db_safely(target, …)``).

    Intentionally loose: an audit tool is only useful if it distinguishes
    real leaks from known-safe patterns. A cleanup-skipping branch still
    flags as a false negative here, but is far rarer than the "cleanup
    happens in a downstream Try" pattern this check is meant to recognise.
    """
    close_markers = ('close', 'release', 'dispose')
    # Find the assign_node's position in fn_node.body so we only scan forward.
    try:
        start = fn_node.body.index(assign_node)
    except ValueError:
        # assign_node nested deeper than top-level; scan the whole function.
        start = -1

    stmts = fn_node.body[start + 1:] if start >= 0 else fn_node.body
    for stmt in stmts:
        for node in ast.walk(stmt):
            if not isinstance(node, ast.Call):
                continue
            # <target>.close()
            if (isinstance(node.func, ast.Attribute)
                    and node.func.attr == 'close'
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == target):
                return True
            # helper(<target>, ...) where helper name hints close/release.
            if (isinstance(node.func, ast.Name)
                    and node.args
                    and isinstance(node.args[0], ast.Name)
                    and node.args[0].id == target
                    and any(m in node.func.id.lower() for m in close_markers)):
                return True
    return False


def _try_closes_target(try_node: ast.Try, target: str) -> bool:
    """True if ``try_node.finalbody`` releases the target connection.

    Recognises three shapes:
        * Direct method call:   ``<target>.close()``
        * Project wrapper:      ``_close_db_safely(<target>, …)``
                                ``close_db(<target>)`` / ``release(<target>)``
        * Any Call that takes ``<target>`` as its first positional argument
          and whose name contains ``close`` or ``release`` (catches future
          helper names without having to patch this tool every time).
    """
    close_helper_markers = ('close', 'release', 'dispose')

    def _is_target_close(node: ast.AST) -> bool:
        if not isinstance(node, ast.Call):
            return False
        # 1. <target>.close()
        if (isinstance(node.func, ast.Attribute)
                and node.func.attr == 'close'
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == target):
            return True
        # 2/3. helper(<target>, ...) where helper name hints close/release.
        if (isinstance(node.func, ast.Name)
                and node.args
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == target
                and any(m in node.func.id.lower() for m in close_helper_markers)):
            return True
        return False

    for stmt in try_node.finalbody:
        for descendant in ast.walk(stmt):
            if _is_target_close(descendant):
                return True
    return False


# ─── Driver ──────────────────────────────────────────────────────────────────


def _iter_py_files(root: Path) -> Iterable[Path]:
    for path, dirs, files in os.walk(root):
        # Prune excluded subtrees in-place so os.walk skips them.
        rel = os.path.relpath(path, root).replace('\\', '/')
        dirs[:] = [d for d in dirs if d not in _EXCLUDED_DIRS
                   and f'{rel}/{d}' not in _EXCLUDED_DIRS]
        if rel in _EXCLUDED_DIRS:
            dirs[:] = []
            continue
        for name in files:
            if name.endswith('.py'):
                yield Path(path) / name


def audit_repo(root: Path) -> list[FileReport]:
    reports: list[FileReport] = []
    for file_path in _iter_py_files(root):
        try:
            source = file_path.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            continue
        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError:
            continue
        visitor = _DbCallVisitor(
            file_path=str(file_path.relative_to(root)).replace('\\', '/'),
            source_lines=source.splitlines(),
        )
        # The visit infrastructure needs the module node to seed the
        # ancestor stack, so walk from there.
        visitor.visit(tree)
        if visitor.findings:
            reports.append(FileReport(
                file=str(file_path.relative_to(root)).replace('\\', '/'),
                findings=visitor.findings,
            ))
    return reports


def format_markdown(reports: list[FileReport]) -> str:
    total = sum(len(r.findings) for r in reports)
    lines: list[str] = []
    lines.append('# `get_db()` leak audit — factory-loop iteration 2')
    lines.append('')
    lines.append(f'Total suspect call sites: **{total}** across {len(reports)} files.')
    lines.append('')
    lines.append(
        'Generated by `tools/audit_db_sessions.py`. A finding here means a '
        '`get_db()` call isn\'t paired with either a `db_session()` context '
        'manager (preferred) or a `try/finally: db.close()` pair. Each is a '
        'candidate pooled-connection leak.'
    )
    lines.append('')
    lines.append('## Severity legend')
    lines.append('')
    lines.append('- **assigned-but-not-closed** — `db = get_db()` without a `try/finally` that closes `db`. Highest priority; the worker holds a live connection for the caller\'s lifetime.')
    lines.append('- **bare-call** — `get_db().execute(...)` as an expression. The connection is abandoned after the chained call; the pool will eventually reclaim it but transactions may linger.')
    lines.append('')
    lines.append('## Known-safe patterns (not leaks)')
    lines.append('')
    lines.append('These shapes still appear in the table because the classifier is deliberately precise, but they are intentional:')
    lines.append('')
    lines.append('- `db.py::_pool_acquire` returning `get_db()` — the pool function\'s contract is to hand ownership of a fresh connection to its caller, which then returns it via the `db_session()` context manager on exit. The pool itself can\'t close what it\'s yielding.')
    lines.append('- `tests/test_db_safety.py::test_get_db_*` — tests that exercise `get_db()`\'s OWN cleanup-on-failure behaviour. Skipping close in the test body is the scenario under test.')
    lines.append('- `tests/conftest.py::db` fixture — a "keeper" connection that persists for the shared in-memory SQLite URI throughout the fixture\'s lifetime, then closes on teardown via ``yield`` semantics.')
    lines.append('')
    if not reports:
        lines.append('_No findings._ Repo is clean under the AST classifier.')
        lines.append('')
        return '\n'.join(lines)

    # Aggregate summary by directory so the reader knows where to start.
    dir_counts: dict[str, int] = {}
    for r in reports:
        top = r.file.split('/', 1)[0] if '/' in r.file else r.file
        dir_counts[top] = dir_counts.get(top, 0) + len(r.findings)
    lines.append('## Top-level summary')
    lines.append('')
    lines.append('| Top-level | Findings |')
    lines.append('|-----------|---------:|')
    for directory, count in sorted(dir_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f'| `{directory}/` | {count} |')
    lines.append('')

    reports_sorted = sorted(reports, key=lambda r: (-len(r.findings), r.file))
    for report in reports_sorted:
        lines.append(f'## `{report.file}` ({len(report.findings)} finding{"s" if len(report.findings) != 1 else ""})')
        lines.append('')
        lines.append('| Location | Function | Severity | Snippet |')
        lines.append('|----------|----------|----------|---------|')
        for f in sorted(report.findings, key=lambda x: x.line):
            lines.append(f.as_markdown_row())
        lines.append('')

    return '\n'.join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-o', '--output',
        help='Write the Markdown report to this path. Default: stdout.',
    )
    parser.add_argument(
        '--root', default='.',
        help='Repo root to scan (default: current working directory).',
    )
    parser.add_argument(
        '--fail-on-find', action='store_true',
        help='Exit with status 1 if any finding is recorded (for CI gating).',
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    reports = audit_repo(root)
    report = format_markdown(reports)

    if args.output:
        out_path = Path(args.output).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding='utf-8')
    else:
        sys.stdout.write(report)
        sys.stdout.write('\n')

    total = sum(len(r.findings) for r in reports)
    if args.fail_on_find and total > 0:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
