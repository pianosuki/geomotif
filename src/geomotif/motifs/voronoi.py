"""Voronoi diagrams, the Delaunay triangulation, and Lloyd's relaxation.

Scatter some points and ask, of every place on the page, "which of you is
nearest?". The answer divides the plane into one convex cell per point -- the
Voronoi diagram -- and joining the points whose cells touch gives the Delaunay
triangulation, the same figure read the other way round.

Everything in this module is built from one construction: **a site's cell is
the region rectangle, clipped by the perpendicular bisector between that site
and each of its Delaunay neighbours**. No other bisector reaches it, which is
what makes this cheap: the neighbours are a handful rather than the whole set,
and one triangulation answers every question asked below.

The triangulation itself comes from scipy's Qhull binding, which makes this
the one module in the catalog behind an optional dependency::

    pip install 'geomotif[scipy]'

That dependency is real rather than a convenience. Points sharing a circle --
a plain square grid, which this library will happily hand you -- are exactly
where a hand-rolled incremental triangulator has to break a tie arbitrarily
and can then contradict itself; getting that right is Qhull's day job.

scipy is imported when a design is *built*, not when this module is imported,
so these motifs can still be listed, described and reported as unavailable on
a machine without it. They carry ``requires="scipy"`` in the registry for
exactly that reason.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, override

from ..bases import PolygonMotif, SegmentMotif
from ..core.motif import Motif
from ..core.registry import register, spec
from ..core.transform import jitter
from ..core.types import Bounds, Design
from .primitives import PointGrid

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from ..core.types import Point

__all__ = ["Delaunay", "LloydRelaxation", "Voronoi", "VoronoiCells"]

#: Ceiling on the number of sites. Far above any plottable design, and far
#: below anything that would keep Lloyd's relaxation running for minutes.
_MAX_SITES = 5_000

#: Ceiling on relaxation passes. A centroidal diagram settles in a handful;
#: hundreds mean a typo.
_MAX_PASSES = 200

#: How far the derived region reaches past the points, as a fraction of their
#: larger extent. Without it the outermost sites get a sliver of a cell cut
#: off at their own coordinates, which reads as a mistake rather than an edge.
_MARGIN = 0.1

#: Two cells that share a corner each compute it from a different sequence of
#: clips, so their answers differ in the last bits -- measured at 2e-12 on a
#: 240-unit box. Corners closer than this fraction of the region's size are
#: the same corner. It sits far above that disagreement and far below any
#: feature anyone would draw.
_WELD = 1e-9

#: The example point set: a lattice shaken loose by half its own pitch. Loose
#: enough that no two cells are alike, tight enough that none is a sliver.
_EXAMPLE_POINTS = tuple(
    jitter(PointGrid(columns=6, rows=6, dx=42.0, dy=42.0).build(), 20.0, seed=7)
)

#: The same lattice shaken until nothing is left of it, which is what a
#: clumped scatter looks like -- and what Lloyd's relaxation is for.
_EXAMPLE_SCATTER = tuple(
    jitter(PointGrid(columns=6, rows=6, dx=42.0, dy=42.0).build(), 38.0, seed=11)
)


def _sites(points: Sequence[Point], *, owner: str) -> tuple[Point, ...]:
    """Validate a point set and normalize it to a tuple of finite float pairs.

    A tuple rather than whatever was passed in because these are the key to
    the triangulation memo below, and a list cannot be one.
    """
    sites: list[Point] = []
    for index, point in enumerate(points):
        try:
            x, y = point
        except (TypeError, ValueError):
            raise TypeError(
                f"{owner} points[{index}] must be an (x, y) pair, got {point!r}"
            ) from None
        fx, fy = float(x), float(y)
        if not math.isfinite(fx) or not math.isfinite(fy):
            raise ValueError(f"{owner} points[{index}] must be finite, got ({fx}, {fy})")
        sites.append((fx, fy))

    if len(sites) < 3:
        raise ValueError(
            f"{owner} needs at least 3 points to triangulate, got {len(sites)}; "
            f"two points have no triangle between them"
        )
    if len(sites) > _MAX_SITES:
        raise ValueError(
            f"{owner} was given {len(sites)} points (limit {_MAX_SITES}); "
            f"a diagram that dense is not a drawing"
        )
    return tuple(sites)


def _triangles(sites: tuple[Point, ...]) -> tuple[tuple[int, int, int], ...]:
    """Return the Delaunay triangles of ``sites``, as index triples.

    scipy is imported here rather than at module scope on purpose -- see the
    module docstring: listing a motif must not require its dependency.
    """
    try:
        from scipy.spatial import Delaunay as Triangulation
        from scipy.spatial import QhullError
    except ImportError:
        raise ImportError(
            "geomotif.motifs.voronoi requires scipy. Install it with: pip install 'geomotif[scipy]'"
        ) from None

    try:
        mesh = Triangulation(sites)
    except QhullError as exc:
        # Qhull's own wording is about flat initial simplices, which is true
        # but says nothing about what the caller passed in.
        raise ValueError(
            f"cannot triangulate these {len(sites)} points: they lie on one line, "
            f"or too nearly on one to tell apart. Three points off a common line "
            f"are the least a triangulation can be built from"
        ) from exc

    return tuple((int(a), int(b), int(c)) for a, b, c in mesh.simplices)


def _neighbours(
    count: int, triangles: Iterable[tuple[int, int, int]]
) -> tuple[frozenset[int], ...]:
    """Return, for each site, the sites it shares a Delaunay edge with."""
    near: list[set[int]] = [set() for _ in range(count)]
    for a, b, c in triangles:
        for i, j in ((a, b), (b, c), (c, a)):
            near[i].add(j)
            near[j].add(i)
    return tuple(frozenset(group) for group in near)


def _nearer(polygon: Sequence[Point], site: Point, other: Point) -> tuple[Point, ...]:
    """Return the part of ``polygon`` that is nearer to ``site`` than to ``other``.

    Sutherland-Hodgman against a single half-plane. Both the polygon and the
    half-plane are convex, so the result is one convex loop and never breaks
    into pieces.
    """
    ax, ay = site
    bx, by = other
    # Nearer to a than to b is |p - a|^2 <= |p - b|^2, and the squared terms
    # cancel: what is left is one linear test.
    nx, ny = bx - ax, by - ay
    limit = (bx * bx + by * by - ax * ax - ay * ay) / 2.0

    kept: list[Point] = []
    for p, q in itertools.pairwise((*polygon, polygon[0])):
        depth_p = limit - (nx * p[0] + ny * p[1])
        depth_q = limit - (nx * q[0] + ny * q[1])
        if depth_p >= 0.0:
            kept.append(p)
        # Strictly opposite signs, so the two depths cannot cancel and the
        # division below is safe.
        if (depth_p >= 0.0) != (depth_q >= 0.0):
            share = depth_p / (depth_p - depth_q)
            kept.append((p[0] + (q[0] - p[0]) * share, p[1] + (q[1] - p[1]) * share))
    return tuple(kept)


def _tidied(polygon: Sequence[Point], tolerance: float) -> tuple[Point, ...]:
    """Drop corners that repeat the one before, including around the seam.

    A clip line running exactly through a corner keeps that corner and then
    computes the crossing, which is the same place twice.
    """
    kept: list[Point] = []
    for point in polygon:
        if not kept or math.dist(kept[-1], point) > tolerance:
            kept.append(point)
    while len(kept) > 1 and math.dist(kept[0], kept[-1]) <= tolerance:
        kept.pop()
    return tuple(kept)


def _region_for(sites: tuple[Point, ...], region: Bounds | None) -> Bounds:
    """Return the region to clip against, deriving one from the sites if needed."""
    if region is not None:
        return region
    box = Bounds.from_points(sites)
    return box.padded(_MARGIN * max(box.width, box.height))


@lru_cache(maxsize=16)
def _cells(sites: tuple[Point, ...], region: Bounds) -> tuple[tuple[Point, ...], ...]:
    """Return one convex cell per site, clipped to ``region``.

    A site whose cell falls entirely outside the region gets an empty tuple
    rather than being dropped, so the result stays aligned with ``sites``.

    Memoized because the segment machinery asks for a design's nodes and its
    edges in two separate calls, and Lloyd's relaxation asks again per pass:
    without this the triangulation would be rebuilt each time it is consulted
    rather than each time it changes.
    """
    rectangle = (
        (region.min_x, region.min_y),
        (region.max_x, region.min_y),
        (region.max_x, region.max_y),
        (region.min_x, region.max_y),
    )
    tolerance = _WELD * max(region.width, region.height, 1.0)
    near = _neighbours(len(sites), _triangles(sites))

    cells: list[tuple[Point, ...]] = []
    for index, site in enumerate(sites):
        cell: tuple[Point, ...] = rectangle
        for other in sorted(near[index]):
            cell = _nearer(cell, site, sites[other])
            if not cell:
                break
        cells.append(_tidied(cell, tolerance) if len(cell) > 2 else ())
    return tuple(cells)


def _centroid(polygon: Sequence[Point]) -> Point:
    """Return the center of area of a simple polygon.

    A clip that pinches a cell down to a line leaves corners but no area to
    take a center of. The mean of those corners is the only answer available
    and is the right one, so that case is answered rather than refused.
    """
    twice_area = 0.0
    x_moment = 0.0
    y_moment = 0.0
    for a, b in itertools.pairwise((*polygon, polygon[0])):
        cross = a[0] * b[1] - b[0] * a[1]
        twice_area += cross
        x_moment += (a[0] + b[0]) * cross
        y_moment += (a[1] + b[1]) * cross
    if twice_area == 0.0:
        count = float(len(polygon))
        return (
            math.fsum(x for x, _ in polygon) / count,
            math.fsum(y for _, y in polygon) / count,
        )
    return (x_moment / (3.0 * twice_area), y_moment / (3.0 * twice_area))


def _shrunk(polygon: Sequence[Point], inset: float) -> tuple[Point, ...]:
    """Return ``polygon`` pulled toward its own center of area by ``inset``."""
    if inset == 0.0:
        return tuple(polygon)
    cx, cy = _centroid(polygon)
    keep = 1.0 - inset
    return tuple((cx + (x - cx) * keep, cy + (y - cy) * keep) for x, y in polygon)


def _welded(
    cells: Iterable[Sequence[Point]], tolerance: float
) -> tuple[tuple[Point, ...], tuple[tuple[int, ...], ...]]:
    """Return one shared corner table plus each cell rewritten as indices into it.

    Neighbouring buckets are probed as well as the exact one: a rounding key
    alone would split a pair of corners that agree to within ``tolerance``
    but happen to fall either side of a bucket edge, and that pair is what
    tells the two cells they share an edge.
    """
    corners: list[Point] = []
    buckets: dict[tuple[int, int], list[int]] = {}

    def index_of(point: Point) -> int:
        key = (round(point[0] / tolerance), round(point[1] / tolerance))
        for dx, dy in itertools.product((-1, 0, 1), repeat=2):
            for found in buckets.get((key[0] + dx, key[1] + dy), ()):
                if math.dist(corners[found], point) <= tolerance:
                    return found
        buckets.setdefault(key, []).append(len(corners))
        corners.append(point)
        return len(corners) - 1

    loops = tuple(tuple(index_of(point) for point in cell) for cell in cells if len(cell) > 2)
    return tuple(corners), loops


def _relaxed(sites: tuple[Point, ...], region: Bounds, passes: int) -> tuple[Point, ...]:
    """Move every site to the middle of its own cell, ``passes`` times over.

    A site clipped out of the region has no middle to move to and stays
    where it is: the set comes back the size it went in, rather than
    quietly losing its outliers.
    """
    for _ in range(passes):
        cells = _cells(sites, region)
        sites = tuple(
            _centroid(cell) if len(cell) > 2 else site
            for site, cell in zip(sites, cells, strict=True)
        )
    return sites


@register(
    "voronoi.delaunay", family="voronoi", requires="scipy", example={"points": _EXAMPLE_POINTS}
)
@dataclass(frozen=True, slots=True)
class Delaunay(SegmentMotif):
    """The triangulation that joins points whose Voronoi cells touch.

    Of all the ways to cut a point set into triangles, this is the one that
    avoids thin ones: no point ever falls inside another triangle's
    circumcircle, which maximizes the smallest angle in the whole mesh. That
    is why it is what meshers, terrain models and low-poly renderers use, and
    why a scatter drawn this way reads as a surface rather than a tangle.

    Parameters
    ----------
    points : sequence of (float, float)
        The sites to triangulate. At least three, not all on one line.
    """

    points: Sequence[Point]

    def __post_init__(self) -> None:
        object.__setattr__(self, "points", _sites(self.points, owner=type(self).__name__))

    @override
    def nodes(self) -> Sequence[Point]:
        return self.points

    @override
    def edges(self) -> Iterable[tuple[int, int]]:
        # Every triangle names its three sides; the shared ones arrive twice
        # and the segment machinery drops the repeat.
        for a, b, c in _triangles(tuple(self.points)):
            yield from ((a, b), (b, c), (c, a))


@register(
    "voronoi.diagram", family="voronoi", requires="scipy", example={"points": _EXAMPLE_POINTS}
)
@dataclass(frozen=True, slots=True)
class Voronoi(SegmentMotif):
    """The map of which point is nearest, drawn as its borders.

    Each border is drawn once, however many cells meet along it, so the
    result is a plotter's diagram rather than a stack of outlines --
    ``merge=True`` then chains those borders into long strokes.
    :class:`VoronoiCells` is the same figure when each region matters more
    than the lines between them.

    Parameters
    ----------
    points : sequence of (float, float)
        The sites. At least three, not all on one line.
    region : Bounds, optional
        Where to cut off the cells of the outermost sites, whose borders
        otherwise run to infinity. Defaults to the points' own extent, grown
        by a tenth.
    """

    points: Sequence[Point]
    region: Bounds | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "points", _sites(self.points, owner=type(self).__name__))

    def cells(self) -> tuple[tuple[Point, ...], ...]:
        """Return one convex cell per site, clipped to the region."""
        sites = tuple(self.points)
        return _cells(sites, _region_for(sites, self.region))

    def corners(self) -> tuple[tuple[Point, ...], tuple[tuple[int, ...], ...]]:
        """Return the shared corner table and each cell as indices into it."""
        sites = tuple(self.points)
        region = _region_for(sites, self.region)
        return _welded(_cells(sites, region), _WELD * max(region.width, region.height, 1.0))

    @override
    def nodes(self) -> Sequence[Point]:
        return self.corners()[0]

    @override
    def edges(self) -> Iterable[tuple[int, int]]:
        for loop in self.corners()[1]:
            yield from itertools.pairwise((*loop, loop[0]))


@register(
    "voronoi.cells",
    family="voronoi",
    requires="scipy",
    example={"points": _EXAMPLE_POINTS, "inset": 0.12},
)
@dataclass(frozen=True, slots=True)
class VoronoiCells(PolygonMotif):
    """The same map, drawn one closed region at a time.

    Each cell is its own closed path, so a border shared by two of them is
    drawn twice -- the price of having each region be a thing in itself,
    which is what you want to fill, color, or cut. ``inset`` pulls every
    cell back from its neighbours and gives the cracked-mud look the diagram
    is usually drawn for.

    Parameters
    ----------
    points : sequence of (float, float)
        The sites. At least three, not all on one line.
    region : Bounds, optional
        Where to cut off the outermost cells. Defaults to the points' own
        extent, grown by a tenth.
    inset : float, optional
        Fraction of the way each cell is pulled toward its own middle.
        ``0`` leaves the cells touching; ``0.5`` halves them.
    """

    points: Sequence[Point]
    region: Bounds | None = None
    inset: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "points", _sites(self.points, owner=type(self).__name__))
        if not 0.0 <= self.inset < 1.0:
            raise ValueError(f"inset must be in [0, 1), got {self.inset}")

    @override
    def outlines(self) -> Iterable[Sequence[Point]]:
        sites = tuple(self.points)
        cells = _cells(sites, _region_for(sites, self.region))
        # A site whose cell falls outside the region is simply not drawn. No
        # guard against every site doing so: the diagram covers the whole
        # plane, so wherever the region is put, some site owns it. Only a
        # region with no area at all leaves nothing, and the polygon base
        # says so already.
        return [_shrunk(cell, self.inset) for cell in cells if len(cell) > 2]


@register(
    "voronoi.lloyd",
    family="voronoi",
    requires="scipy",
    example={"points": _EXAMPLE_SCATTER, "iterations": 6},
)
@dataclass(frozen=True, slots=True)
class LloydRelaxation(Motif):
    """Points nudged toward the middle of their own cells, over and over.

    Lloyd's algorithm, and the cheapest way to turn a clumped scatter into an
    even one that still looks unplanned. Each pass replaces every point with
    the center of area of its Voronoi cell; a point in a crowd is off-center
    in its own cell and drifts away from the crowd, a point in a gap is
    already central and stays. The fixed point of that -- reached in a
    handful of passes -- is a centroidal diagram, which is what stippling,
    dot art and object scattering all want.

    Produces loose points, not strokes: the result is the input to the other
    motifs here rather than a drawing of its own.

    Parameters
    ----------
    points : sequence of (float, float)
        The sites to even out. At least three, not all on one line.
    iterations : int, optional
        Passes to run. Most of the work happens in the first three.
    region : Bounds, optional
        The area the points are kept inside. Defaults to their own extent,
        grown by a tenth, and is fixed at the start so the set cannot creep.
    """

    points: Sequence[Point]
    iterations: int = 3
    region: Bounds | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "points", _sites(self.points, owner=type(self).__name__))
        if not 0 <= self.iterations <= _MAX_PASSES:
            raise ValueError(f"iterations must be in [0, {_MAX_PASSES}], got {self.iterations}")

    def relaxed(self) -> tuple[Point, ...]:
        """Return the points after the relaxation, ready to feed another motif."""
        sites = tuple(self.points)
        return _relaxed(sites, _region_for(sites, self.region), self.iterations)

    @override
    def build(self) -> Design:
        return Design(points=self.relaxed(), meta=spec(self))
