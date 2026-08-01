"""The house style is American English, and this test keeps it that way.

Geomotif shipped a British/American split -- American on the public API
(center, ink, --color) and British in the prose (colour, centre, catalogue).
1.2.0 resolved it in favour of American, and this test makes the spelling a
fail-fast check rather than a review comment. It walks the repository and
flags the British spellings the style guide bans, with the American spelling
to use instead.

One name is deliberately exempt: `colours_in` shipped in 1.1.0 and is kept as
a deprecated alias for `colors_in`, so this test must not flag it. It does not
-- the scan matches word boundaries, and `colours_in`'s trailing underscore
keeps it from matching ``colours``. The exemption is otherwise total: nowhere
else may a British spelling appear.

See ``docs/style-guide.md`` for the policy behind the list.
"""

from __future__ import annotations

import re
from pathlib import Path

#: ``(british_pattern, american)`` -- a matched British spelling is reported
#: with the American replacement, pointing at the style guide. Patterns are
#: case-insensitive and word-bounded, so ``colour`` and ``Colour`` are caught
#: but not ``colourful`` or ``colours_in``.
_BRITISH: tuple[tuple[str, str], ...] = (
    (r"\bcolours\b", "colors"),
    (r"\bcolour\b", "color"),
    (r"\bcentr(?:e|es|ed)\b", "center"),
    (r"\blabelled\b", "labeled"),
    (r"\btravelled\b", "traveled"),
    (r"\bhonours\b", "honors"),
    (r"\bhonour(?:ed|ing)?\b", "honor"),
    (r"\bbehaviour\b", "behavior"),
    (r"\brecognis(?:e|es|ed|ing)\b", "recognize"),
    (r"\bmillimetres?\b", "millimeter"),
    (r"\bcatalogue\b", "catalog"),
    (r"\brasteris(?:e|ed|es|ing)\b", "rasterize"),
    (r"\bquantis(?:e|er|es|ed|ing)\b", "quantize"),
    (r"\bquantisation\b", "quantization"),
    (r"\bmanoeuvre\b", "maneuver"),
)

#: The roots this test sweeps. Scan both the code and the prose, because a
#: misspelt help string or docstring is as much a breach of the style as a
#: misspelt identifier. Generated binary and virtual-environment trees are
#: excluded.
_ROOTS = (
    Path("src"),
    Path("tests"),
    Path("tools"),
    Path("examples"),
    Path("docs"),
    Path(".github"),
    Path("Makefile"),
    Path("README.md"),
    Path("CHANGELOG.md"),
    Path("CONTRIBUTING.md"),
    Path("CODE_OF_CONDUCT.md"),
    Path("mkdocs.yml"),
    Path(".gitignore"),
)

#: Files that are *about* the British spellings and therefore name them on
#: purpose: the style guide's own replacement table, and this test's pattern
#: list. They state what is banned rather than serving as examples of it.
_EXEMPT = {Path("docs/style-guide.md"), Path("tests/test_spelling.py")}

_FAILED: list[str] = []


def _is_target(path: Path) -> bool:
    """Whether a file path is prose or code this test should read."""
    if ".git" in path.parts or "__pycache__" in path.parts:
        return False
    if path in _EXEMPT:
        return False
    return path.suffix in {".py", ".md", ".yml", ".yaml", ".css"} or path.name in {
        "Makefile",
        ".gitignore",
    }


def _check_file(path: str) -> None:
    """Record every British spelling in one file, with its fix and location."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, start=1):
        for pattern, american in _BRITISH:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                _FAILED.append(
                    f"{path}:{line_number}: found {match.group()!r} "
                    f"-- write {american!r} instead (see docs/style-guide.md)"
                )


def test_the_house_style_is_american_english():
    """No British spelling appears in the code, the tests, or the docs."""
    for root in _ROOTS:
        if root.is_dir():
            for path in sorted(root.rglob("*")):
                if _is_target(path):
                    _check_file(str(path))
        elif root.is_file():
            _check_file(str(root))

    assert not _FAILED, "British spelling crept in:\n" + "\n".join(_FAILED)


def test_the_deprecated_alias_is_the_one_allowed_override():
    """`colours_in` is exempted, because it shipped in 1.1.0 and still works."""
    from geomotif.io.raster import colors_in, colours_in

    assert colours_in.__name__ == "colours_in"
    assert colors_in.__name__ == "colors_in"
