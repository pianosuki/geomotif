"""Affine transforms and the composite operators built on them.

This layer is why the motif catalogue stays a sane size. Mandalas,
snowflakes, rosettes, kaleidoscopes and most tessellations are
:func:`radial_repeat` or :func:`tile` applied to one small motif, not thirty
hardcoded classes.

:class:`Affine` follows the SVG/PostScript convention: the six coefficients
``(a, b, c, d, e, f)`` are the matrix ::

    | a  c  e |
    | b  d  f |
    | 0  0  1 |

so a point maps to ``(a*x + c*y + e, b*x + d*y + f)``.
"""

from __future__ import annotations

import decimal
import itertools
import math
import random
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Literal, Self

from .types import Design, Path, select_styles

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from .types import Bounds, Point

__all__ = [
    "SNAP_MODES",
    "Affine",
    "SnapMode",
    "clip_to",
    "fit_to",
    "jitter",
    "layer",
    "mirror_axis",
    "offset_path",
    "radial_repeat",
    "snap",
    "symmetry_group",
    "tile",
]

type SnapMode = Literal["half-even", "half-up", "floor", "ceil", "trunc"]

#: Every rounding rule :func:`snap` understands. Named rather than inferred,
#: because a user interface offering the choice needs the list and should not
#: have to hardcode it.
SNAP_MODES: tuple[SnapMode, ...] = ("half-even", "half-up", "floor", "ceil", "trunc")


@dataclass(frozen=True, slots=True)
class Affine:
    """A 2D affine transform, composable with ``@`` and callable on points.

    Defaults to the identity, so ``Affine()`` is a no-op you can build on.
    """

    a: float = 1.0
    b: float = 0.0
    c: float = 0.0
    d: float = 1.0
    e: float = 0.0
    f: float = 0.0

    @classmethod
    def identity(cls) -> Self:
        """Return the transform that changes nothing."""
        return cls()

    @classmethod
    def translate(cls, dx: float, dy: float) -> Self:
        """Move by ``dx`` horizontally and ``dy`` vertically."""
        return cls(e=dx, f=dy)

    @classmethod
    def rotate(cls, angle: float, *, about: Point = (0.0, 0.0)) -> Self:
        """Rotate by ``angle`` radians, counter-clockwise in y-up coordinates."""
        cos, sin = math.cos(angle), math.sin(angle)
        cx, cy = about
        return cls(
            a=cos,
            b=sin,
            c=-sin,
            d=cos,
            e=cx - cx * cos + cy * sin,
            f=cy - cx * sin - cy * cos,
        )

    @classmethod
    def scale(cls, sx: float, sy: float | None = None, *, about: Point = (0.0, 0.0)) -> Self:
        """Scale by ``sx`` horizontally and ``sy`` vertically (``sy`` defaults to ``sx``)."""
        if sy is None:
            sy = sx
        cx, cy = about
        return cls(a=sx, d=sy, e=cx - cx * sx, f=cy - cy * sy)

    @classmethod
    def mirror(cls, angle: float = 0.0, *, through: Point = (0.0, 0.0)) -> Self:
        """Reflect across the line at ``angle`` radians passing through ``through``."""
        cos, sin = math.cos(2.0 * angle), math.sin(2.0 * angle)
        cx, cy = through
        return cls(
            a=cos,
            b=sin,
            c=sin,
            d=-cos,
            e=cx - cx * cos - cy * sin,
            f=cy - cx * sin + cy * cos,
        )

    @classmethod
    def shear(cls, kx: float, ky: float = 0.0) -> Self:
        """Slant by ``kx`` along x per unit y, and ``ky`` along y per unit x."""
        return cls(c=kx, b=ky)

    def __matmul__(self, other: Affine) -> Affine:
        """Compose: ``(m @ n)(p) == m(n(p))`` -- the right-hand one applies first."""
        if not isinstance(other, Affine):
            return NotImplemented
        return Affine(
            a=self.a * other.a + self.c * other.b,
            b=self.b * other.a + self.d * other.b,
            c=self.a * other.c + self.c * other.d,
            d=self.b * other.c + self.d * other.d,
            e=self.a * other.e + self.c * other.f + self.e,
            f=self.b * other.e + self.d * other.f + self.f,
        )

    def __call__(self, p: Point) -> Point:
        """Return ``p`` mapped through this transform."""
        x, y = p
        return (self.a * x + self.c * y + self.e, self.b * x + self.d * y + self.f)

    @property
    def determinant(self) -> float:
        """Signed area scale factor; negative when the transform reflects."""
        return self.a * self.d - self.b * self.c

    def inverse(self) -> Affine:
        """Return the transform that undoes this one.

        Raises
        ------
        ValueError
            If the transform is singular (a zero scale factor, say), which
            collapses the plane onto a line and cannot be undone.
        """
        det = self.determinant
        if det == 0.0:
            raise ValueError(f"transform is singular and cannot be inverted: {self!r}")
        return Affine(
            a=self.d / det,
            b=-self.b / det,
            c=-self.c / det,
            d=self.a / det,
            e=(self.c * self.f - self.d * self.e) / det,
            f=(self.b * self.e - self.a * self.f) / det,
        )


