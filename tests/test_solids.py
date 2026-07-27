import itertools
import math

import pytest

from geomotif.motifs.solids import (
    Cube,
    Dodecahedron,
    Icosahedron,
    Octahedron,
    Polyhedron,
    Projection,
    Tetrahedron,
    TruncatedIcosahedron,
    _cyclic,
    _shortest_pairs,
    _unit,
)

PHI = (1.0 + math.sqrt(5.0)) / 2.0

#: Every solid whose corners are all alike, with the counts it should have.
REGULAR = [
    (Tetrahedron, 4, 6, 4),
    (Cube, 8, 12, 6),
    (Octahedron, 6, 12, 8),
    (Dodecahedron, 20, 30, 12),
    (Icosahedron, 12, 30, 20),
    (TruncatedIcosahedron, 60, 90, 32),
]
IDS = [cls.__name__ for cls, *_ in REGULAR]


def reach(vertex):
    return math.sqrt(sum(c * c for c in vertex))


# --- the tables -------------------------------------------------------------


@pytest.mark.parametrize(("cls", "corners", "edges", "faces"), REGULAR, ids=IDS)
def test_the_counts_are_the_ones_the_solid_is_named_for(cls, corners, edges, faces):
    motif = cls()
    assert len(motif.vertices()) == corners
    assert len(list(motif.edges())) == edges
    assert cls.faces == faces


@pytest.mark.parametrize(("cls", "corners", "edges", "faces"), REGULAR, ids=IDS)
def test_euler_holds(cls, corners, edges, faces):
    # The check that catches a mistyped coordinate: get one corner wrong and
    # the nearest-pairs rule finds the wrong edges, and this stops being 2.
    assert corners - edges + faces == 2


@pytest.mark.parametrize(("cls", "corners", "edges", "faces"), REGULAR, ids=IDS)
def test_every_corner_sits_on_one_sphere(cls, corners, edges, faces):
    reaches = [reach(v) for v in cls().vertices()]
    assert reaches == pytest.approx([reaches[0]] * corners)


@pytest.mark.parametrize(("cls", "corners", "edges", "faces"), REGULAR, ids=IDS)
def test_every_edge_is_the_same_length(cls, corners, edges, faces):
    motif = cls()
    unit = _unit(motif.vertices())
    spans = [math.dist(unit[i], unit[j]) for i, j in motif.edges()]
    assert spans == pytest.approx([spans[0]] * edges)


@pytest.mark.parametrize(("cls", "corners", "edges", "faces"), REGULAR, ids=IDS)
def test_no_two_corners_land_on_top_of_each_other(cls, corners, edges, faces):
    unit = _unit(cls().vertices())
    for a, b in itertools.combinations(unit, 2):
        assert math.dist(a, b) > 1e-9


def test_the_icosahedron_is_three_golden_rectangles():
    # Each pair of corners furthest apart is a diagonal; the twelve corners
    # fall into three flat rectangles whose sides are 2 and 2*phi.
    corners = Icosahedron().vertices()
    flat = [c for c in corners if c[0] == 0.0]
    assert len(flat) == 4
    sides = sorted({round(math.dist(a, b), 6) for a, b in itertools.combinations(flat, 2)})
    assert sides[1] / sides[0] == pytest.approx(PHI)


def test_the_football_is_pentagons_and_hexagons():
    motif = TruncatedIcosahedron()
    # Every corner of a truncated solid meets exactly three edges: one along
    # the original edge and two round the cut.
    met = [0] * len(motif.vertices())
    for i, j in motif.edges():
        met[i] += 1
        met[j] += 1
    assert set(met) == {3}


# --- the helpers ------------------------------------------------------------


def test_a_cyclic_table_writes_out_every_shuffle_and_sign():
    assert len(_cyclic(0.0, 1.0, PHI)) == 12
    assert len(_cyclic(1.0, 1.0, 1.0)) == 24  # the cube's corners, three times over
    assert len(_cyclic(1.0, 0.0, 0.0)) == 6


def test_a_zero_is_not_counted_twice_for_its_sign():
    assert (0.0, 1.0, PHI) in _cyclic(0.0, 1.0, PHI)
    assert sum(1 for v in _cyclic(0.0, 1.0, PHI) if v == (0.0, 1.0, PHI)) == 1


def test_the_shortest_pairs_are_the_only_pairs():
    line = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (5.0, 0.0, 0.0))
    assert _shortest_pairs(line) == ((0, 1), (1, 2))


def test_normalising_puts_the_furthest_corner_one_unit_out():
    assert max(reach(v) for v in _unit(((3.0, 4.0, 0.0), (1.0, 0.0, 0.0)))) == pytest.approx(1.0)


# --- projections ------------------------------------------------------------


def test_orthographic_simply_drops_the_depth():
    view = Projection(kind="orthographic")
    assert view((0.3, -0.4, 0.9)) == pytest.approx((0.3, -0.4))


