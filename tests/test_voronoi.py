import itertools
import math
import sys

import pytest

from geomotif.core.types import Bounds
from geomotif.motifs.voronoi import (
    _EXAMPLE_POINTS,
    _EXAMPLE_SCATTER,
    Delaunay,
    LloydRelaxation,
    Voronoi,
    VoronoiCells,
    _cells,
    _centroid,
    _nearer,
    _neighbours,
    _region_for,
    _shrunk,
    _sites,
    _tidied,
    _triangles,
    _welded,
)

# The module imports fine without scipy -- that is exactly what the lazy
# import buys, and what lets the registry list these motifs anyway -- but
# nothing below can be checked without it.
pytest.importorskip("scipy")

BOX = Bounds(-150.0, -150.0, 150.0, 150.0)
SQUARE = ((-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0))

#: A lattice, which is the case a hand-rolled triangulator gets wrong: every
#: set of four neighbours shares a circle, so there is no single right answer
#: for which diagonal to cut, and a triangulator that picks inconsistently
#: contradicts itself. Its Voronoi diagram, though, is not ambiguous at all.
GRID = tuple((float(i * 20), float(j * 20)) for i in range(-3, 4) for j in range(-3, 4))


def area(polygon):
    """Return the unsigned area of a simple polygon."""
    return (
        abs(
            math.fsum(
                a[0] * b[1] - b[0] * a[1] for a, b in itertools.pairwise((*polygon, polygon[0]))
            )
        )
        / 2.0
    )


def nearest(point, sites):
    """Return the index of the site closest to ``point``."""
    return min(range(len(sites)), key=lambda i: math.dist(sites[i], point))


def hull(points):
    """Return the convex hull of a point set, counter-clockwise (monotone chain)."""

    def half(ordered):
        chain: list[tuple[float, float]] = []
        for point in ordered:
            while len(chain) > 1:
                (ax, ay), (bx, by) = chain[-2], chain[-1]
                if (bx - ax) * (point[1] - ay) - (by - ay) * (point[0] - ax) > 0:
                    break
                chain.pop()
            chain.append(point)
        return chain[:-1]

    ordered = sorted(set(points))
    return half(ordered) + half(ordered[::-1])


# --- the one construction ---------------------------------------------------


def test_the_cells_tile_the_region_exactly():
    # The claim the whole module rests on: clipping the rectangle by the
    # bisectors against the Delaunay neighbours -- and no other bisector --
    # partitions it. Miss a neighbour and a cell is too big; use a bisector
    # that does not belong and a cell is too small. Either way this sum
    # stops being the area of the rectangle.
    cells = _cells(_EXAMPLE_POINTS, BOX)
    assert math.fsum(area(cell) for cell in cells) == pytest.approx(BOX.width * BOX.height)


def test_every_place_in_a_cell_belongs_to_its_own_site():
    sites = _EXAMPLE_POINTS
    cells = _cells(sites, BOX)
    for index, cell in enumerate(cells):
        middle = _centroid(cell)
        assert nearest(middle, sites) == index
        for corner in cell:
            # A corner is equidistant from two or more sites, so its own
            # site can only tie, never lose.
            own = math.dist(corner, sites[index])
            assert own <= min(math.dist(corner, s) for s in sites) + 1e-9


def test_every_site_sits_inside_its_own_cell():
    sites = _EXAMPLE_POINTS
    for site, cell in zip(sites, _cells(sites, BOX), strict=True):
        turns = [
            (b[0] - a[0]) * (site[1] - a[1]) - (b[1] - a[1]) * (site[0] - a[0])
            for a, b in itertools.pairwise((*cell, cell[0]))
        ]
        assert min(turns) >= -1e-9


def test_the_cells_of_a_lattice_are_the_lattice_squares():
    # The cocircular case. Every interior cell must come out as a 20x20
    # square, and the whole set must still tile the box.
    region = Bounds(-70.0, -70.0, 70.0, 70.0)
    cells = _cells(GRID, region)
    inner = [
        area(cell)
        for site, cell in zip(GRID, cells, strict=True)
        if abs(site[0]) < 60.0 and abs(site[1]) < 60.0
    ]
    assert len(inner) == 25
    assert inner == pytest.approx([400.0] * 25)
    assert math.fsum(area(cell) for cell in cells) == pytest.approx(140.0 * 140.0)