def layer(*designs: Design) -> Design:
    """Overlay designs into one. Equivalent to repeated ``+``."""
    result = Design()
    for design in designs:
        result = result + design
    return result


def radial_repeat(
    design: Design,
    n: int,
    *,
    about: Point = (0.0, 0.0),
    mirror: bool = False,
) -> Design:
    """Repeat ``design`` ``n`` times evenly around a point -- the mandala workhorse.

    Parameters
    ----------
    design : Design
        The unit to repeat.
    n : int
        Number of copies, including the original. Must be >= 1.
    about : (float, float), optional
        Center of rotation.
    mirror : bool, optional
        Also emit a reflected copy in each sector, giving dihedral rather
        than merely cyclic symmetry.
    """
    if n < 1:
        raise ValueError(f"n must be >= 1, got {n}")
    step = math.tau / n
    parts: list[Design] = []
    for i in range(n):
        rotation = Affine.rotate(i * step, about=about)
        parts.append(design.transformed(rotation))
        if mirror:
            # Reflect in the sector's own bisector so the pair meets cleanly
            # at the spoke rather than overlapping the neighbouring copy.
            parts.append(design.transformed(rotation @ Affine.mirror(step / 2.0, through=about)))
    return layer(*parts)


def symmetry_group(design: Design, group: str) -> Design:
    """Apply a full cyclic ``Cn`` or dihedral ``Dn`` symmetry group.

    Parameters
    ----------
    design : Design
        The fundamental domain to replicate.
    group : str
        ``"C6"`` for 6-fold rotation, ``"D6"`` for 6-fold rotation plus
        mirrors. Case-insensitive.
    """
    name = group.strip().upper()
    kind, order = name[:1], name[1:]
    if kind not in ("C", "D") or not order.isdigit():
        raise ValueError(f"group must look like 'C6' or 'D6', got {group!r}")
    return radial_repeat(design, int(order), mirror=kind == "D")


def mirror_axis(design: Design, angle: float = 0.0, *, through: Point = (0.0, 0.0)) -> Design:
    """Return ``design`` overlaid with its reflection across a line."""
    return design + design.transformed(Affine.mirror(angle, through=through))


def tile(
    design: Design,
    cols: int,
    rows: int,
    *,
    dx: float,
    dy: float,
    stagger: float = 0.0,
) -> Design:
    """Repeat ``design`` on a rectangular lattice.

    Parameters
    ----------
    design : Design
        The unit cell contents.
    cols, rows : int
        Lattice size. Both must be >= 1.
    dx, dy : float
        Spacing between columns and rows.
    stagger : float, optional
        Fraction of ``dx`` by which to offset every other row -- ``0.5``
        gives the familiar brick/hexagonal offset.
    """
    if cols < 1 or rows < 1:
        raise ValueError(f"cols and rows must be >= 1, got {cols}x{rows}")
    parts = [
        design.transformed(Affine.translate(col * dx + (row % 2) * stagger * dx, row * dy))
        for row in range(rows)
        for col in range(cols)
    ]
    return layer(*parts)


