"""Polyhedra, flattened onto the page.

Three dimensions reach the plotter the only way they can: as a wireframe. A
solid here is a list of corners in space and a rule for which of them are
joined; :class:`Projection` turns that into two dimensions, and the rest is
the segment machinery every other graph motif already uses.

The rule for which corners are joined is the same one for all six regular and
semi-regular solids in this module: **join every pair of corners that are as
close together as any pair gets**. On a shape whose corners are all alike that
is exactly its edge set, so the whole catalog below is six tables of numbers
and nothing else. :class:`Polyhedron` is for the shapes that are not like
that, and takes its edges as given.

Nothing is hidden. A wireframe drawn complete is what a plotter can draw and
what the eye can read as a solid seen through -- and it is also, not by
accident, what makes :class:`~geomotif.motifs.illusions.NeckerCube` ambiguous.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, Literal, override

from ..bases import SegmentMotif
from ..core.registry import register

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from ..core.types import Point

__all__ = [
    "Cube",
    "Dodecahedron",
    "Icosahedron",
    "Octahedron",
    "Polyhedron",
    "PolyhedronBase",
    "Projection",
    "Tetrahedron",
    "TruncatedIcosahedron",
]

type Vertex = tuple[float, float, float]

type View = Literal["orthographic", "isometric", "perspective"]

_PHI = (1.0 + math.sqrt(5.0)) / 2.0

#: The orientation that makes the three axes leave a corner at equal angles
#: and equal lengths, which is what "isometric" means. Turn a cube by these
#: and its three visible faces come out identical rhombi.
_ISOMETRIC = (math.pi / 4.0, math.atan(1.0 / math.sqrt(2.0)))

#: Ceiling on the corner count, so a mistyped table raises rather than
#: spending minutes in the quadratic search for the shortest edge.
_MAX_CORNERS = 2_000


def _turned(vertex: Vertex, yaw: float, pitch: float, roll: float) -> Vertex:
    """Return ``vertex`` turned about y, then x, then the line of sight."""
    x, y, z = vertex
    cos, sin = math.cos(yaw), math.sin(yaw)
    x, z = x * cos + z * sin, z * cos - x * sin
    cos, sin = math.cos(pitch), math.sin(pitch)
    y, z = y * cos - z * sin, y * sin + z * cos
    cos, sin = math.cos(roll), math.sin(roll)
    x, y = x * cos - y * sin, x * sin + y * cos
    return (x, y, z)


@dataclass(frozen=True, slots=True)
class Projection:
    """How a corner in space becomes a point on the page.

    Parameters
    ----------
    kind : str, optional
        ``"isometric"`` for the draughtsman's view, in which the three axes
        leave a corner at equal angles; ``"orthographic"`` for a straight
        drop of the depth, which is what makes a cube read as a square until
        you turn it; ``"perspective"`` for a view from a finite distance, in
        which the far side of the solid comes out smaller.
    yaw, pitch, roll : float, optional
        Extra turns applied after the base orientation: about the vertical,
        about the horizontal, and about the line of sight.
    distance : float, optional
        How far the eye is from the middle, in circumradii. Only
        ``"perspective"`` uses it, and it must be greater than 1 or the eye
        would be inside the solid.
    """

    kind: View = "isometric"
    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0
    distance: float = 3.0

    def __post_init__(self) -> None:
        if self.kind not in ("orthographic", "isometric", "perspective"):
            raise ValueError(
                f"Projection kind must be 'orthographic', 'isometric' or "
                f"'perspective', got {self.kind!r}"
            )
        if self.kind == "perspective" and self.distance <= 1.0:
            raise ValueError(
                f"Projection distance must be > 1 circumradius, got {self.distance}; "
                f"any less and the eye is inside the solid"
            )

    def oriented(self, vertex: Vertex) -> Vertex:
        """Return ``vertex`` turned into the view's own frame, still in space."""
        if self.kind == "isometric":
            vertex = _turned(vertex, *_ISOMETRIC, 0.0)
        return _turned(vertex, self.yaw, self.pitch, self.roll)

    def __call__(self, vertex: Vertex) -> Point:
        """Return where ``vertex`` lands on the page."""
        x, y, z = self.oriented(vertex)
        if self.kind == "perspective":
            near = self.distance / (self.distance - z)
            return (x * near, y * near)
        return (x, y)


