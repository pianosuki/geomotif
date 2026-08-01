"""The ``geomotif`` command line.

Pure :mod:`argparse`, so the zero-dependency core stays that way::

    geomotif list                                  # every motif, by family
    geomotif list --family fractal
    geomotif show rose                             # docs, parameters, defaults
    geomotif render rose --n 5 --samples 400 --out rose.svg
    geomotif render spiral.golden --samples 300 --ease power:2.5 --out s.csv
    geomotif render fractal.hilbert --depth 6 --out h.dxf --fit 800x800
    geomotif render fractal.hilbert --out h.gif --motion draw-on --frames 60
    geomotif render fractal.hilbert --out h.gif --frames 60 --hold 12
    geomotif render mandala --out m.svg --paper a4 --optimize    # for a plotter
    geomotif render --spec my-design.json --out out.svg
    geomotif explore rose --out rose.html          # sliders for its parameters
    geomotif gallery --out docs/gallery
    geomotif demo

A motif's flags are generated from its dataclass fields, which is the point of
every builtin motif being one: ``--n``, ``--depth``, ``--center 0,0`` and the
rest all come from the same declaration that drives ``describe()`` and the spec
format. Nothing is written twice.

Two things follow from generating flags rather than writing them.

**Not every parameter can be said on a command line.** A motif parameterized by
a Python function, by another motif, or by a point set has no sensible flag.
Those take their value from the motif's registered example instead, so every
motif in the catalog still renders -- ``geomotif render voronoi.cells`` gives
you the example's point set, and ``--inset`` still works on top of it.

**A generic flag and a motif parameter share one namespace.** The handful of
names this module claims are listed in :data:`RESERVED`; a motif parameter that
collides with one is not given a flag, and there is a test that no builtin
does. That is why the sampling options are ``--samples``, ``--stride`` and
``--ease`` rather than the more obvious words, which are all taken by motifs.
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys
import textwrap
from typing import TYPE_CHECKING, Any, Literal, cast, get_args, get_origin

from . import __version__
from .core import registry
from .core.spacing import (
    CircularSpacing,
    CubicSpacing,
    ExponentialSpacing,
    LinearSpacing,
    PowerSpacing,
    QuadraticSpacing,
    SineSpacing,
    SmoothstepSpacing,
    SpacingCurve,
)
from .core.transform import SNAP_MODES
from .core.types import Bounds
from .explore import DEFAULT_SIZE, DEFAULT_STEPS, save_html
from .io import load_spec, save_design, save_dxf, save_gif, save_png, save_svg, to_spec
from .io.plotter import PAPER, optimize, save_plotter_svg

# Imported rather than repeated: "0 or negative writes whole integers" is part
# of the export contract, and two copies of it would eventually disagree.
from .io.points import _rounder

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .core.motif import Motif
    from .core.registry import MotifInfo, ParamInfo
    from .core.types import Design, Point

__all__ = ["MOTIONS", "RESERVED", "build_parser", "main"]

#: Option names the command line keeps for itself. A motif parameter with one
#: of these names gets no flag and falls back to its example value, because
#: argparse has one namespace and the generic option has to win.
RESERVED = frozenset(
    {
        "aa_level",
        "antialias",
        "background",
        "by",
        "compression",
        "distribute",
        "dither",
        "dot_radius",
        "ease",
        "fit",
        "fps",
        "frames",
        "hold",
        "ink",
        "keep_duplicates",
        "landscape",
        "loop",
        "margin",
        "motion",
        "optimize",
        "out",
        "padding",
        "paper",
        "precision",
        "quality",
        "samples",
        "snap",
        "snap_mode",
        "spec",
        "stride",
        "title",
    }
)

#: How ``--motion`` turns one design into many. Sweeping a parameter is not
#: here: it needs a parameter name and a range of values, which is two more
#: flags and a small language to say them in -- write it in Python, where
#: :func:`geomotif.animate.sweep` takes exactly the values you mean.
MOTIONS = ("draw-on", "spin")

#: Canvas for an animation when ``--fit`` did not say, in pixels.
_GIF_SIZE = 480

#: The ``name:arg:arg`` mini-syntax for ``--ease``. The arguments are handed to
#: the constructor positionally, which is why ``power:2.5`` sets the exponent
#: and ``exp:out:6`` sets the mode and then the strength -- each class already
#: declares them in the order you would say them.
SPACINGS: dict[str, type[SpacingCurve]] = {
    "linear": LinearSpacing,
    "power": PowerSpacing,
    "quadratic": QuadraticSpacing,
    "cubic": CubicSpacing,
    "sine": SineSpacing,
    "exp": ExponentialSpacing,
    "exponential": ExponentialSpacing,
    "circular": CircularSpacing,
    "smoothstep": SmoothstepSpacing,
}

#: Which writer a ``--out`` suffix asks for.
_WRITERS = {
    ".svg": "svg",
    ".dxf": "dxf",
    ".csv": "design",
    ".txt": "design",
    ".tsv": "design",
    ".json": "design",
    ".gif": "gif",
    ".png": "png",
    ".pdf": "figure",
    ".jpg": "figure",
    ".jpeg": "figure",
}


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line and return the process exit code."""
    args = list(sys.argv[1:] if argv is None else argv)
    motif = _peek_motif(args)
    parser = build_parser(motif)
    parsed = parser.parse_args(_glue_coordinates(args, _coordinate_flags(motif)))
    handlers = {
        "list": _list,
        "show": _show,
        "render": _render,
        "explore": _explore,
        "gallery": _gallery,
        "demo": _demo,
    }
    try:
        return handlers[parsed.command](parsed)
    except (KeyError, ValueError, TypeError, OSError) as exc:
        # KeyError stringifies with its own quotes around the whole message,
        # which reads badly on a terminal.
        message = exc.args[0] if isinstance(exc, KeyError) and exc.args else exc
        print(f"geomotif: error: {message}", file=sys.stderr)
        return 2