def test_a_site_outside_the_region_gets_no_cell():
    far = (*_EXAMPLE_POINTS, (10_000.0, 10_000.0))
    cells = _cells(far, Bounds(-150.0, -150.0, 150.0, 150.0))
    assert cells[-1] == ()
    assert math.fsum(area(c) for c in cells if c) == pytest.approx(300.0 * 300.0)


# --- the triangulation ------------------------------------------------------


@pytest.mark.parametrize("sites", [_EXAMPLE_POINTS, _EXAMPLE_SCATTER, GRID])
def test_the_triangles_cover_the_convex_hull_and_do_not_overlap(sites):
    # Both halves of "a triangulation" in one number: the triangles cover
    # the hull (no gap) and their areas add up to it (no overlap).
    total = math.fsum(area([sites[i] for i in tri]) for tri in _triangles(sites))
    assert total == pytest.approx(area(hull(sites)))


def test_no_point_falls_inside_another_triangles_circumcircle():
    # The defining property of a Delaunay triangulation, and the reason it
    # avoids thin triangles where any triangulation would do.
    sites = _EXAMPLE_POINTS
    for tri in _triangles(sites):
        a, b, c = (sites[i] for i in tri)
        centre, radius = _circumcircle(a, b, c)
        for index, site in enumerate(sites):
            if index in tri:
                continue
            assert math.dist(centre, site) > radius - 1e-6


def _circumcircle(a, b, c):
    """Return the centre and radius of the circle through three points."""
    d = 2.0 * (a[0] * (b[1] - c[1]) + b[0] * (c[1] - a[1]) + c[0] * (a[1] - b[1]))
    sa, sb, sc = (p[0] ** 2 + p[1] ** 2 for p in (a, b, c))
    x = (sa * (b[1] - c[1]) + sb * (c[1] - a[1]) + sc * (a[1] - b[1])) / d
    y = (sa * (c[0] - b[0]) + sb * (a[0] - c[0]) + sc * (b[0] - a[0])) / d
    return (x, y), math.dist((x, y), a)


def test_neighbours_are_symmetric_and_come_from_the_triangles():
    triangles = _triangles(_EXAMPLE_POINTS)
    near = _neighbours(len(_EXAMPLE_POINTS), triangles)
    for i, group in enumerate(near):
        assert i not in group
        for j in group:
            assert i in near[j]
    assert all(near)


def test_a_single_triangle_makes_everyone_a_neighbour():
    assert _neighbours(3, [(0, 1, 2)]) == (frozenset({1, 2}), frozenset({0, 2}), frozenset({0, 1}))


def test_points_on_one_line_cannot_be_triangulated():
    with pytest.raises(ValueError, match="one line"):
        Delaunay(points=((0.0, 0.0), (1.0, 1.0), (2.0, 2.0), (3.0, 3.0))).build()


# --- Euler, on the diagram itself -------------------------------------------


def test_the_diagram_is_a_planar_map():
    # V - E + F = 2 over the whole picture, counting the outside as a face.
    # Every cell is a face, and the rectangle's own boundary closes the map.
    motif = Voronoi(points=_EXAMPLE_POINTS, region=BOX)
    corners, loops = motif.corners()
    edges = {frozenset(pair) for loop in loops for pair in itertools.pairwise((*loop, loop[0]))}
    faces = len(loops) + 1
    assert len(corners) - len(edges) + faces == 2


def test_every_border_is_drawn_once_however_many_cells_meet_along_it():
    motif = Voronoi(points=_EXAMPLE_POINTS, region=BOX)
    design = motif.build()
    _, loops = motif.corners()
    named = [pair for loop in loops for pair in itertools.pairwise((*loop, loop[0]))]
    assert len(design.paths) == len({frozenset(pair) for pair in named})
    # An interior border is named by both of the cells that share it, so the
    # cells claim strictly more borders than there are.
    assert len(named) > len(design.paths)


def test_the_cells_claim_each_interior_border_exactly_twice():
    _, loops = Voronoi(points=_EXAMPLE_POINTS, region=BOX).corners()
    counts: dict[frozenset[int], int] = {}
    for loop in loops:
        for pair in itertools.pairwise((*loop, loop[0])):
            counts[frozenset(pair)] = counts.get(frozenset(pair), 0) + 1
    assert set(counts.values()) == {1, 2}
    # The ones claimed once are the region's own sides, cut up by the cells
    # that reach them.
    assert sum(1 for n in counts.values() if n == 1) > 4


# --- welding ----------------------------------------------------------------


