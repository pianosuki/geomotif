"""Impossible figures and interference patterns.

Two different tricks share this module because both are about what a *drawing*
can say that an object cannot.

The impossible figures -- :class:`PenroseTriangle`, :class:`PenroseStairs`,
:class:`ImpossibleCube` and the honestly ambiguous :class:`NeckerCube` -- all
lean on the same property of a parallel projection: it throws away depth. In an
isometric view, going one unit up is drawn exactly like going one unit away
along each of the two horizontal axes, so a figure whose ends fail to meet in
space by ``(t, t, t)`` meets itself perfectly on the page. That is not a fudge
in the drawing; it is the whole of why these figures work, and both Penrose
constructions here are built on it directly rather than by nudging coordinates
until they line up.

:class:`CafeWall` and :class:`MoirePattern` are the other kind: nothing about
them is impossible, and they still refuse to be seen straight. The cafe wall's
mortar lines are exactly parallel and the moire's fringes are not drawn at all
-- they are what two regular patterns make between them.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, override

from ..core.motif import Motif
from ..core.registry import register, spec
from ..core.types import Design, Path
from ._common import arc_points

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ..core.types import Point

__all__ = [
    "CafeWall",
    "ImpossibleCube",
    "MoirePattern",
    "NeckerCube",
    "PenroseStairs",
    "PenroseTriangle",
]

type Spatial = tuple[float, float, float]

type MoireKind = Literal["rings", "lines", "radial"]

#: The three isometric axes, as they land on the page. They are 120 degrees
#: apart, which is what makes the up-axis and the two-horizontal-axes-together
#: land in the same place.
_AXES = tuple(
    (math.cos(math.radians(angle)), math.sin(math.radians(angle))) for angle in (-30.0, 90.0, 210.0)
)

_ROOT3 = math.sqrt(3.0)

#: Ceilings, so a mistyped count raises rather than filling memory.
_MAX_STEPS = 40
_MAX_TILES = 4_000
_MAX_LINES = 600


def _check_size(owner: str, size: float, *, name: str = "size") -> None:
    if size <= 0.0:
        raise ValueError(f"{owner} {name} must be > 0, got {size}")


def _isometric(point: Spatial) -> Point:
    """Return a point in space as it lands on the page, seen along ``(1, 1, 1)``.

    Up and away-along-both-horizontals give the same answer, which is exactly
    the ambiguity the impossible figures live in: ``(t, t, t)`` maps to the
    origin for every ``t``.
    """
    x, y, z = point
    return ((x - y) * _ROOT3 / 2.0, z - (x + y) / 2.0)


def _fitted(
    shapes: Sequence[Sequence[Point]], size: float, center: Point
) -> tuple[tuple[Point, ...], ...]:
    """Scale a whole figure to ``size`` across and put its middle on ``center``.

    Applied to every shape at once rather than to each in turn, so that the
    parts keep their places relative to one another.
    """
    xs = [x for shape in shapes for x, _ in shape]
    ys = [y for shape in shapes for _, y in shape]
    scale = size / (max(xs) - min(xs))
    mx, my = (max(xs) + min(xs)) / 2.0, (max(ys) + min(ys)) / 2.0
    cx, cy = center
    return tuple(
        tuple((cx + (x - mx) * scale, cy + (y - my) * scale) for x, y in shape) for shape in shapes
    )


def _inside(polygon: Sequence[Point], point: Point) -> bool:
    """Even-odd point-in-polygon."""
    x, y = point
    hit = False
    for i, (x0, y0) in enumerate(polygon):
        x1, y1 = polygon[(i + 1) % len(polygon)]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            hit = not hit
    return hit


def _outside(loop: Sequence[Point], blocker: Sequence[Point]) -> list[tuple[Point, ...]]:
    """Return the pieces of a closed outline that ``blocker`` does not cover.

    Proper hidden-line removal rather than a break at each crossing: where one
    bar passes in front of another it hides a whole length of it, and drawing
    that length with two small gaps in it would not read as a solid bar.
    """
    corners = [*loop, loop[0]]
    pieces: list[tuple[Point, ...]] = []
    run: list[Point] = []
    for start, end in itertools.pairwise(corners):
        cuts = [0.0, 1.0]
        for i, edge_start in enumerate(blocker):
            edge_end = blocker[(i + 1) % len(blocker)]
            ux, uy = end[0] - start[0], end[1] - start[1]
            vx, vy = edge_end[0] - edge_start[0], edge_end[1] - edge_start[1]
            det = vx * uy - vy * ux
            if det == 0.0:
                continue
            rx, ry = edge_start[0] - start[0], edge_start[1] - start[1]
            here = (vx * ry - vy * rx) / det
            there = (ux * ry - uy * rx) / det
            if 1e-12 < here < 1.0 - 1e-12 and -1e-12 <= there <= 1.0 + 1e-12:
                cuts.append(here)
        cuts.sort()
        for first, second in itertools.pairwise(cuts):
            if second - first < 1e-12:
                continue
            head = (start[0] + first * (end[0] - start[0]), start[1] + first * (end[1] - start[1]))
            tail = (
                start[0] + second * (end[0] - start[0]),
                start[1] + second * (end[1] - start[1]),
            )
            middle = ((head[0] + tail[0]) / 2.0, (head[1] + tail[1]) / 2.0)
            if _inside(blocker, middle):
                if len(run) > 1:
                    pieces.append(tuple(run))
                run = []
            else:
                if not run:
                    run.append(head)
                run.append(tail)
    if len(run) > 1:
        pieces.append(tuple(run))
    # The outline's point list has to start somewhere; if that somewhere was
    # not hidden, the first and last pieces are really one piece.
    if len(pieces) > 1 and math.dist(pieces[-1][-1], pieces[0][0]) < 1e-12:
        pieces[0] = pieces[-1][:-1] + pieces[0]
        pieces.pop()
    return pieces


# --- the tribar -------------------------------------------------------------


@register("illusion.penrose-triangle", family="illusion")
@dataclass(frozen=True, slots=True)
class PenroseTriangle(Motif):
    """The tribar: three square beams meeting at three right angles.

    Each beam is drawn as the silhouette of a long cuboid seen isometrically,
    and the three are the same beam turned by a third of a revolution. Every
    beam passes in front of the next one round, which is the whole trick:
    locally each joint is an ordinary right angle, and following them round
    gets you back underneath where you started.

    Parameters
    ----------
    size : float, optional
        Width of the finished figure.
    thickness : float, optional
        Beam width as a fraction of its length. Thin beams give the spidery
        version, fat ones the chunky Escher version.
    center : (float, float), optional
        Middle of the figure.
    """

    size: float = 240.0
    thickness: float = 0.25
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        owner = type(self).__name__
        _check_size(owner, self.size)
        if not 0.0 < self.thickness < 0.5:
            raise ValueError(
                f"{owner} thickness must be strictly between 0 and 0.5, got "
                f"{self.thickness}; at half the length the three beams swallow "
                f"each other and there is no triangle left"
            )

    def beams(self) -> tuple[tuple[Point, ...], ...]:
        """Return the three beams as their outlines, before any is hidden."""
        length, width = 1.0, self.thickness
        beams: list[tuple[Point, ...]] = []
        for k in range(3):
            along, left, right = _AXES[k], _AXES[(k + 1) % 3], _AXES[(k + 2) % 3]
            # Each beam starts where the one before it ends: turning the start
            # by a third of a revolution has to land exactly one length along.
            turn = k * math.tau / 3.0
            cos, sin = math.cos(turn), math.sin(turn)
            base = (-length / _ROOT3 * cos, -length / _ROOT3 * sin)

            def corner(*terms: tuple[float, Point], base: Point = base) -> Point:
                return (
                    base[0] + math.fsum(f * v[0] for f, v in terms),
                    base[1] + math.fsum(f * v[1] for f, v in terms),
                )

            beams.append(
                (
                    corner((-width, along)),
                    corner((width, left)),
                    corner((length, along), (width, left)),
                    corner((length, along)),
                    corner((length, along), (width, right)),
                    corner((width, right)),
                )
            )
        return tuple(beams)

    @override
    def build(self) -> Design:
        beams = self.beams()
        pieces = [
            piece for k, beam in enumerate(beams) for piece in _outside(beam, beams[(k + 1) % 3])
        ]
        return Design(
            tuple(Path(piece) for piece in _fitted(pieces, self.size, self.center)),
            meta=spec(self),
        )


# --- the staircase ----------------------------------------------------------


@register("illusion.penrose-stairs", family="illusion")
@dataclass(frozen=True, slots=True)
class PenroseStairs(Motif):
    """The endless staircase: four flights, every step up, back where you began.

    Built in space and then flattened, rather than drawn flat and fudged. Four
    flights of equal step count run round a rectangle, each step rising by
    ``rise``; after a full circuit the walk has failed to close by exactly
    ``(t, t, t)``, and an isometric view sends that to nothing. Two opposite
    flights have to be longer than the other two by four times the rise for the
    error to come out equal on all three axes -- which is why a real drawing of
    this staircase is never quite square.

    Parameters
    ----------
    steps : int, optional
        Steps per flight.
    rise : float, optional
        Height of one step, in units of the short flight's tread.
    width : float, optional
        How deep each tread is, in the same units.
    size : float, optional
        Width of the finished figure.
    center : (float, float), optional
        Middle of the figure.
    """

    steps: int = 5
    rise: float = 0.4
    width: float = 1.8
    size: float = 280.0
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        owner = type(self).__name__
        _check_size(owner, self.size)
        _check_size(owner, self.rise, name="rise")
        _check_size(owner, self.width, name="width")
        if not 1 <= self.steps <= _MAX_STEPS:
            raise ValueError(f"{owner} steps must be in [1, {_MAX_STEPS}], got {self.steps}")

    def walk(self) -> tuple[Spatial, ...]:
        """Return the corners of the stepped band's outer edge, in space.

        Three points per step: the foot of the riser, its top, and the far end
        of the tread.
        """
        far = 1.0 + 4.0 * self.rise
        runs = ((far, 0.0), (0.0, far), (-1.0, 0.0), (0.0, -1.0))
        here: Spatial = (0.0, 0.0, 0.0)
        corners: list[Spatial] = []
        for dx, dy in runs:
            for _ in range(self.steps):
                top = (here[0], here[1], here[2] + self.rise)
                onward = (top[0] + dx, top[1] + dy, top[2])
                corners.extend((here, top, onward))
                here = onward
        return tuple(corners)

    @override
    def build(self) -> Design:
        # Inward is the walking direction turned a quarter turn to the left,
        # so the treads always reach into the middle of the loop.
        inward = ((0.0, 1.0), (-1.0, 0.0), (0.0, -1.0), (1.0, 0.0))
        outer = self.walk()
        per_flight = 3 * self.steps
        back: list[Spatial] = []
        for index, (x, y, z) in enumerate(outer):
            ix, iy = inward[index // per_flight]
            back.append((x + ix * self.width, y + iy * self.width, z))

        flat = [_isometric(p) for p in outer]
        flat_back = [_isometric(p) for p in back]
        # The two sides of every tread, which is what makes each step read as
        # a solid slab rather than as a line on a folded ribbon.
        sides = [
            (flat[i], flat_back[i])
            for i in range(len(flat))
            if i % 3 in (1, 2)  # the top of the riser and the far end of the tread
        ]
        shapes = _fitted([flat, flat_back, *sides], self.size, self.center)
        return Design(
            (
                Path(shapes[0], closed=True),
                Path(shapes[1], closed=True),
                *(Path(side) for side in shapes[2:]),
            ),
            meta=spec(self),
        )


# --- cubes ------------------------------------------------------------------


def _cube_edges(half: float, offset: Point) -> tuple[tuple[Point, ...], ...]:
    """Return the twelve edges of an obliquely drawn cube: front, back, joins."""
    front = ((-half, -half), (half, -half), (half, half), (-half, half))
    back = tuple((x + offset[0], y + offset[1]) for x, y in front)
    edges = [(front[i], front[(i + 1) % 4]) for i in range(4)]
    edges += [(back[i], back[(i + 1) % 4]) for i in range(4)]
    edges += [(front[i], back[i]) for i in range(4)]
    return tuple(edges)


def _crossings_of(edges: Sequence[Sequence[Point]]) -> list[tuple[int, int, Point]]:
    """Return where two of these segments cross, strictly between their ends."""
    found: list[tuple[int, int, Point]] = []
    for i, (a, b) in enumerate(edges):
        for j in range(i + 1, len(edges)):
            c, d = edges[j]
            ux, uy = b[0] - a[0], b[1] - a[1]
            vx, vy = d[0] - c[0], d[1] - c[1]
            det = vx * uy - vy * ux
            if det == 0.0:
                continue
            rx, ry = c[0] - a[0], c[1] - a[1]
            here = (vx * ry - vy * rx) / det
            there = (ux * ry - uy * rx) / det
            if 1e-9 < here < 1.0 - 1e-9 and 1e-9 < there < 1.0 - 1e-9:
                found.append((i, j, (a[0] + here * ux, a[1] + here * uy)))
    return found


def _gapped(edge: Sequence[Point], holes: Sequence[Point], gap: float) -> list[Path]:
    """Return an edge cut into strokes, with a gap around each hole."""
    start, end = edge
    span = math.dist(start, end)
    cuts = sorted(math.dist(start, hole) for hole in holes)
    runs: list[tuple[float, float]] = []
    cursor = 0.0
    for at in cuts:
        if at - gap > cursor:
            runs.append((cursor, at - gap))
        cursor = max(cursor, at + gap)
    if cursor < span:
        runs.append((cursor, span))

    def along(distance: float) -> Point:
        t = distance / span
        return (start[0] + t * (end[0] - start[0]), start[1] + t * (end[1] - start[1]))

    return [Path((along(first), along(second))) for first, second in runs]


@dataclass(frozen=True, slots=True)
class _CubeBase(Motif):
    """Shared geometry for the two wireframe cubes drawn in oblique projection."""

    size: float = 180.0
    depth: float = 0.45
    angle: float = math.pi / 4.0
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        owner = type(self).__name__
        _check_size(owner, self.size)
        if not 0.0 < self.depth < 1.0:
            raise ValueError(
                f"{owner} depth must be strictly between 0 and 1, got {self.depth}; "
                f"at 1 the far face sits on the near face's corner and the cube "
                f"stops crossing itself"
            )
        if not 0.0 < self.angle < math.pi / 2.0:
            raise ValueError(
                f"{owner} angle must be strictly between 0 and pi/2 radians, got "
                f"{self.angle}; outside that the far face is not behind and to one side"
            )

    def edges(self) -> tuple[tuple[Point, ...], ...]:
        """Return the twelve edges: near face, far face, then the four joins."""
        offset = (self.depth * math.cos(self.angle), self.depth * math.sin(self.angle))
        return _fitted(_cube_edges(0.5, offset), self.size, self.center)


@register("illusion.necker-cube", family="illusion")
@dataclass(frozen=True, slots=True)
class NeckerCube(_CubeBase):
    """A wireframe cube with nothing to say which face is in front.

    All twelve edges drawn, none broken. Louis Necker noticed in 1832 that
    the same drawing flips between two solid cubes as you look at it, and it
    does so because nothing in it is wrong -- the drawing is simply true of
    both.

    Parameters
    ----------
    size : float, optional
        Width of the finished figure.
    depth : float, optional
        How far the far face is offset, as a fraction of the near face's width.
    angle : float, optional
        Which way it is offset, in radians.
    center : (float, float), optional
        Middle of the figure.
    """

    @override
    def build(self) -> Design:
        return Design(tuple(Path(edge) for edge in self.edges()), meta=spec(self))


@register("illusion.impossible-cube", family="illusion")
@dataclass(frozen=True, slots=True)
class ImpossibleCube(_CubeBase):
    """The same cube, told two contradictory things about which face is nearer.

    The near and far faces cross each other twice. At one crossing the far edge
    is broken, which says the near face is in front; at the other the near edge
    is broken, which says the opposite. Either break alone would be an ordinary
    solid cube; together they are Escher's.

    Parameters
    ----------
    size, depth, angle, center
        As :class:`NeckerCube`.
    gap : float, optional
        Length of the break, as a fraction of the size.
    """

    gap: float = 0.06

    def __post_init__(self) -> None:
        # Named rather than ``super()``: a slotted dataclass is a different
        # class object from the one the decorator was applied to, and the
        # no-argument ``super()`` cannot see that.
        _CubeBase.__post_init__(self)
        if not 0.0 < self.gap < 0.25:
            raise ValueError(
                f"{type(self).__name__} gap must be strictly between 0 and 0.25, got {self.gap}"
            )

    @override
    def build(self) -> Design:
        edges = self.edges()
        # Exactly two, always: a depth below 1 and an angle inside the right
        # angle put the far face's left and bottom edges across the near
        # face's top and right ones, and nothing else can meet.
        first, second = sorted(_crossings_of(edges), key=lambda c: c[2])
        # Near-face edges are 0..3 and far-face edges 4..7, so the lower index
        # of each pair is the near one. Break the far edge at one crossing and
        # the near edge at the other, and the cube contradicts itself.
        holes: dict[int, list[Point]] = {
            first[1]: [first[2]],  # the far edge yields here, as it should
            second[0]: [second[2]],  # and the near edge yields here, as it must not
        }

        paths: list[Path] = []
        for index, edge in enumerate(edges):
            if index in holes:
                paths.extend(_gapped(edge, holes[index], self.gap * self.size))
            else:
                paths.append(Path(edge))
        return Design(tuple(paths), meta=spec(self))


# --- interference -----------------------------------------------------------


@register("illusion.cafe-wall", family="illusion")
@dataclass(frozen=True, slots=True)
class CafeWall(Motif):
    """Parallel mortar lines that refuse to look parallel.

    Rows of tiles, every other row shifted sideways, with a line of mortar
    between them. The dark tiles are hatched rather than filled, which is what
    a plotter can draw -- and the illusion needs only the contrast, not the
    ink. Every mortar line is exactly horizontal; none of them looks it.

    Named for a cafe in Bristol whose tiling did this to passers-by.

    Parameters
    ----------
    cols, rows : int, optional
        How many tiles across and down.
    size : float, optional
        Side of one tile.
    mortar : float, optional
        Gap between rows.
    shift : float, optional
        How far every other row is displaced, as a fraction of a tile. The
        illusion is strongest around a quarter to a half.
    hatch : int, optional
        Lines drawn across each dark tile.
    center : (float, float), optional
        Middle of the wall.
    """

    cols: int = 8
    rows: int = 6
    size: float = 40.0
    mortar: float = 3.0
    shift: float = 0.5
    hatch: int = 4
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        owner = type(self).__name__
        _check_size(owner, self.size)
        if self.cols < 1 or self.rows < 1:
            raise ValueError(f"{owner} needs at least one tile, got {self.cols}x{self.rows}")
        if self.cols * self.rows > _MAX_TILES:
            raise ValueError(
                f"{owner} would draw {self.cols * self.rows} tiles (limit {_MAX_TILES})"
            )
        if self.mortar < 0.0:
            raise ValueError(f"{owner} mortar must be >= 0, got {self.mortar}")
        if not 0.0 <= self.shift <= 1.0:
            raise ValueError(f"{owner} shift must be in [0, 1], got {self.shift}")
        if self.hatch < 1:
            raise ValueError(f"{owner} hatch must be >= 1, got {self.hatch}")

    @override
    def build(self) -> Design:
        step = self.size + self.mortar
        cx, cy = self.center
        left = cx - self.cols * self.size / 2.0
        bottom = cy - self.rows * step / 2.0
        paths: list[Path] = []
        for row in range(self.rows):
            y = bottom + row * step
            offset = (row % 2) * self.shift * self.size
            for col in range(self.cols):
                if (col + row) % 2:
                    continue  # the light tiles are the paper
                x = left + col * self.size + offset
                paths.append(
                    Path(
                        ((x, y), (x + self.size, y), (x + self.size, y + self.size),
                         (x, y + self.size)),
                        closed=True,
                    )
                )  # fmt: skip
                paths.extend(
                    Path(((x, y + self.size * (k + 1) / (self.hatch + 1)),
                          (x + self.size, y + self.size * (k + 1) / (self.hatch + 1))))
                    for k in range(self.hatch)
                )  # fmt: skip
            if row:
                # The mortar itself: dead straight, and the reason to look.
                line = y - self.mortar / 2.0
                paths.append(Path(((left, line), (left + self.cols * self.size, line))))
        return Design(tuple(paths), meta=spec(self))


@register("illusion.moire", family="illusion", example={"kind": "rings"})
@dataclass(frozen=True, slots=True)
class MoirePattern(Motif):
    """Two regular patterns laid over each other, and the fringes between them.

    Nothing draws the fringes. They are where the two patterns nearly agree,
    and they move much faster than either pattern does -- shift one grating by
    a hair and the bands sweep across the whole figure.

    Parameters
    ----------
    kind : str, optional
        ``"rings"`` for two sets of concentric circles, ``"lines"`` for two
        straight gratings, ``"radial"`` for two fans of rays.
    count : int, optional
        Lines or circles in each of the two patterns.
    spacing : float, optional
        Distance between neighbouring lines or circles.
    offset : float, optional
        How far apart the two patterns' middles are.
    angle : float, optional
        How far the second pattern is turned, in radians. A very small angle
        gives very wide fringes. Concentric circles look the same however far
        you turn them, so ``"rings"`` ignores it and works on ``offset`` alone.
    center : (float, float), optional
        Middle of the first pattern.
    """

    kind: MoireKind = "rings"
    count: int = 34
    spacing: float = 6.0
    offset: float = 26.0
    angle: float = 0.06
    center: Point = (0.0, 0.0)

    def __post_init__(self) -> None:
        owner = type(self).__name__
        _check_size(owner, self.spacing, name="spacing")
        if self.kind not in ("rings", "lines", "radial"):
            raise ValueError(
                f"{owner} kind must be 'rings', 'lines' or 'radial', got {self.kind!r}"
            )
        if not 1 <= self.count <= _MAX_LINES:
            raise ValueError(f"{owner} count must be in [1, {_MAX_LINES}], got {self.count}")

    def family(self, at: Point, turn: float) -> tuple[Path, ...]:
        """Return one of the two patterns, placed and turned."""
        reach = self.count * self.spacing
        cos, sin = math.cos(turn), math.sin(turn)

        def place(x: float, y: float) -> Point:
            return (at[0] + x * cos - y * sin, at[1] + x * sin + y * cos)

        match self.kind:
            case "rings":
                return tuple(
                    Path(arc_points(at, (i + 1) * self.spacing, 0.0, math.tau)[:-1], closed=True)
                    for i in range(self.count)
                )
            case "lines":
                return tuple(
                    Path((place((i - self.count / 2.0) * self.spacing, -reach),
                          place((i - self.count / 2.0) * self.spacing, reach)))
                    for i in range(self.count)
                )  # fmt: skip
            case _:
                return tuple(
                    Path(
                        (
                            place(0.0, 0.0),
                            place(
                                reach * math.cos(math.tau * i / self.count),
                                reach * math.sin(math.tau * i / self.count),
                            ),
                        )
                    )
                    for i in range(self.count)
                )

    @override
    def build(self) -> Design:
        cx, cy = self.center
        second = (cx + self.offset, cy)
        paths = self.family(self.center, 0.0) + self.family(second, self.angle)
        return Design(paths, meta=spec(self))