def _unit(vertices: Sequence[Vertex]) -> tuple[Vertex, ...]:
    """Return the corners scaled so the furthest sits one unit from the middle."""
    reach = max(math.sqrt(x * x + y * y + z * z) for x, y, z in vertices)
    return tuple((x / reach, y / reach, z / reach) for x, y, z in vertices)


def _shortest_pairs(vertices: Sequence[Vertex]) -> tuple[tuple[int, int], ...]:
    """Return every pair of corners as close together as any pair gets."""
    spans = [
        (math.dist(a, b), i, j)
        for i, a in enumerate(vertices)
        for j, b in enumerate(vertices)
        if i < j
    ]
    shortest = min(span for span, _, _ in spans)
    return tuple((i, j) for span, i, j in spans if span < shortest * (1.0 + 1e-9))


def _along(start: Vertex, end: Vertex, share: float) -> Vertex:
    """Return the point a given fraction of the way from one corner to another."""
    return (
        start[0] + share * (end[0] - start[0]),
        start[1] + share * (end[1] - start[1]),
        start[2] + share * (end[2] - start[2]),
    )


def _nearest(vertices: Sequence[Vertex]) -> tuple[tuple[int, int], ...]:
    """Return the edge set of a solid whose corners are all alike."""
    return _shortest_pairs(_unit(vertices))


def _cyclic(a: float, b: float, c: float) -> tuple[Vertex, ...]:
    """Return the three cyclic shufflings of one triple, and their sign changes.

    The compact way the regular solids are tabulated: ``(0, +-1, +-phi)`` and
    its shufflings is the icosahedron, and writing it out longhand would be
    twelve lines that hide the pattern.
    """

    def signs(value: float) -> tuple[float, ...]:
        # A zero has no sign to flip, and listing it twice would double half
        # the corners.
        return (1.0, -1.0) if value else (1.0,)

    return tuple(
        (sx * x, sy * y, sz * z)
        for x, y, z in ((a, b, c), (b, c, a), (c, a, b))
        for sx in signs(x)
        for sy in signs(y)
        for sz in signs(z)
    )


@dataclass(frozen=True, slots=True)
class PolyhedronBase(SegmentMotif, ABC):
    """Base for a solid: corners in space, joined and flattened onto the page.

    Implement :meth:`vertices`. :meth:`edges` joins every pair of corners that
    are as close together as any pair gets, which is the edge set of any solid
    whose corners are all alike; override it for one whose corners are not.

    Parameters
    ----------
    size : float, optional
        Diameter of the sphere the corners sit on. The drawing itself is
        usually smaller, since a projection foreshortens.
    projection : Projection, optional
        How space becomes the page.
    center : (float, float), optional
        Where the middle lands.
    """

    #: How many faces the solid has. Not used to draw it -- it is the third
    #: number in Euler's ``V - E + F = 2``, which is what the tests check the
    #: corner and edge tables against.
    faces: ClassVar[int] = 0

    size: float = field(default=200.0, kw_only=True)
    projection: Projection = field(default=Projection(), kw_only=True)
    center: Point = field(default=(0.0, 0.0), kw_only=True)

    def __post_init__(self) -> None:
        owner = type(self).__name__
        if self.size <= 0.0:
            raise ValueError(f"{owner} size must be > 0, got {self.size}")
        corners = self.vertices()
        if len(corners) < 2:
            raise ValueError(
                f"{owner}.vertices() returned {len(corners)} corner(s); a wireframe "
                f"needs at least 2"
            )
        if len(corners) > _MAX_CORNERS:
            raise ValueError(
                f"{owner} has {len(corners)} corners (limit {_MAX_CORNERS}); the "
                f"search for the shortest edge is quadratic in that number"
            )

    @abstractmethod
    def vertices(self) -> Sequence[Vertex]:
        """Return the corners, in any scale: they are normalized before drawing."""

    @override
    def nodes(self) -> Sequence[Point]:
        cx, cy = self.center
        scale = self.size / 2.0
        placed: list[Point] = []
        for corner in _unit(self.vertices()):
            x, y = self.projection(corner)
            placed.append((cx + x * scale, cy + y * scale))
        return placed

    @override
    def edges(self) -> Iterable[tuple[int, int]]:
        """Join every pair of corners as close together as any pair gets."""
        return _nearest(self.vertices())