def test_welding_recognises_corners_that_agree_to_within_the_tolerance():
    cells = (
        ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0)),
        ((1.0, 0.0), (1.0 + 1e-13, 1.0 - 1e-13), (2.0, 1.0)),
    )
    corners, loops = _welded(cells, 1e-9)
    assert len(corners) == 4
    assert loops[0][1] == loops[1][0]
    assert loops[0][2] == loops[1][1]


def test_welding_looks_in_the_neighbouring_bucket_too():
    # Two corners a hair apart but either side of a rounding boundary: the
    # exact bucket alone would miss the match and split the shared border.
    tolerance = 1e-3
    below, above = 0.4999 * tolerance, 0.5001 * tolerance
    assert round(below / tolerance) != round(above / tolerance)
    assert abs(above - below) < tolerance
    cells = (
        ((0.0, 0.0), (1.0, 0.0), (below, 1.0)),
        ((0.0, 0.0), (1.0, 0.0), (above, 1.0)),
    )
    corners, _ = _welded(cells, tolerance)
    assert len(corners) == 3


def test_welding_skips_a_cell_that_is_not_a_polygon():
    corners, loops = _welded([((0.0, 0.0), (1.0, 0.0)), ()], 1e-9)
    assert corners == ()
    assert loops == ()


# --- the half-plane clip ----------------------------------------------------


def test_clipping_keeps_the_half_nearer_the_site():
    kept = _nearer(SQUARE, (-1.0, 0.0), (1.0, 0.0))
    assert area(kept) == pytest.approx(2.0)
    assert all(x <= 1e-12 for x, _ in kept)


def test_a_clip_that_misses_changes_nothing():
    assert _nearer(SQUARE, (0.0, 0.0), (100.0, 0.0)) == SQUARE


def test_a_clip_that_covers_everything_leaves_nothing():
    assert _nearer(SQUARE, (-100.0, 0.0), (0.0, 0.0)) == ()


def test_a_clip_through_two_corners_leaves_no_slivers():
    # The line through (1, -1) and (-1, 1) keeps both corners and then finds
    # a crossing at each of them; the duplicates have to go.
    kept = _tidied(_nearer(SQUARE, (-1.0, -1.0), (1.0, 1.0)), 1e-9)
    assert len(kept) == 3
    assert area(kept) == pytest.approx(2.0)