def jitter(design: Design, amount: float, *, seed: int | None = None) -> Design:
    """Randomly displace every point, for controlled hand-drawn irregularity.

    Each coordinate is offset independently by a uniform value in
    ``[-amount, amount]``. The RNG is private to this call -- the global
    :mod:`random` state is never touched -- so a given ``seed`` always
    reproduces the same result no matter what else the program is doing.
    """
    if amount < 0:
        raise ValueError(f"amount must be >= 0, got {amount}")
    rng = random.Random(seed)

    def shift(p: Point) -> Point:
        return (p[0] + rng.uniform(-amount, amount), p[1] + rng.uniform(-amount, amount))

    paths = tuple(
        replace(path, points=tuple(shift(p) for p in path.points)) for path in design.paths
    )
    return Design(paths, tuple(shift(p) for p in design.points), design.meta)


def _quantizer(mode: SnapMode) -> Callable[[float], int]:
    """Return the rule taking a coordinate measured in grid steps to a grid line."""
    match mode:
        case "half-even":
            # What Python's own round() does, and therefore what the writers'
            # precision= has always done: halves alternate between the two
            # neighbours so a long list of them does not drift upward.
            return round
        case "half-up":
            # Away from zero, not toward +infinity. Toward +infinity would snap
            # a design and its mirror image onto grids a whole step apart, and
            # symmetry surviving the snap matters more here than agreeing with
            # the accountants' definition of the name.
            return lambda q: int(math.copysign(math.floor(abs(q) + 0.5), q))
        case "floor":
            return math.floor
        case "ceil":
            return math.ceil
        case "trunc":
            return math.trunc
        case _:
            raise ValueError(f"unknown snap mode {mode!r}; expected one of {list(SNAP_MODES)}")


def _grid_places(step: float) -> int:
    """Return the decimal places a multiple of ``step`` needs to be written exactly.

    Three tenths is ``0.30000000000000004`` if you reach it by multiplying, and
    that is the wrong answer to hand someone who asked for a tenth-unit grid:
    tidy numbers are the entire point of snapping, and one arriving with
    seventeen digits is not one. Rounding the product back to the step's own
    decimals removes the representation error and nothing else.
    """
    exponent = decimal.Decimal(str(step)).normalize().as_tuple().exponent
    return max(0, -int(exponent))


def _without_repeats(points: Iterable[Point], *, closed: bool) -> tuple[Point, ...]:
    """Drop each point equal to the one before it, and a seam that has closed itself.

    Only *consecutive* repeats go. A point that lands on some earlier,
    non-adjacent point of the same stroke is a crossing rather than a
    redundancy -- a figure eight snapped onto a coarse grid still has to go
    round both of its loops -- and dropping it would draw a different shape.
    """
    kept: list[Point] = []
    for point in points:
        if not kept or point != kept[-1]:
            kept.append(point)
    # A closed path's last segment is implied and never stored, so a final
    # point that has landed on the first would have the pen draw the seam
    # twice: once along the stroke and once round the implied closure.
    if closed and len(kept) > 1 and kept[-1] == kept[0]:
        kept.pop()
    return tuple(kept)