def test_isometric_makes_a_cube_a_hexagon():
    # The three faces you can see come out as identical rhombi, so the outline
    # is a regular hexagon and two corners land exactly on top of each other.
    corners = [Projection()(v) for v in _unit(Cube().vertices())]
    reaches = sorted(round(math.hypot(*p), 6) for p in corners)
    assert reaches[0] == pytest.approx(0.0, abs=1e-9)
    assert reaches[1] == pytest.approx(0.0, abs=1e-9)
    assert reaches[2:] == pytest.approx([reaches[-1]] * 6)


def test_perspective_makes_the_near_side_bigger():
    view = Projection(kind="perspective", distance=3.0)
    near = view((0.5, 0.0, 0.9))
    far = view((0.5, 0.0, -0.9))
    assert near[0] > 0.5 > far[0]


def test_turning_the_view_turns_the_solid():
    upright = Projection(kind="orthographic")
    rolled = Projection(kind="orthographic", roll=math.pi / 2.0)
    x, y = upright((0.6, 0.2, 0.0))
    assert rolled((0.6, 0.2, 0.0)) == pytest.approx((-y, x))


def test_a_yaw_of_a_quarter_turn_swaps_depth_for_width():
    view = Projection(kind="orthographic", yaw=math.pi / 2.0)
    assert view((1.0, 0.0, 0.0)) == pytest.approx((0.0, 0.0), abs=1e-12)
    assert view((0.0, 0.0, 1.0)) == pytest.approx((1.0, 0.0))


@pytest.mark.parametrize(
    ("make", "why"),
    [
        (lambda: Projection(kind="cabinet"), "kind"),  # type: ignore[arg-type]
        (lambda: Projection(kind="perspective", distance=1.0), "distance"),
        (lambda: Projection(kind="perspective", distance=-2.0), "distance"),
    ],
)
def test_a_bad_projection_is_refused(make, why):
    with pytest.raises(ValueError, match=why):
        make()


# --- placing and sizing -----------------------------------------------------


@pytest.mark.parametrize(("cls", "corners", "edges", "faces"), REGULAR, ids=IDS)
def test_nothing_reaches_further_than_the_circumsphere(cls, corners, edges, faces):
    design = cls(size=100.0).build()
    assert max(math.hypot(*p) for p in design) <= 50.0 + 1e-9


def test_the_solid_lands_where_it_is_told():
    here = Cube(size=80.0).build()
    there = Cube(size=80.0, center=(15.0, -25.0)).build()
    for first, second in zip(here.paths, there.paths, strict=True):
        for (x, y), (u, v) in zip(first.points, second.points, strict=True):
            assert (u, v) == pytest.approx((x + 15.0, y - 25.0))


def test_size_scales_the_whole_thing():
    small = Icosahedron(size=10.0).build().bounds
    large = Icosahedron(size=40.0).build().bounds
    assert large.width / small.width == pytest.approx(4.0)


def test_the_edges_can_be_chained_into_longer_strokes():
    plain = Cube(size=50.0).build()
    merged = Cube(size=50.0, merge=True).build()
    assert len(merged.paths) < len(plain.paths)
    assert math.fsum(p.length for p in merged.paths) == pytest.approx(
        math.fsum(p.length for p in plain.paths)
    )


def test_the_corners_can_be_drawn_as_points():
    assert Cube(show_nodes=True).build().points != ()
    assert Cube().build().points == ()


# --- a solid of your own ----------------------------------------------------


def test_a_custom_solid_uses_the_edges_it_is_given():
    pyramid = Polyhedron(
        corners=(
            (-1.0, -1.0, 0.0),
            (1.0, -1.0, 0.0),
            (1.0, 1.0, 0.0),
            (-1.0, 1.0, 0.0),
            (0.0, 0.0, 1.4),
        ),
        links=((0, 1), (1, 2), (2, 3), (3, 0), (0, 4), (1, 4), (2, 4), (3, 4)),
    )
    assert len(pyramid.build().paths) == 8


def test_a_custom_solid_with_no_edges_joins_the_nearest_pairs():
    # The same corners as the cube, and no edge list: the fallback has to find
    # the cube's twelve edges and not its face diagonals.
    loose = Polyhedron(corners=tuple(Cube().vertices()))
    assert len(list(loose.edges())) == 12


@pytest.mark.parametrize(
    "make",
    [
        lambda: Cube(size=0.0),
        lambda: Cube(size=-5.0),
        lambda: Polyhedron(corners=()),
        lambda: Polyhedron(corners=((0.0, 0.0, 0.0),)),
    ],
)
def test_bad_parameters_are_refused(make):
    with pytest.raises(ValueError):
        make()


def test_a_solid_with_more_corners_than_can_be_searched_is_refused():
    with pytest.raises(ValueError, match="quadratic"):
        Polyhedron(corners=tuple((float(i), 0.0, 0.0) for i in range(2001)))


def test_an_edge_that_names_a_corner_that_is_not_there_is_refused():
    with pytest.raises(IndexError):
        Polyhedron(corners=tuple(Cube().vertices()), links=((0, 99),)).build()


def test_meta_records_the_parameters():
    design = Dodecahedron(size=75.0).build()
    assert design.meta["motif"] == "solid.dodecahedron"
    assert design.meta["size"] == 75.0
    assert design.meta["projection"] == Projection()