def test_tidying_closes_the_seam():
    assert _tidied(((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (1e-15, 1e-15)), 1e-9) == (
        (0.0, 0.0),
        (1.0, 0.0),
        (1.0, 1.0),
    )


def test_tidying_a_single_point_leaves_it_alone():
    assert _tidied(((3.0, 4.0), (3.0, 4.0)), 1e-9) == ((3.0, 4.0),)


# --- centroids and insets ---------------------------------------------------


def test_the_centroid_of_a_square_is_its_middle():
    assert _centroid(SQUARE) == pytest.approx((0.0, 0.0))


def test_the_centroid_of_a_triangle_is_the_mean_of_its_corners():
    corners = ((0.0, 0.0), (6.0, 0.0), (0.0, 9.0))
    assert _centroid(corners) == pytest.approx((2.0, 3.0))


def test_a_cell_pinched_down_to_a_line_still_has_a_middle():
    # No area to take a centre of, so the corners' mean it is -- the
    # alternative being a division by zero somewhere deep in a relaxation.
    assert _centroid(((0.0, 0.0), (1.0, 0.0), (5.0, 0.0))) == pytest.approx((2.0, 0.0))


def test_an_inset_shrinks_a_cell_about_its_own_middle():
    shrunk = _shrunk(SQUARE, 0.5)
    assert area(shrunk) == pytest.approx(area(SQUARE) * 0.25)
    assert _centroid(shrunk) == pytest.approx(_centroid(SQUARE))


def test_no_inset_returns_the_cell_untouched():
    assert _shrunk(SQUARE, 0.0) == SQUARE


# --- the region -------------------------------------------------------------


def test_the_derived_region_reaches_a_tenth_past_the_points():
    region = _region_for(((-50.0, -20.0), (50.0, 20.0), (0.0, 0.0)), None)
    assert region == Bounds(-60.0, -30.0, 60.0, 30.0)


def test_a_given_region_is_used_as_it_stands():
    assert _region_for(_EXAMPLE_POINTS, BOX) is BOX


def test_the_diagram_stays_inside_its_region():
    design = Voronoi(points=_EXAMPLE_POINTS, region=BOX).build()
    assert design.bounds.min_x >= BOX.min_x - 1e-9
    assert design.bounds.max_x <= BOX.max_x + 1e-9
    assert design.bounds.min_y >= BOX.min_y - 1e-9
    assert design.bounds.max_y <= BOX.max_y + 1e-9


def test_a_region_nowhere_near_the_points_still_belongs_to_one_of_them():
    # The diagram covers the whole plane, so a region put anywhere at all is
    # some site's -- the nearest one's -- and comes back whole.
    far = Bounds(5_000.0, 5_000.0, 5_100.0, 5_100.0)
    design = VoronoiCells(points=_EXAMPLE_POINTS, region=far).build()
    assert len(design.paths) == 1
    assert area(design.paths[0].points) == pytest.approx(far.width * far.height)


def test_a_region_with_no_area_leaves_nothing_to_draw():
    with pytest.raises(ValueError, match="no outlines"):
        VoronoiCells(points=_EXAMPLE_POINTS, region=Bounds(0.0, 0.0, 0.0, 0.0)).build()


# --- Lloyd's relaxation -----------------------------------------------------


def test_relaxing_evens_the_spacing_out():
    def spread(points):
        """Return the closest and widest gap between neighbours, and their ratio."""
        near = _neighbours(len(points), _triangles(points))
        gaps = [min(math.dist(p, points[j]) for j in near[i]) for i, p in enumerate(points)]
        return min(gaps), max(gaps), max(gaps) / min(gaps)

    before = spread(_EXAMPLE_SCATTER)
    after = spread(LloydRelaxation(points=_EXAMPLE_SCATTER, iterations=8).relaxed())
    # It is the clumps that go: the widest gap barely moves, while the
    # closest pair more than quadruples the distance between them.
    assert before[2] > 8.0
    assert after[2] < 2.0
    assert after[0] > 4.0 * before[0]
    assert after[1] == pytest.approx(before[1], rel=0.15)


def test_relaxing_moves_less_and_less():
    sites = _EXAMPLE_SCATTER
    region = _region_for(sites, None)
    steps = []
    for _ in range(6):
        moved = LloydRelaxation(points=sites, iterations=1, region=region).relaxed()
        steps.append(max(math.dist(a, b) for a, b in zip(sites, moved, strict=True)))
        sites = moved
    # Not monotone -- a point can be handed a new neighbour and jump -- but
    # the trend is unmistakable.
    assert steps[-1] < steps[0] / 4.0


def test_no_iterations_leaves_the_points_where_they_are():
    assert LloydRelaxation(points=_EXAMPLE_SCATTER, iterations=0).relaxed() == _EXAMPLE_SCATTER


def test_the_relaxed_points_are_the_centres_of_their_own_cells():
    sites = LloydRelaxation(points=_EXAMPLE_SCATTER, iterations=1).relaxed()
    region = _region_for(_EXAMPLE_SCATTER, None)
    for site, cell in zip(sites, _cells(_EXAMPLE_SCATTER, region), strict=True):
        assert site == pytest.approx(_centroid(cell))


def test_relaxing_keeps_the_points_inside_the_region():
    region = _region_for(_EXAMPLE_SCATTER, None)
    for point in LloydRelaxation(points=_EXAMPLE_SCATTER, iterations=5).relaxed():
        assert point in region


def test_a_site_with_no_cell_stays_put():
    far = (*_EXAMPLE_POINTS, (10_000.0, 10_000.0))
    relaxed = LloydRelaxation(points=far, iterations=3, region=BOX).relaxed()
    assert relaxed[-1] == (10_000.0, 10_000.0)


def test_the_relaxation_is_a_point_field_not_a_drawing():
    design = LloydRelaxation(points=_EXAMPLE_SCATTER).build()
    assert design.paths == ()
    assert len(design.points) == len(_EXAMPLE_SCATTER)


# --- the motifs -------------------------------------------------------------


def test_the_triangulation_draws_one_stroke_per_edge():
    motif = Delaunay(points=_EXAMPLE_POINTS)
    edges = {frozenset(pair) for pair in motif.edges()}
    assert len(motif.build().paths) == len(edges)


def test_the_triangulation_and_the_diagram_have_the_same_number_of_borders():
    # They are dual: a Delaunay edge and the Voronoi border it crosses are
    # the same fact told twice. The diagram has the region's own sides on
    # top of that, which the triangulation has nothing to match.
    triangulation = len(Delaunay(points=_EXAMPLE_POINTS).build().paths)
    diagram = len(Voronoi(points=_EXAMPLE_POINTS, region=BOX).build().paths)
    assert diagram > triangulation


def test_the_diagram_hands_out_its_cells():
    motif = Voronoi(points=_EXAMPLE_POINTS, region=BOX)
    assert motif.cells() == _cells(_EXAMPLE_POINTS, BOX)


def test_the_cells_are_closed_and_the_diagram_is_not():
    assert all(path.closed for path in VoronoiCells(points=_EXAMPLE_POINTS).build().paths)
    assert not any(path.closed for path in Voronoi(points=_EXAMPLE_POINTS).build().paths)


def test_there_is_one_closed_cell_per_site():
    design = VoronoiCells(points=_EXAMPLE_POINTS).build()
    assert len(design.paths) == len(_EXAMPLE_POINTS)


def test_an_inset_pulls_every_cell_away_from_its_neighbours():
    plain = VoronoiCells(points=_EXAMPLE_POINTS).build()
    inset = VoronoiCells(points=_EXAMPLE_POINTS, inset=0.2).build()
    for whole, shrunk in zip(plain.paths, inset.paths, strict=True):
        assert area(shrunk.points) == pytest.approx(area(whole.points) * 0.64)


def test_the_borders_can_be_chained_into_longer_strokes():
    plain = Voronoi(points=_EXAMPLE_POINTS).build()
    merged = Voronoi(points=_EXAMPLE_POINTS, merge=True).build()
    assert len(merged.paths) < len(plain.paths)
    assert math.fsum(p.length for p in merged.paths) == pytest.approx(
        math.fsum(p.length for p in plain.paths)
    )


def test_the_corners_can_be_drawn_as_points():
    assert Voronoi(points=_EXAMPLE_POINTS, show_nodes=True).build().points != ()
    assert Delaunay(points=_EXAMPLE_POINTS, show_nodes=True).build().points == _EXAMPLE_POINTS


def test_meta_records_the_parameters():
    design = VoronoiCells(points=_EXAMPLE_POINTS, inset=0.3).build()
    assert design.meta["motif"] == "voronoi.cells"
    assert design.meta["inset"] == 0.3
    assert design.meta["points"] == _EXAMPLE_POINTS


# --- what is refused --------------------------------------------------------


def test_a_list_of_whole_numbers_comes_back_a_tuple_of_floats():
    # Normalized on the way in, because the point set is the key to the
    # triangulation memo and a list cannot be one.
    motif = Delaunay(points=[(0, 0), (10, 0), (0, 10)])
    assert motif.points == ((0.0, 0.0), (10.0, 0.0), (0.0, 10.0))
    assert all(isinstance(value, float) for point in motif.points for value in point)


@pytest.mark.parametrize(
    ("make", "why"),
    [
        (lambda: Delaunay(points=((0.0, 0.0), (1.0, 0.0))), "at least 3"),
        (lambda: Voronoi(points=()), "at least 3"),
        (lambda: Delaunay(points=tuple((float(i), 0.5) for i in range(5001))), "5000"),
        (lambda: VoronoiCells(points=_EXAMPLE_POINTS, inset=1.0), "inset"),
        (lambda: VoronoiCells(points=_EXAMPLE_POINTS, inset=-0.1), "inset"),
        (lambda: LloydRelaxation(points=_EXAMPLE_POINTS, iterations=-1), "iterations"),
        (lambda: LloydRelaxation(points=_EXAMPLE_POINTS, iterations=201), "iterations"),
        (lambda: Delaunay(points=((0.0, 0.0), (1.0, 0.0), (0.0, float("inf")))), "finite"),
    ],
)
def test_bad_parameters_are_refused(make, why):
    with pytest.raises(ValueError, match=why):
        make()


def test_a_point_that_is_not_a_pair_is_refused():
    with pytest.raises(TypeError, match="points\\[1\\]"):
        Delaunay(points=((0.0, 0.0), 7.0, (1.0, 1.0)))  # type: ignore[arg-type]


def test_sites_says_which_motif_complained():
    with pytest.raises(ValueError, match="Widget needs at least 3"):
        _sites(((0.0, 0.0),), owner="Widget")


def test_without_scipy_the_error_says_how_to_get_it(monkeypatch):
    # A None in sys.modules is what the import machinery leaves behind for a
    # module it has been told not to load, and it makes ``from ... import``
    # raise exactly as a missing scipy would.
    monkeypatch.setitem(sys.modules, "scipy.spatial", None)
    with pytest.raises(ImportError, match=r"geomotif\[scipy\]"):
        _triangles(_EXAMPLE_POINTS)