def snap(
    design: Design,
    step: float = 1.0,
    *,
    mode: SnapMode = "half-even",
    drop_duplicates: bool = True,
) -> Design:
    """Move every point onto the nearest line of a square grid.

    This is rounding applied to the *design* rather than to each file as it is
    written, which is the difference that matters: every exporter then agrees,
    and a plot of the result shows what the file will actually contain.
    ``design.snapped()`` alone rounds to whole units.

    Snapping trades this library's exact arc-length spacing for grid alignment.
    Points that were an equal real distance apart come out equal only to within
    half a step, so snap *after* resampling and choose a step well below the
    spacing if the evenness is what you are there for.

    Parameters
    ----------
    design : Design
        What to snap.
    step : float, optional
        Grid size, in the design's own units. Must be finite and positive.
        ``0.5`` snaps to half units, ``5`` to a five-unit lattice -- neither of
        which any number of decimal places can express.
    mode : {"half-even", "half-up", "floor", "ceil", "trunc"}, optional
        How a coordinate between two grid lines is resolved. ``half-even`` is
        the default and matches the writers' ``precision=``: it goes to the
        nearer line, and a coordinate exactly halfway goes to the even one.
        ``half-up`` also goes to the nearer line but sends a halfway coordinate
        away from zero, which is the rounding most people were taught.
        ``floor``, ``ceil`` and ``trunc`` always go the same way -- down, up,
        and toward zero -- which is what a one-sided tolerance asks for.
    drop_duplicates : bool, optional
        Remove points that a coarse grid has landed on top of their immediate
        neighbour, and then any stroke left with fewer than two points. On by
        default, because those are zero-length segments: ink a plotter cannot
        draw and a pen-down/pen-up it should not spend the time on. Turn it off
        to keep the point count exactly as it was, which is what a caller
        feeding a fixed-size buffer or a per-point parallel array needs.

    Returns
    -------
    Design
        Snapped, with each surviving stroke's style following it across.

    Raises
    ------
    ValueError
        If ``step`` is not finite and positive, or ``mode`` is not one of the
        five above.

    Examples
    --------
    >>> from geomotif import Design, Path
    >>> square = Design((Path(((0.4, 0.4), (9.6, 0.4), (9.6, 9.6))),))
    >>> list(snap(square))
    [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
    >>> list(snap(square, 0.25))
    [(0.5, 0.5), (9.5, 0.5), (9.5, 9.5)]
    """
    if not math.isfinite(step) or step <= 0.0:
        raise ValueError(f"step must be finite and > 0, got {step}")
    to_grid = _quantizer(mode)
    places = _grid_places(step)

    def place(p: Point) -> Point:
        x, y = p
        return (round(to_grid(x / step) * step, places), round(to_grid(y / step) * step, places))

    paths: list[Path] = []
    # Which source stroke each surviving one came from, so the styles can be
    # carried across the ones that collapsed away.
    sources: list[int] = []
    for index, path in enumerate(design.paths):
        moved = tuple(place(p) for p in path.points)
        if drop_duplicates:
            moved = _without_repeats(moved, closed=path.closed)
            if len(moved) < 2:
                continue  # the whole stroke landed on one grid point
        paths.append(replace(path, points=moved))
        sources.append(index)

    loose = tuple(place(p) for p in design.points)
    kept = list(range(len(loose)))
    if drop_duplicates:
        # Every duplicate, not merely a consecutive one. A stroke's points are
        # a walk, so only its neighbours can be redundant -- a later revisit is
        # a crossing. Loose points are a set with no walk through them, and
        # which two of them happen to be adjacent in the tuple says nothing
        # about the drawing, so dropping by position would be arbitrary.
        seen: set[Point] = set()
        kept = []
        for i, p in enumerate(loose):
            if p not in seen:
                seen.add(p)
                kept.append(i)
        loose = tuple(loose[i] for i in kept)

    return Design(tuple(paths), loose, select_styles(design.meta, paths=sources, points=kept))


def fit_to(
    design: Design,
    width: float,
    height: float,
    *,
    padding: float = 0.0,
    flip_y: bool = False,
) -> Design:
    """Scale and center ``design`` inside a canvas. See :meth:`Design.fit`."""
    return design.fit(width, height, padding=padding, flip_y=flip_y)


def _clip_segment(a: Point, b: Point, bounds: Bounds) -> tuple[Point, Point] | None:
    """Liang-Barsky clip of one segment, or ``None`` if it misses entirely."""
    x0, y0 = a
    x1, y1 = b
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    for p, q in (
        (-dx, x0 - bounds.min_x),
        (dx, bounds.max_x - x0),
        (-dy, y0 - bounds.min_y),
        (dy, bounds.max_y - y0),
    ):
        if p == 0.0:
            if q < 0.0:
                return None  # parallel to this edge and outside it
            continue
        t = q / p
        if p < 0.0:
            if t > t1:
                return None
            t0 = max(t0, t)
        else:
            if t < t0:
                return None
            t1 = min(t1, t)
    if t0 > t1:
        return None
    return (
        (x0 + t0 * dx, y0 + t0 * dy),
        (x0 + t1 * dx, y0 + t1 * dy),
    )


