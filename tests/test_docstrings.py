"""The example code in module docstrings, checked against the modules it names.

A docstring example is documentation that nothing runs, which is the kind that
goes quietly wrong: `geomotif.core.style` spent a release importing a motif
called `PhyllotaxisPoints`, which has never existed, and then calling
`save_svg` without importing it at all.

The examples are not executed -- several of them write files -- but every name
they import is resolved, and every function they call is traced to an import,
an assignment or a builtin. Those are the two mistakes that docstring made.
"""

from __future__ import annotations

import ast
import builtins
import importlib
import pkgutil
import textwrap

import pytest

import geomotif


def _examples():
    """Yield ``(module name, parsed example)`` for every docstring holding code."""
    for found in pkgutil.walk_packages(geomotif.__path__, "geomotif."):
        module = importlib.import_module(found.name)
        tree = _parsed(module.__doc__ or "")
        if tree is not None and any(
            isinstance(node, ast.Import | ast.ImportFrom) for node in ast.walk(tree)
        ):
            yield module.__name__, tree


def _parsed(doc: str) -> ast.Module | None:
    """Parse the indented block of a ``::`` example, or return None if there isn't one."""
    lines = [line for line in textwrap.dedent(doc).splitlines() if line.startswith("    ")]
    try:
        return ast.parse(textwrap.dedent("\n".join(lines)))
    except SyntaxError:
        return None


CASES = list(_examples())


@pytest.mark.parametrize(("name", "tree"), CASES, ids=[name for name, _ in CASES])
def test_every_name_an_example_imports_exists(name, tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = importlib.import_module(node.module or "")
            for alias in node.names:
                assert hasattr(module, alias.name), (
                    f"{name}'s example imports {alias.name!r} from {node.module}, "
                    f"which has no such name"
                )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                importlib.import_module(alias.name)


@pytest.mark.parametrize(("name", "tree"), CASES, ids=[name for name, _ in CASES])
def test_every_function_an_example_calls_is_one_it_has(name, tree):
    known = set(dir(builtins))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            known |= {(alias.asname or alias.name).split(".")[0] for alias in node.names}
        elif isinstance(node, ast.Assign):
            known |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        elif isinstance(node, ast.FunctionDef):
            known.add(node.name)

    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert called <= known, (
        f"{name}'s example calls {sorted(called - known)} without importing or defining it"
    )