def build_parser(motif: MotifInfo | None = None) -> argparse.ArgumentParser:
    """Build the parser, with ``motif``'s own flags added to ``render`` if given."""
    parser = argparse.ArgumentParser(
        prog="geomotif",
        description="Generate geometric designs and write them out.",
    )
    parser.add_argument("--version", action="version", version=f"geomotif {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    listing = sub.add_parser("list", help="every registered motif, grouped by family")
    listing.add_argument("--family", help="only this family")
    listing.add_argument("--names", action="store_true", help="bare names, one per line")

    show = sub.add_parser("show", help="one motif's documentation and parameters")
    show.add_argument("name", help="registered motif name")

    render = sub.add_parser(
        "render",
        help="build a motif and write it out",
        description=(
            "Build a motif and write it out. Without --out the points go to stdout as "
            "CSV. Run 'geomotif show NAME' or 'geomotif render NAME --help' to see a "
            "motif's own flags."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    render.add_argument("name", nargs="?", help="registered motif name")
    render.add_argument("--spec", type=pathlib.Path, help="read the motif from a spec file instead")
    render.add_argument("--samples", type=int, metavar="N", help="resample to N points")
    render.add_argument(
        "--stride", type=float, metavar="D", help="a point every D units of real distance"
    )
    render.add_argument(
        "--ease",
        type=_spacing,
        metavar="CURVE",
        help=f"spacing curve, as name[:arg[:arg]] from {sorted(SPACINGS)}",
    )
    render.add_argument("--by", choices=("length", "parameter"), default="length")
    render.add_argument("--distribute", choices=("length", "even", "per_path"), default="length")
    render.add_argument("--fit", type=_size, metavar="WxH", help="scale onto a canvas")
    render.add_argument(
        "--canvas",
        type=_size,
        metavar="WxH",
        help="pixel canvas for a .gif, .png or .jpg",
    )
    render.add_argument("--motion", choices=MOTIONS, default="draw-on", help="how a .gif animates")
    render.add_argument("--frames", type=int, default=48, metavar="N", help="frames in a .gif")
    render.add_argument(
        "--hold",
        type=_nonnegative_int,
        metavar="N",
        help="how long .gif sits on the finished drawing, in frames (default: a quarter of --frames)",
    )
    render.add_argument("--fps", type=float, default=20.0, metavar="X", help="a .gif's frame rate")
    render.add_argument(
        "--loop", type=_nonnegative_int, default=0, metavar="N", help="times a .gif plays (0=forever)"
    )
    render.add_argument(
        "--stroke-width",
        type=_positive_int,
        default=1,
        metavar="PX",
        help="stroke width, in pixels",
    )
    render.add_argument(
        "--dot-radius",
        type=_positive_int,
        metavar="PX",
        help="loose-point radius, in pixels (default: --thickness)",
    )
    render.add_argument("--ink", default="#0b0b0b", help="default stroke color, a name or #hex")
    render.add_argument(
        "--background", default="#ffffff", help="canvas color, a name or #hex"
    )
    render.add_argument(
        "--padding",
        type=_nonnegative_float,
        default=8.0,
        metavar="PX",
        help="margin around a raster drawing, in pixels",
    )
    render.add_argument(
        "--antialias", action="store_true", help="smooth a raster drawing's edges"
    )
    render.add_argument(
        "--aa-level",
        type=_positive_int,
        default=8,
        metavar="N",
        help="with --antialias, shades an edge may blend into per color pair",
    )
    render.add_argument(
        "--dither",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="error-diffuse a .gif's palette round-off (--no-dither turns it off)",
    )
    render.add_argument(
        "--compression",
        type=_nonnegative_int,
        default=6,
        choices=range(10),
        metavar="0-9",
        help="zlib level a .png is deflated at (0 fast, 9 small)",
    )
    render.add_argument(
        "--paper",
        choices=sorted(PAPER),
        help="write a .svg at this paper size, in real millimeters, for a plotter",
    )
    render.add_argument("--landscape", action="store_true", help="turn --paper on its side")
    render.add_argument(
        "--margin",
        type=float,
        default=10.0,
        metavar="MM",
        help="with --paper, border to leave unplotted, in millimeters",
    )
    render.add_argument(
        "--optimize",
        action="store_true",
        help="join strokes that meet and order them so the pen travels less",
    )
    render.add_argument(
        "--snap", type=float, metavar="STEP", help="move every point onto a grid this size"
    )
    render.add_argument(
        "--snap-mode",
        choices=SNAP_MODES,
        default="half-even",
        help="which way --snap sends a point between two grid lines",
    )
    render.add_argument(
        "--keep-duplicates",
        action="store_true",
        help="with --snap, keep the points a coarse grid stacked up rather than dropping them",
    )
    render.add_argument("--precision", type=int, metavar="N", help="decimal places to write")
    render.add_argument("--title", help="title for the SVG document or the figure")
    render.add_argument("--out", type=pathlib.Path, help=f"output file; {sorted(_WRITERS)}")
    if motif is not None:
        _add_motif_flags(render, motif)

    explore = sub.add_parser(
        "explore",
        help="one HTML page with a slider per parameter",
        description=(
            "Write a self-contained page with a slider for every parameter a slider "
            "can move. Every frame is rendered ahead of time and embedded, so the "
            "page needs no server and works offline."
        ),
    )
    explore.add_argument("names", nargs="*", help="registered motif names")
    explore.add_argument("--family", help="every motif in this family as well")
    explore.add_argument("--out", type=pathlib.Path, default=pathlib.Path("explore.html"))
    explore.add_argument("--steps", type=int, default=DEFAULT_STEPS, help="values per slider")
    explore.add_argument("--size", type=int, default=DEFAULT_SIZE, help="frame canvas, in units")
    explore.add_argument(
        "--samples", type=int, metavar="N", help="resample each frame, to keep the page small"
    )

    gallery = sub.add_parser("gallery", help="render every motif to SVG, with a manifest")
    gallery.add_argument("--out", type=pathlib.Path, default=pathlib.Path("gallery"))
    gallery.add_argument("--family", help="only this family")
    gallery.add_argument("--size", type=int, default=320, help="SVG canvas, in user units")

    demo = sub.add_parser("demo", help="the spacing-curve showcase (needs matplotlib)")
    demo.add_argument("out", nargs="?", help="save the figure here instead of opening a window")
    return parser


# --- commands --------------------------------------------------------------


def _list(args: argparse.Namespace) -> int:
    """Print the catalog, grouped by family."""
    names = registry.names(family=args.family)
    if not names:
        raise KeyError(
            f"no motifs in family {args.family!r}; try one of {list(registry.families())}"
        )
    if args.names:
        print("\n".join(names))
        return 0

    by_family: dict[str, list[MotifInfo]] = {}
    for name in names:
        info = registry.describe(name)
        by_family.setdefault(info.family or "(none)", []).append(info)

    width = max(len(name) for name in names)
    for family, infos in sorted(by_family.items()):
        print(f"\n{family} ({len(infos)})")
        for info in infos:
            note = "" if info.available else f"  [needs {info.requires}]"
            print(f"  {info.name:<{width}}  {_shorten(info.summary, 78 - width)}{note}")
    families = "family" if len(by_family) == 1 else "families"
    print(f"\n{len(names)} motifs in {len(by_family)} {families}")
    return 0


def _show(args: argparse.Namespace) -> int:
    """Print one motif's documentation, parameters and a usable example command."""
    info = registry.describe(args.name)
    print(f"{info.name}  ({info.family or 'no family'})")
    if not info.available:
        print(f"  unavailable: needs {info.requires} -- pip install 'geomotif[{info.requires}]'")
    print()
    for line in _prose(info.doc).splitlines():
        print(f"  {line}" if line else "")

    settable = [p for p in info.params if _flag_for(p, info, _default_for(p, info)) is not None]
    if settable:
        print("\nparameters:")
        width = max(len(p.name) for p in settable)
        for param in settable:
            flag = f"--{param.name.replace('_', '-')}"
            print(
                f"  {flag:<{width + 2}}  {param.annotation:<16}  default: {_default_for(param, info)!r}"
            )

    rest = [p.name for p in info.params if p not in settable]
    if rest:
        print("\nnot settable from the command line (taken from the example):")
        print(f"  {', '.join(rest)}")

    print(f"\nexample:\n  geomotif render {info.name} --out {info.name}.svg")
    return 0


def _render(args: argparse.Namespace) -> int:
    """Build one motif and write it wherever ``--out`` says."""
    motif = _motif_from(args)
    design = _sample(motif, args)
    if args.optimize:
        design = optimize(design)
    if args.fit is not None:
        design = design.fit(*args.fit)
    if args.snap is not None:
        # Last, so --fit cannot scale the grid away underneath it. The writers
        # that place a design themselves -- .svg, --paper, .gif, the matplotlib
        # formats -- rescale it anyway; the guide says so.
        design = design.snapped(
            args.snap, mode=args.snap_mode, drop_duplicates=not args.keep_duplicates
        )
    if args.out is None:
        return _to_stdout(design, args.precision)
    _write(design, args.out, args)
    print(f"wrote {args.out}", file=sys.stderr)
    return 0


def _explore(args: argparse.Namespace) -> int:
    """Write one page with a slider per parameter, every frame already drawn."""
    names = list(args.names)
    if args.family is not None:
        names.extend(name for name in registry.names(family=args.family) if name not in names)
    if not names:
        raise ValueError("nothing to explore: name a motif, or pass --family")

    written = save_html(
        names,
        args.out,
        steps=args.steps,
        size=args.size,
        samples=args.samples,
        title=names[0] if len(names) == 1 else "geomotif",
    )
    size = written.stat().st_size
    print(f"wrote {written} ({size // 1024} KB, {len(names)} motif(s))", file=sys.stderr)
    return 0


def _gallery(args: argparse.Namespace) -> int:
    """Render every available motif to SVG, plus a manifest that rebuilds them."""
    args.out.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, object]] = []
    skipped: list[str] = []
    for name in registry.names(family=args.family):
        info = registry.describe(name)
        if not info.available:
            skipped.append(name)
            continue
        motif = registry.create(name, **info.example)
        target = args.out / f"{name}.svg"
        save_svg(motif.build(), target, width=args.size, height=args.size, title=name)
        entry: dict[str, object] = {
            "name": name,
            "family": info.family,
            "summary": info.summary,
            "file": target.name,
        }
        try:
            entry["spec"] = to_spec(motif)
        except TypeError:
            # A motif parameterized by a Python function has no spec; the
            # picture is still worth having, and the gap is worth recording.
            entry["spec"] = None
        entries.append(entry)

    manifest = args.out / "manifest.json"
    manifest.write_text(json.dumps(entries, indent=2) + "\n")
    note = f", {len(skipped)} skipped (missing extras)" if skipped else ""
    print(f"wrote {len(entries)} SVGs and {manifest}{note}", file=sys.stderr)
    return 0


def _demo(args: argparse.Namespace) -> int:
    """Run the showcase figure."""
    from .demo import main as run_demo

    run_demo([args.out] if args.out else [])
    return 0


# --- putting a motif together ----------------------------------------------


def _peek_motif(argv: list[str]) -> MotifInfo | None:
    """Look ahead for ``render NAME`` so the parser can carry that motif's flags.

    The name has to be the first word after ``render`` for this to work, which
    is the documented form anyway. An unknown name is left alone here so that
    the registry can report it with its own near-miss suggestion.
    """
    if argv[:1] != ["render"] or len(argv) < 2 or argv[1].startswith("-"):
        return None
    try:
        return registry.describe(argv[1])
    except KeyError:
        return None


def _motif_from(args: argparse.Namespace) -> Motif:
    """Build the motif named on the command line, or read it from a spec."""
    if args.spec is not None:
        if args.name is not None:
            raise ValueError(f"give a motif name or --spec, not both (got {args.name!r})")
        return load_spec(args.spec)
    if args.name is None:
        raise ValueError("nothing to render: name a motif, or pass --spec FILE")
    info = registry.describe(args.name)
    return registry.create(args.name, **_motif_params(info, args))


def _motif_params(info: MotifInfo, args: argparse.Namespace) -> dict[str, object]:
    """Merge the flags that were parsed over the motif's registered example."""
    values = dict(info.example)
    for param in info.params:
        dest = _dest(param)
        if hasattr(args, dest):
            values[param.name] = getattr(args, dest)
    return values


def _sample(motif: Motif, args: argparse.Namespace) -> Design:
    """Resample the design if asked to, or return it at its native resolution."""
    if args.samples is None and args.stride is None:
        if args.ease is not None:
            raise ValueError("--ease needs a point count: add --samples N or --stride D")
        return motif.build()
    return motif.generate(
        args.samples,
        step=args.stride,
        spacing=args.ease,
        distribute=args.distribute,
        by=args.by,
    )


def _add_motif_flags(parser: argparse.ArgumentParser, info: MotifInfo) -> None:
    """Add one flag per parameter the command line can express."""
    for param in info.params:
        if param.name in RESERVED:
            continue
        default = _default_for(param, info)
        options = _flag_for(param, info, default)
        if options is None:
            continue
        parser.add_argument(f"--{param.name.replace('_', '-')}", dest=_dest(param), **options)


def _coordinate_flags(motif: MotifInfo | None) -> frozenset[str]:
    """Return the options whose value may begin with a minus sign."""
    flags = {"--fit"}
    if motif is not None:
        for param in motif.params:
            options = _flag_for(param, motif, _default_for(param, motif))
            if options is not None and options.get("type") in {_point, _bounds}:
                flags.add(f"--{param.name.replace('_', '-')}")
    return frozenset(flags)


def _glue_coordinates(argv: list[str], flags: frozenset[str]) -> list[str]:
    """Join a coordinate value onto its option, so a leading minus is not read as one.

    ``--region -60,-60,60,60`` fails in plain argparse: the value starts with a
    dash and is not a bare negative number, so it is taken for another option.
    The ``--region=-60,...`` form has always worked; this makes the spaced
    form -- the one people actually type -- work as well.

    Only options known to take coordinates are touched, and only when the next
    token starts with a dash, so nothing else changes shape on the way in.
    """
    glued: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        following = argv[index + 1] if index + 1 < len(argv) else ""
        if token in flags and following.startswith("-"):
            glued.append(f"{token}={following}")
            index += 2
        else:
            glued.append(token)
            index += 1
    return glued


def _dest(param: ParamInfo) -> str:
    """Return where a motif flag lands, kept clear of the generic options."""
    return f"motif_{param.name}"


def _default_for(param: ParamInfo, info: MotifInfo) -> object:
    """Return the value a flag starts from: the example, else the declared default.

    Starting from the example means ``geomotif render rose`` draws the rose
    from the catalog and ``--n 7`` changes one thing about it, rather than
    silently rendering a different motif than the gallery shows.
    """
    return info.example.get(param.name, param.default)


def _flag_for(param: ParamInfo, info: MotifInfo, default: object) -> dict[str, Any] | None:
    """Return the argparse options for a parameter, or ``None`` if it cannot be a flag."""
    if param.name in RESERVED:
        return None
    # argparse skips a blank help line entirely, defaults and all, so a
    # parameter with no `help=` metadata falls back to naming its own type.
    shared: dict[str, Any] = {"default": default, "help": param.description or param.annotation}
    choices = _literal_choices(param.annotation, info.cls)
    if choices is not None:
        return {**shared, "choices": list(choices)}
    match param.annotation:
        case "bool":
            return {**shared, "action": argparse.BooleanOptionalAction}
        case "int" | "int | None":
            return {**shared, "type": int, "metavar": "N"}
        case "float" | "float | None":
            return {**shared, "type": float, "metavar": "X"}
        case "str" | "str | None":
            return {**shared, "type": str, "metavar": "TEXT"}
        case "Point" | "Point | None":
            return {**shared, "type": _point, "metavar": "X,Y"}
        case "Bounds" | "Bounds | None":
            return {**shared, "type": _bounds, "metavar": "X0,Y0,X1,Y1"}
        case _:
            return None


def _literal_choices(annotation: str, cls: type) -> tuple[str, ...] | None:
    """Return the permitted strings, if the annotation is a Literal or an alias for one.

    Annotations arrive as text, because ``from __future__ import annotations``
    means nothing ever evaluated them. A bare ``Literal[...]`` can be read
    straight out of the string; a named alias has to be looked up in the module
    that declared the motif, which is where the name was in scope.
    """
    if annotation.startswith("Literal["):
        return tuple(part.strip().strip("'\"") for part in annotation[8:-1].split(","))
    alias = getattr(sys.modules.get(cls.__module__), annotation, None)
    value = getattr(alias, "__value__", None)
    if get_origin(value) is Literal:
        args = get_args(value)
        if all(isinstance(arg, str) for arg in args):
            return args
    return None


# --- small parsers and writers ---------------------------------------------


def _nonnegative_int(text: str) -> int:
    """Parse a whole number that may not go below zero."""
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected a whole number -- got {text!r}") from None
    if value < 0:
        raise argparse.ArgumentTypeError(f"--hold must be >= 0, got {value}")
    return value


def _positive_int(text: str) -> int:
    """Parse a whole number that must be at least one."""
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected a whole number -- got {text!r}") from None
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be >= 1, got {value}")
    return value


def _nonnegative_float(text: str) -> float:
    """Parse a number that may not go below zero."""
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected a number -- got {text!r}") from None
    if value < 0:
        raise argparse.ArgumentTypeError(f"must be >= 0, got {value}")
    return value


def _point(text: str) -> Point:
    """Parse ``x,y``."""
    try:
        x, y = (float(part) for part in text.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected x,y -- got {text!r}") from None
    return (x, y)


def _bounds(text: str) -> Bounds:
    """Parse ``min_x,min_y,max_x,max_y``."""
    try:
        values = [float(part) for part in text.split(",")]
        return Bounds(*values)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(f"expected x0,y0,x1,y1 -- got {text!r} ({exc})") from None


def _size(text: str) -> tuple[float, float]:
    """Parse ``800x600``."""
    try:
        width, height = (float(part) for part in text.lower().split("x"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected WxH -- got {text!r}") from None
    return (width, height)


def _spacing(text: str) -> SpacingCurve:
    """Parse the ``name[:arg[:arg]]`` spacing mini-syntax."""
    name, *rest = text.split(":")
    factory = SPACINGS.get(name)
    if factory is None:
        raise argparse.ArgumentTypeError(f"unknown spacing curve {name!r}; try {sorted(SPACINGS)}")
    try:
        return factory(*(_number_or_word(arg) for arg in rest))
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(f"cannot build {text!r}: {exc}") from None


def _number_or_word(text: str) -> float | str:
    """Read a spacing argument: a number or a mode name, and it is obvious which."""
    try:
        return float(text)
    except ValueError:
        return text


def _prose(doc: str) -> str:
    """Return the human half of a docstring: everything before its first section.

    A motif's ``Parameters`` section says the same thing this command already
    prints from the dataclass fields, and says it less usefully -- no defaults,
    no flag names. Cutting it leaves the part that only prose can carry.

    Only the first line of a docstring is flush left, so the rest is dedented
    to match it rather than arriving with the source's indentation attached.
    """
    summary, _, rest = doc.partition("\n")
    lines = [summary, *textwrap.dedent(rest).splitlines()]
    kept: list[str] = []
    for line, following in zip(lines, [*lines[1:], ""], strict=True):
        # A numpydoc section is a title underlined with dashes, so the title
        # is only recognizable from the line after it.
        underline = following.strip()
        if underline and set(underline) == {"-"}:
            break
        kept.append(line)
    return "\n".join(kept).rstrip()


def _shorten(text: str, width: int) -> str:
    """Trim a summary to fit a listing line."""
    return text if len(text) <= width else text[: max(width - 1, 0)].rstrip() + "…"


def _write(design: Design, target: pathlib.Path, args: argparse.Namespace) -> None:
    """Write the design in whatever format the file suffix asks for."""
    kind = _WRITERS.get(target.suffix.lower())
    if kind is None:
        raise ValueError(
            f"do not know how to write {target.suffix!r}; expected one of {sorted(_WRITERS)}"
        )
    match kind:
        case "svg" if args.paper is not None:
            save_plotter_svg(
                design,
                target,
                paper=args.paper,
                landscape=args.landscape,
                margin=args.margin,
                precision=3 if args.precision is None else args.precision,
                title=args.title,
            )
        case "svg":
            precision = 3 if args.precision is None else args.precision
            save_svg(design, target, precision=precision, title=args.title)
        case "dxf":
            precision = 4 if args.precision is None else args.precision
            save_dxf(design, target, precision=precision)
        case "design":
            save_design(design, target, precision=args.precision)
        case "gif":
            _save_animation(design, target, args)
        case "png":
            _save_still(design, target, args)
        case _:
            _save_figure(design, target, args)


def _save_animation(design: Design, target: pathlib.Path, args: argparse.Namespace) -> None:
    """Turn one design into frames and write them as an animated GIF."""
    from .animate import draw_on, spin

    width, height = _canvas(args)
    hold = _hold_for(args)
    match args.motion:
        case "spin":
            frames = spin(design, args.frames, hold=hold)
        case _:
            frames = draw_on(design, args.frames, hold=hold)
    save_gif(
        frames,
        target,
        width=width,
        height=height,
        fps=args.fps,
        loop=args.loop,
        ink=args.ink,
        background=args.background,
        thickness=args.stroke_width,
        dot_radius=args.dot_radius,
        padding=args.padding,
        antialias=args.antialias,
        aa_level=args.aa_level,
        dither=args.dither,
    )


def _canvas(args: argparse.Namespace) -> tuple[int, int]:
    """Return the raster canvas in pixels, ``--canvas`` winning over ``--fit``.

    ``--canvas`` changes how big the pixels are, ``--fit`` changes what the
    drawing is -- so when both are given the drawing is still fitted onto the
    world canvas (in _render) and the pixel canvas comes from ``--canvas``
    alone. Either alone sets the canvas from itself; neither falls back to the
    1.1.0 fixed 480.
    """
    if args.canvas is not None:
        return round(args.canvas[0]), round(args.canvas[1])
    if args.fit is not None:
        return round(args.fit[0]), round(args.fit[1])
    return _GIF_SIZE, _GIF_SIZE


def _hold_for(args: argparse.Namespace) -> int:
    """How many copies of the finished drawing to sit on, for this invocation.

    ``--hold`` wins when it is given; otherwise each motion keeps the behavior
    it has always had -- ``draw-on`` settles on a quarter of the run, and
    ``spin``, whose whole business is turning, holds nothing.
    """
    if args.motion == "spin" and args.hold is None:
        return 0
    held = args.hold if args.hold is not None else max(1, args.frames // 4)
    return cast("int", held)


def _save_still(design: Design, target: pathlib.Path, args: argparse.Namespace) -> None:
    """Render the finished design as one raster still: a PNG, with no extra install.

    Where a GIF is the moving picture (a run of frames), a still is the
    picture that does not move: the completed design drawn once. The animation
    flags -- ``--motion``, ``--frames``, ``--hold`` -- simply do not apply and
    are ignored, so ``render rose --motion spin --out rose.png`` degrades
    gracefully to a still of the final shape.
    """
    width, height = _canvas(args)
    save_png(
        design,
        target,
        width=width,
        height=height,
        ink=args.ink,
        background=args.background,
        thickness=args.stroke_width,
        dot_radius=args.dot_radius,
        padding=args.padding,
        antialias=args.antialias,
        aa_level=args.aa_level,
        compression=args.compression,
    )


def _save_figure(design: Design, target: pathlib.Path, args: argparse.Namespace) -> None:
    """Render through matplotlib, which is the only optional part of the CLI."""
    try:
        from .plotting import plot_design
    except ImportError:
        raise SystemExit(
            f"writing {target.suffix} needs matplotlib: pip install 'geomotif[plot]'"
        ) from None
    ax = plot_design(design, title=args.title, show_points=args.samples is not None)
    figure = ax.get_figure()
    figure.savefig(target, dpi=150, facecolor=figure.get_facecolor())


def _to_stdout(design: Design, precision: int | None) -> int:
    """Write the points to stdout as CSV, so the command composes with a pipe."""
    coord = _rounder(precision)
    writer = csv.writer(sys.stdout)
    writer.writerow(("x", "y"))
    writer.writerows((coord(x), coord(y)) for x, y in design)
    return 0
