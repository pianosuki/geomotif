"""Generate the parts of the documentation that are derived from the code.

Three kinds of page are not written by hand, because writing them by hand is how
documentation goes stale:

- **the API reference** -- one page per public module, each a single ``:::``
  directive that mkdocstrings fills in from the docstrings;
- **the gallery** -- every registered motif, rendered to SVG at its own native
  resolution, beside the code that reproduces exactly that picture;
- **the catalog** -- the same list as a plain table, for reading rather than
  looking at.

The reference and the gallery are rebuilt on every docs build and are not
committed: an SVG per motif comes to several megabytes, and a generated file in
the tree is a file that can disagree with the code. The catalog and the
handful of images the README leads with *are* committed, because GitHub renders
a README without ever running mkdocs -- so those two are checked for drift
instead, by ``make docs-check`` and by CI.

This module is both a script and an mkdocs hook. ``mkdocs.yml`` names it under
``hooks:``, so ``mkdocs serve`` and ``mkdocs build`` regenerate everything
themselves and neither needs a separate step. Writing is conditional on the
content actually differing, which is what keeps ``mkdocs serve`` from noticing a
file it has just rewritten and rebuilding forever.
"""

from __future__ import annotations

import argparse
import json
import pkgutil
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import geomotif
import geomotif.compose
import geomotif.motifs
from geomotif import to_spec, to_svg
from geomotif.core import registry

if TYPE_CHECKING:
    from collections.abc import Iterator

    from geomotif.core.registry import MotifInfo, ParamInfo

__all__ = ["generate", "main", "on_config"]

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

#: Canvas for a gallery image, in SVG user units. The design is fitted to it,
#: so this is a display size and not a resolution -- the geometry underneath is
#: whatever the motif built.
GALLERY_SIZE = 320

#: Canvas for the images the README leads with, which sit several to a row.
HERO_SIZE = 200

#: Stroke for a gallery image. Near-black, and the dark theme inverts the whole
#: image rather than shipping a second copy of every file.
GALLERY_INK = "#0b0b0b"

#: Stroke for a README image. A README has no stylesheet to invert it and no
#: way to know which theme it is being read on, so these are drawn in a grey
#: that stays legible on a white page and on a black one alike.
HERO_INK = "#808080"

#: The motifs the README leads with. Chosen for variety rather than rank: a
#: spiral, a polar figure, a fractal, an aperiodic tiling, a knot and a
#: composition, so the strip shows the range instead of six of one thing.
HERO = (
    "spiral.golden",
    "rose.maurer",
    "fractal.hilbert",
    "tiling.penrose-p3",
    "knot.celtic-grid",
    "mandala",
)

#: How long a generated constructor call may get before the gallery falls back
#: to building the motif through the registry instead.
_CALL_WIDTH = 110

#: Where a module lands in the reference nav, in reading order: what the library
#: *is*, then what you extend, then what it ships, then the surfaces around it.
_GROUPS = (
    "Overview",
    "Core",
    "Motif bases",
    "Motif catalog",
    "Composers",
    "Reading and writing",
    "Surfaces",
)