@register("solid.tetrahedron", family="solid")
@dataclass(frozen=True, slots=True)
class Tetrahedron(PolyhedronBase):
    """Four triangles: the simplest solid there is, and its own dual."""

    faces: ClassVar[int] = 4

    @override
    def vertices(self) -> Sequence[Vertex]:
        # Alternate corners of a cube -- which is why the tetrahedron falls
        # out of the same table as everything else here.
        return ((1.0, 1.0, 1.0), (1.0, -1.0, -1.0), (-1.0, 1.0, -1.0), (-1.0, -1.0, 1.0))


@register("solid.cube", family="solid")
@dataclass(frozen=True, slots=True)
class Cube(PolyhedronBase):
    """Six squares. Dual to the octahedron, and the one everybody can check."""

    faces: ClassVar[int] = 6

    @override
    def vertices(self) -> Sequence[Vertex]:
        return tuple((x, y, z) for x in (-1.0, 1.0) for y in (-1.0, 1.0) for z in (-1.0, 1.0))


@register("solid.octahedron", family="solid")
@dataclass(frozen=True, slots=True)
class Octahedron(PolyhedronBase):
    """Eight triangles: a corner of the cube's every face, joined up."""

    faces: ClassVar[int] = 8

    @override
    def vertices(self) -> Sequence[Vertex]:
        return _cyclic(1.0, 0.0, 0.0)


@register("solid.dodecahedron", family="solid")
@dataclass(frozen=True, slots=True)
class Dodecahedron(PolyhedronBase):
    """Twelve pentagons, built on a cube and the golden ratio."""

    faces: ClassVar[int] = 12

    @override
    def vertices(self) -> Sequence[Vertex]:
        cube = tuple((x, y, z) for x in (-1.0, 1.0) for y in (-1.0, 1.0) for z in (-1.0, 1.0))
        return cube + _cyclic(0.0, 1.0 / _PHI, _PHI)


@register("solid.icosahedron", family="solid")
@dataclass(frozen=True, slots=True)
class Icosahedron(PolyhedronBase):
    """Twenty triangles: three golden rectangles at right angles to each other."""

    faces: ClassVar[int] = 20

    @override
    def vertices(self) -> Sequence[Vertex]:
        return _cyclic(0.0, 1.0, _PHI)


@register("solid.truncated-icosahedron", family="solid")
@dataclass(frozen=True, slots=True)
class TruncatedIcosahedron(PolyhedronBase):
    """The football: twelve pentagons and twenty hexagons.

    Made by cutting each of the icosahedron's twelve corners off a third of
    the way along every edge that meets it. The cut leaves a pentagon where
    the corner was and turns each triangle into a hexagon.
    """

    faces: ClassVar[int] = 32

    @override
    def vertices(self) -> Sequence[Vertex]:
        corners = Icosahedron().vertices()
        return tuple(
            _along(corners[i], corners[j], share)
            for i, j in _shortest_pairs(corners)
            for share in (1.0 / 3.0, 2.0 / 3.0)
        )


@register(
    "solid.polyhedron",
    family="solid",
    example={
        # A square pyramid: four corners alike and a fifth that is not, which
        # is exactly the case the nearest-pairs rule cannot handle.
        "corners": (
            (1.0, 0.0, -0.5),
            (0.0, 1.0, -0.5),
            (-1.0, 0.0, -0.5),
            (0.0, -1.0, -0.5),
            (0.0, 0.0, 1.1),
        ),
        "links": ((0, 1), (1, 2), (2, 3), (3, 0), (0, 4), (1, 4), (2, 4), (3, 4)),
    },
)
@dataclass(frozen=True, slots=True)
class Polyhedron(PolyhedronBase):
    """Any solid you like: your corners, your edges.

    For the shapes whose corners are not all alike, where "join the nearest
    pairs" is not the edge set -- a pyramid, a prism, a stellation, a
    scaffold. Leave ``links`` empty to fall back to joining the nearest pairs
    anyway.

    Parameters
    ----------
    corners : tuple of (float, float, float)
        The corners, in any scale.
    links : tuple of (int, int), optional
        Index pairs into ``corners``. Empty means the nearest pairs.
    """

    corners: tuple[Vertex, ...]
    links: tuple[tuple[int, int], ...] = ()

    @override
    def vertices(self) -> Sequence[Vertex]:
        return self.corners

    @override
    def edges(self) -> Iterable[tuple[int, int]]:
        # Calls the helper rather than ``super().edges()``: a slotted
        # dataclass is a different class object from the one the decorator
        # was applied to, and the no-argument ``super()`` cannot see that.
        return self.links or _nearest(self.corners)