def clip_to(design: Design, bounds: Bounds) -> Design:
    """Trim ``design`` to a rectangle, splitting paths that leave and re-enter.

    Clipped paths come back open even if they went in closed: a shape whose
    outline has been cut is no longer a closed loop, and pretending otherwise
    would draw a chord across the gap. Loose points outside the rectangle are
    dropped.
    """
    paths: list[Path] = []
    # One stroke in can be several strokes out, or none; ``sources`` records
    # which one each fragment came from so its style follows it across.
    sources: list[int] = []

    def emit(run: list[Point], source: int) -> None:
        """Keep a fragment, if it is long enough to draw."""
        if len(run) > 1:
            paths.append(Path(tuple(run)))
            sources.append(source)

    for index, path in enumerate(design.paths):
        vertices = list(path.points)
        if path.closed and len(vertices) > 2:
            vertices.append(vertices[0])
        run: list[Point] = []
        for a, b in itertools.pairwise(vertices):
            clipped = _clip_segment(a, b, bounds)
            if clipped is None:
                emit(run, index)
                run = []
                continue
            start, end = clipped
            if not run:
                run.append(start)
            elif math.dist(run[-1], start) > 1e-12:
                # The path left the box and came back: start a new stroke
                # rather than drawing the shortcut across the outside.
                emit(run, index)
                run = [start]
            run.append(end)
        emit(run, index)
    kept = [i for i, p in enumerate(design.points) if p in bounds]
    return Design(
        tuple(paths),
        tuple(design.points[i] for i in kept),
        select_styles(design.meta, paths=sources, points=kept),
    )


def offset_path(path: Path, distance: float) -> Path:
    """Return a parallel copy of ``path``, offset by ``distance`` to its left.

    Left is relative to the direction of travel in y-up coordinates, so a
    negative distance offsets to the right. Corners are mitered, with a limit
    that falls back to a plain bevel on very sharp turns.

    This is the "simple parallel stroke" of guilloché and knot outlines, not a
    CAD offset: self-intersections on tight concave corners are not cleaned
    up, and the result may cross itself where the offset exceeds the local
    radius of curvature.
    """
    vertices = list(path.points)
    if len(vertices) < 2:
        return path
    if path.closed and len(vertices) > 2:
        vertices.append(vertices[0])

    normals: list[Point] = []
    for a, b in itertools.pairwise(vertices):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        # Zero-length segments have no direction; inherit the previous one so
        # a duplicated vertex does not punch a hole in the offset.
        if length == 0.0:
            normals.append(normals[-1] if normals else (0.0, 0.0))
        else:
            normals.append((-dy / length, dx / length))

    # For unit normals n1, n2 the miter vector is 2*(n1 + n2) / |n1 + n2|^2:
    # it bisects the corner and is exactly 1/cos(half-angle) long, which is
    # what keeps the offset stroke a constant distance from the original.
    miter_limit = 4.0
    bevel_below = 2.0 / miter_limit
    offset: list[Point] = []
    for i, vertex in enumerate(vertices):
        before = normals[i - 1] if i > 0 else normals[0]
        after = normals[i] if i < len(normals) else normals[-1]
        mx, my = before[0] + after[0], before[1] + after[1]
        scale = math.hypot(mx, my)
        if scale < bevel_below:
            # Near-reversal: the miter would shoot off toward infinity, so
            # fall back to the outgoing normal and let the corner bevel.
            nx, ny = after
        else:
            nx, ny = 2.0 * mx / (scale * scale), 2.0 * my / (scale * scale)
        offset.append((vertex[0] + nx * distance, vertex[1] + ny * distance))

    if path.closed and len(path.points) > 2:
        offset.pop()
    return replace(path, points=tuple(offset))