def main(argv: list[str] | None = None) -> int:
    """Regenerate the derived documentation and report what changed."""
    parser = argparse.ArgumentParser(
        prog="gendocs", description="Regenerate the derived parts of the documentation."
    )
    parser.add_argument("--docs", type=Path, default=DOCS, help="documentation root")
    args = parser.parse_args(argv)

    changed = generate(args.docs)
    for path in changed:
        print(f"wrote {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    print(f"{len(changed)} file(s) changed")
    return 0


def on_config(config: Any) -> None:  # noqa: ARG001
    """Regenerate before mkdocs reads the file tree. This is the ``hooks:`` entry.

    Typed as ``Any`` rather than importing mkdocs, so that this module stays
    importable -- and type-checkable -- in an environment that has geomotif but
    not the documentation toolchain.
    """
    generate(DOCS)


def generate(docs: Path = DOCS) -> list[Path]:
    """Write every derived page under ``docs``, returning the ones that changed."""
    return [
        *_reference(docs / "reference"),
        *_gallery(docs / "gallery"),
        *_catalog(docs / "catalog.md"),
        *_hero(docs / "assets"),
    ]


# --- the API reference ------------------------------------------------------


def _reference(out: Path) -> Iterator[Path]:
    """Write one page per public module, plus the nav that lists them."""
    modules = sorted(_public_modules(), key=lambda name: (_GROUPS.index(_group(name)), name))
    for module in modules:
        yield from _write(out / _page_name(module), f"::: {module}\n")
    yield from _prune(out, {*map(_page_name, modules), "SUMMARY.md"})

    lines = [_BANNER, ""]
    for group in _GROUPS:
        members = [module for module in modules if _group(module) == group]
        match members:
            case []:
                continue
            case [only]:
                lines.append(f"* [{group}]({_page_name(only)})")
            case _:
                lines.append(f"* {group}")
                lines.extend(f"    * [`{module}`]({_page_name(module)})" for module in members)
    yield from _write(out / "SUMMARY.md", "\n".join(lines) + "\n")


def _public_modules() -> Iterator[str]:
    """Yield every importable module of the package that is not private.

    Walked rather than listed, so a module added to the package cannot be
    forgotten here. ``__main__`` is skipped because importing it runs the
    command line, and an underscore-prefixed module is skipped because that
    leading underscore is the whole convention for "not part of the API".
    """
    yield geomotif.__name__
    for found in pkgutil.walk_packages(geomotif.__path__, f"{geomotif.__name__}."):
        if not found.name.rpartition(".")[2].startswith("_"):
            yield found.name


def _group(module: str) -> str:
    """Return the reference-nav heading a module belongs under."""
    match module.split("."):
        case ["geomotif"]:
            return "Overview"
        case ["geomotif", "core", *_]:
            return "Core"
        case ["geomotif", "bases", *_]:
            return "Motif bases"
        case ["geomotif", "motifs", *_]:
            return "Motif catalog"
        case ["geomotif", "compose", *_]:
            return "Composers"
        case ["geomotif", "io", *_]:
            return "Reading and writing"
        case _:
            return "Surfaces"


def _page_name(module: str) -> str:
    """Return a module's page: ``geomotif.core.types`` becomes ``core.types.md``."""
    stem = module.removeprefix("geomotif.")
    return "index.md" if stem == geomotif.__name__ else f"{stem}.md"


# --- the gallery ------------------------------------------------------------


def _gallery(out: Path) -> Iterator[Path]:
    """Write a page per family, an image per motif, and the nav over both."""
    families = {family: _describe(family) for family in registry.families()}

    for family, infos in families.items():
        for info in infos:
            yield from _image(out / "img", info, GALLERY_SIZE)
        yield from _write(out / f"{family}.md", _family_page(family, infos))
    yield from _prune(out / "img", {f"{name}.svg" for name in registry.names()})
    yield from _prune(out, {*(f"{family}.md" for family in families), "index.md", "SUMMARY.md"})

    yield from _write(out / "index.md", _gallery_index(families))
    lines = [
        _BANNER,
        "",
        "* [Overview](index.md)",
        *(f"* [{family} ({len(infos)})]({family}.md)" for family, infos in families.items()),
    ]
    yield from _write(out / "SUMMARY.md", "\n".join(lines) + "\n")


def _describe(family: str) -> list[MotifInfo]:
    """Return every motif in one family, described."""
    return [registry.describe(name) for name in registry.names(family=family)]


def _gallery_index(families: dict[str, list[MotifInfo]]) -> str:
    """Return the gallery's front page: one thumbnail and one line per family."""
    total = sum(len(infos) for infos in families.values())
    lines = [
        _BANNER,
        "",
        "# Gallery",
        "",
        f"All {total} registered motifs, rendered by geomotif itself at the parameters",
        "each one's `example=` records -- the same parameters `geomotif render NAME`",
        "starts from. Every picture is the motif at its **native resolution**: what",
        "`build()` produced, before any resampling. The code beside it reproduces that",
        "exact file.",
        "",
        "| Family | Motifs | |",
        "|---|---|---|",
    ]
    for family, infos in families.items():
        names = ", ".join(f"`{info.name}`" for info in infos[:4])
        more = ", …" if len(infos) > 4 else ""
        thumb = f"![](img/{infos[0].name}.svg){{ .motif .thumb }}"
        lines.append(f"| [**{family}**]({family}.md) | {names}{more} | {thumb} |")
    lines += [
        "",
        "None of this is committed to the repository. The images are rebuilt from the",
        "registry on every documentation build, so a motif cannot be shown here at",
        "parameters it no longer has.",
        "",
    ]
    return "\n".join(lines)


def _family_page(family: str, infos: list[MotifInfo]) -> str:
    """Return one family's page: every motif, with its picture, code and parameters."""
    lines = [
        _BANNER,
        "",
        f"# {family}",
        "",
        f"{len(infos)} motifs. Import them from `geomotif.motifs`, or build one by name",
        f'with `registry.create("{infos[0].name}")`.',
        "",
    ]
    for info in infos:
        lines += [f"## `{info.name}`", "", *_picture(info), _md(info.summary), ""]
        lines += [*_tabs(info), *_parameters(info)]
    return "\n".join(lines)


def _picture(info: MotifInfo) -> list[str]:
    """Return the image for a motif, or the reason this machine could not draw it."""
    if info.available:
        return [f"![{info.name}](img/{info.name}.svg){{ .motif }}", ""]
    return [
        '!!! warning "Not rendered here"',
        "",
        f"    This motif needs the `{info.requires}` extra, which the machine that built",
        "    these pages did not have. It is still listed, described and serialized",
        "    without it; only building one raises.",
        "",
    ]


def _tabs(info: MotifInfo) -> list[str]:
    """Return the Python / command line / spec tab block for one motif."""
    command = f"```bash\ngeomotif render {info.name} --out {info.name}.svg\n```"
    return [
        '=== "Python"',
        "",
        _indent(_python(info), 4),
        "",
        '=== "Command line"',
        "",
        _indent(command, 4),
        "",
        '=== "Spec"',
        "",
        _indent(_spec(info), 4),
        "",
    ]


def _python(info: MotifInfo) -> str:
    """Return the code that reproduces this motif's gallery image.

    Written as a constructor call where the example can be said in one, and
    through the registry where it cannot -- a composer's example holds whole
    motifs, and spelling those out would be a page of imports rather than an
    illustration.
    """
    call = _call(info)
    save = (
        f'save_svg(motif.build(), "{info.name}.svg", width={GALLERY_SIZE}, height={GALLERY_SIZE})'
    )
    if call is None:
        return "\n".join(
            [
                "```python",
                "from geomotif import save_svg",
                "from geomotif.core import registry",
                "",
                "# This motif's example takes values that are themselves objects, so it",
                "# reads better through the registry than as a constructor call.",
                f'motif = registry.create("{info.name}", **registry.describe("{info.name}").example)',
                save,
                "```",
            ]
        )
    return "\n".join(
        [
            "```python",
            "from geomotif import save_svg",
            f"from {_home(info)} import {info.cls.__name__}",
            "",
            f"motif = {call}",
            save,
            "```",
        ]
    )


def _call(info: MotifInfo) -> str | None:
    """Return the constructor call for a motif's example, or ``None`` if it needs objects.

    Length is a reason to give up as well as type. A Voronoi diagram's example
    is a scatter of three dozen points: perfectly sayable, and a line of code
    nobody would read. Past ``_CALL_WIDTH`` the registry form says the same
    thing in one line.
    """
    arguments: list[str] = []
    for name, value in info.example.items():
        if not _sayable(value):
            return None
        arguments.append(f"{name}={value!r}")
    call = f"{info.cls.__name__}({', '.join(arguments)})"
    return None if len(call) > _CALL_WIDTH else call


def _sayable(value: object) -> bool:
    """Return whether a value's ``repr`` is something you could paste back in."""
    match value:
        case None | bool() | int() | float() | str():
            return True
        case tuple() | list():
            return all(_sayable(item) for item in value)
        case _:
            return False


def _home(info: MotifInfo) -> str:
    """Return the module a motif class is meant to be imported from.

    Where it is *defined* is an implementation detail. ``geomotif.motifs`` and
    ``geomotif.compose`` are the two flat namespaces the catalog is published
    through, and a snippet should name the one a reader would type.
    """
    for module in ("geomotif.motifs", "geomotif.compose"):
        if getattr(sys.modules[module], info.cls.__name__, None) is info.cls:
            return module
    return info.cls.__module__


def _spec(info: MotifInfo) -> str:
    """Return the motif's spec file, or the reason it has not got one."""
    try:
        blob = to_spec(registry.create(info.name, **info.example))
    except TypeError as exc:
        return f"This motif has no spec:\n\n```text\n{exc.args[0]}\n```"
    return f"```json\n{json.dumps(blob, indent=2)}\n```"


def _parameters(info: MotifInfo) -> list[str]:
    """Return the collapsible parameter table for one motif.

    The last column is only drawn when something would go in it: prose beside a
    parameter comes from a ``#:`` comment on the field, and most motifs say
    what they need to say in the class docstring instead.
    """
    if not info.params:
        return [""]
    described = any(param.description for param in info.params)
    header = "| Name | Type | Default |" + (" Notes |" if described else "")
    rule = "|---|---|---|" + ("---|" if described else "")
    rows = [
        f"    | `{param.name}` | {_code(param.annotation)} | {_default(param)} |"
        + (f" {_md(param.description or '')} |" if described else "")
        for param in info.params
    ]
    return ['??? abstract "Parameters"', "", f"    {header}", f"    {rule}", *rows, ""]


def _default(param: ParamInfo) -> str:
    """Render a parameter's default for a table cell, stably.

    A default that is a function reprs with its address in it, which would make
    this page differ between two runs of the same code and turn the drift check
    into a coin toss. What matters about such a default is that it is a
    function, and it says that.
    """
    if param.required:
        return "*required*"
    if _sayable(param.default):
        return _code(repr(param.default))
    return f"a {type(param.default).__name__}"


def _image(out: Path, info: MotifInfo, size: int, stroke: str = GALLERY_INK) -> Iterator[Path]:
    """Render one motif to SVG, if this machine has what it needs to build it."""
    if not info.available:
        return
    design = registry.create(info.name, **info.example).build()
    # precision=2 rather than the writer's default of 3: the design has already
    # been fitted to a canvas this small, so a third decimal is a hundredth of a
    # pixel, and dropping it takes about a tenth off the file.
    yield from _write(
        out / f"{info.name}.svg",
        to_svg(design, width=size, height=size, precision=2, stroke=stroke, title=info.name),
    )


# --- the committed pieces ---------------------------------------------------


def _catalog(out: Path) -> Iterator[Path]:
    """Write the whole registry as one table -- the gallery, for reading."""
    names = registry.names()
    families = registry.families()
    lines = [
        _BANNER,
        "",
        "# The catalog",
        "",
        f"{len(names)} motifs in {len(families)} families, as of geomotif",
        f"{geomotif.__version__}. Every one of them resamples by arc length, takes every",
        "spacing curve, and exports to SVG, DXF, GIF, CSV, TXT, JSON and a spec file.",
        "",
        "The pictures are in [the gallery](gallery/index.md); this page is the same",
        "list in a form you can search and read.",
        "",
    ]
    for family in families:
        lines += [
            f"## {family}",
            "",
            "| Motif | Class | Summary |",
            "|---|---|---|",
            *(
                f"| `{info.name}` | `{info.cls.__name__}` | {_cell(_md(info.summary))}"
                f"{'' if info.available else f' *(needs `{info.requires}`)*'} |"
                for info in _describe(family)
            ),
            "",
        ]
    yield from _write(out, "\n".join(lines))


def _hero(out: Path) -> Iterator[Path]:
    """Render the images the README leads with.

    Committed, unlike the gallery, because GitHub renders a README without ever
    running mkdocs. They are small, monochrome and written by geomotif's own SVG
    writer, so the bytes are deterministic and a diff here is a real signal.
    """
    for name in HERO:
        yield from _image(out, registry.describe(name), HERO_SIZE, stroke=HERO_INK)
    yield from _prune(out, {f"{name}.svg" for name in HERO})


# --- writing ----------------------------------------------------------------

_BANNER = "<!-- Generated by tools/gendocs.py. Do not edit; run `make docs-gen`. -->"

#: ``:class:`~geomotif.PolarMotif``` and friends. Only the last dotted part is
#: kept, because the reference already says which module a name lives in.
_ROLE = re.compile(r":[a-z]+:`~?([^`]+)`")

#: RST spells inline code with two backticks; Markdown spells it with one.
_LITERAL = re.compile(r"``([^`]+)``")


def _md(text: str) -> str:
    """Render the RST flavour of a docstring as Markdown.

    Docstrings here are numpydoc, which is RST underneath, and these pages are
    Markdown. Two constructs actually occur in the catalog -- inline literals
    and ``:class:`` cross-references -- so two substitutions cover it, and
    anything more elaborate would be guessing at text that is not there.
    """
    text = _ROLE.sub(lambda match: f"`{match.group(1).rpartition('.')[2]}`", text)
    return _LITERAL.sub(r"`\1`", text)


def _cell(text: str) -> str:
    """Escape prose for a Markdown table cell.

    The table extension splits a row on every pipe, so one in the text itself
    has to be escaped out of the way.
    """
    return text.replace("|", "\\|")


def _code(text: str) -> str:
    """Render a value as code inside a table cell, pipes and all.

    Backticks are no good here: a union type reads ``int | None``, the table
    extension splits the row on that pipe, and escaping it leaves a visible
    backslash because a code span is taken literally. Raw HTML with a numeric
    character reference is the way through -- the cell never sees a pipe, and
    the browser prints one.
    """
    return f"<code>{text.replace('|', '&#124;')}</code>"


def _write(path: Path, content: str) -> Iterator[Path]:
    """Write ``content`` to ``path``, yielding the path only if it changed.

    Rewriting an identical file would still be enough to wake mkdocs' file
    watcher, which would run this hook again, which would rewrite the file:
    comparing first is what keeps ``mkdocs serve`` from looping on its own
    output.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")
    yield path


def _prune(directory: Path, keep: set[str]) -> Iterator[Path]:
    """Delete generated files that nothing generates any more, yielding each.

    Without this, renaming a motif would leave its old image behind: the docs
    would keep showing a picture of something that no longer exists, and the
    drift check would pass, because nothing had changed.
    """
    if not directory.is_dir():
        return
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.name not in keep:
            path.unlink()
            yield path


def _indent(text: str, width: int) -> str:
    """Indent every non-empty line, for a block nested inside a Markdown tab."""
    pad = " " * width
    return "\n".join(f"{pad}{line}" if line else line for line in text.splitlines())


if __name__ == "__main__":
    raise SystemExit(main())
