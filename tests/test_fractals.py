import math
from itertools import pairwise

import pytest

from geomotif.core.transform import Affine
from geomotif.motifs.fractals import (
    ApollonianGasket,
    BarnsleyFern,
    CantorSet,
    DragonCurve,
    GosperCurve,
    HilbertCurve,
    HTree,
    IFSAttractor,
    IFSMap,
    KochAntisnowflake,
    KochCurve,
    KochSnowflake,
    LevyCCurve,
    MinkowskiIsland,
    MinkowskiSausage,
    MooreCurve,
    PeanoCurve,
    PythagorasTree,
    SierpinskiArrowhead,
    SierpinskiCarpet,
    SierpinskiTriangle,
    Terdragon,
    TwinDragon,
    VicsekFractal,
)


def only_path(motif):
    design = motif.build()
    assert len(design.paths) == 1
    return design.paths[0]


def segment_count(path):
    """Return how many turtle moves a path records, closed or open."""
    return len(path.points) if path.closed else len(path.points) - 1


def enclosed_area(points):
    """Return the absolute area a closed polygon encloses, by the shoelace formula."""
    n = len(points)
    return (
        abs(
            math.fsum(
                points[i][0] * points[(i + 1) % n][1] - points[(i + 1) % n][0] * points[i][1]
                for i in range(n)
            )
        )
        / 2.0
    )


def side_of(outline):
    """Return the side length of a square given as four corners."""
    return math.dist(outline[0], outline[1])


# --- grammars ---------------------------------------------------------------

# Each grammar replaces one segment with a fixed number of them, so the count
# is exactly that number raised to the depth, times whatever the axiom draws.
# A wrong rewrite rule cannot survive this table.
SEGMENTS = [
    (KochCurve, 4, 4**4),
    (KochSnowflake, 3, 3 * 4**3),
    (KochAntisnowflake, 3, 3 * 4**3),
    (MinkowskiSausage, 3, 8**3),
    (MinkowskiIsland, 2, 4 * 8**2),
    (SierpinskiArrowhead, 5, 3**5),
    (DragonCurve, 8, 2**8),
    (TwinDragon, 8, 2 * 2**8),
    (Terdragon, 5, 3**5),
    (LevyCCurve, 8, 2**8),
    (GosperCurve, 3, 7**3),
    (VicsekFractal, 3, 4 * 5**3),
    # The space-filling curves visit every cell of their grid, so they draw one
    # segment fewer than there are cells -- except Moore's, which closes the
    # loop and therefore draws one more.
    (HilbertCurve, 4, 4**4 - 1),
    (PeanoCurve, 2, 9**2 - 1),
    (MooreCurve, 3, 4**4),
]


@pytest.mark.parametrize(("cls", "depth", "expected"), SEGMENTS)
def test_each_grammar_draws_the_segments_its_rule_implies(cls, depth, expected):
    assert segment_count(only_path(cls(depth=depth))) == expected


# End-to-end distance for the grammars that go somewhere: each is the scale
# factor of one rewrite, raised to the depth. This is the fractal's dimension
# stated as a measurement -- pair it with the segment count above and
# log(segments) / log(distance) is it.
SCALES = [
    (KochCurve, 4, 3.0),
    (MinkowskiSausage, 3, 4.0),
    (SierpinskiArrowhead, 6, 2.0),
    (DragonCurve, 10, math.sqrt(2.0)),
    (LevyCCurve, 10, math.sqrt(2.0)),
    (Terdragon, 6, math.sqrt(3.0)),
    (GosperCurve, 4, math.sqrt(7.0)),
]


@pytest.mark.parametrize(("cls", "depth", "scale"), SCALES)
def test_each_open_grammar_spans_its_scale_factor_to_the_depth(cls, depth, scale):
    path = only_path(cls(depth=depth))
    assert math.dist(path.points[0], path.points[-1]) == pytest.approx(scale**depth)


@pytest.mark.parametrize("depth", [1, 2, 3, 4])
def test_the_koch_curve_spans_three_to_the_depth(depth):
    assert only_path(KochCurve(depth=depth)).length == pytest.approx(4.0**depth)
    assert KochCurve(depth=depth).build().bounds.width == pytest.approx(3.0**depth)


@pytest.mark.parametrize("depth", [1, 2, 3, 4])
def test_the_hilbert_curve_fills_a_square_grid(depth):
    bounds = HilbertCurve(depth=depth).build().bounds
    assert bounds.width == pytest.approx(2**depth - 1)
    assert bounds.height == pytest.approx(2**depth - 1)


@pytest.mark.parametrize("depth", [1, 2, 3])
def test_the_peano_curve_fills_a_grid_of_thirds(depth):
    bounds = PeanoCurve(depth=depth).build().bounds
    assert bounds.width == pytest.approx(3**depth - 1)
    assert bounds.height == pytest.approx(3**depth - 1)


@pytest.mark.parametrize("depth", [0, 1, 2, 3, 4])
def test_the_snowflake_area_follows_the_series(depth):
    # Each round adds three new triangles per side at a ninth the area, so the
    # area is A0 * (1 + 3/5 * (1 - (4/9)**n)) -- converging on 8/5 of the
    # starting triangle while the perimeter runs away to infinity.
    side = 3.0**depth
    start = math.sqrt(3.0) / 4.0 * side * side
    path = only_path(KochSnowflake(depth=depth))
    assert enclosed_area(path.points) == pytest.approx(
        start * (1.0 + 0.6 * (1.0 - (4.0 / 9.0) ** depth))
    )
    assert path.length == pytest.approx(3.0 * side * (4.0 / 3.0) ** depth)


def test_the_snowflake_area_approaches_eight_fifths_of_its_triangle():
    ratios = []
    for depth in (2, 4, 6):
        side = 3.0**depth
        start = math.sqrt(3.0) / 4.0 * side * side
        ratios.append(enclosed_area(only_path(KochSnowflake(depth=depth)).points) / start)
    assert ratios[0] < ratios[1] < ratios[2] < 1.6
    assert ratios[-1] == pytest.approx(1.6, abs=5e-3)


@pytest.mark.parametrize("depth", [0, 1, 2, 3])
def test_the_minkowski_island_keeps_the_area_of_its_square(depth):
    # The generator detours above the chord and below it by the same amount, so
    # the coastline lengthens without the enclosed area changing at all.
    path = only_path(MinkowskiIsland(depth=depth))
    assert enclosed_area(path.points) == pytest.approx(16.0**depth)
    assert path.length == pytest.approx(4.0 * 8.0**depth)


def test_the_antisnowflake_encloses_less_than_the_snowflake():
    # Same triangle, same number of spikes, turned the other way -- so the one
    # eats into the triangle exactly as much as the other adds to it.
    depth = 3
    inward = enclosed_area(only_path(KochAntisnowflake(depth=depth)).points)
    outward = enclosed_area(only_path(KochSnowflake(depth=depth)).points)
    triangle = math.sqrt(3.0) / 4.0 * (3.0**depth) ** 2
    assert inward < triangle < outward
    assert triangle - inward == pytest.approx(outward - triangle)


@pytest.mark.parametrize(
    "cls",
    [
        KochSnowflake,
        KochAntisnowflake,
        MinkowskiIsland,
        SierpinskiTriangle,
        MooreCurve,
        TwinDragon,
        VicsekFractal,
    ],
)
def test_the_closed_grammars_come_home(cls):
    path = only_path(cls(depth=2))
    assert path.closed
    # The seam is implied rather than stored, so the last vertex is one turtle
    # step short of the first rather than on top of it.
    assert math.dist(path.points[0], path.points[-1]) == pytest.approx(1.0)


@pytest.mark.parametrize("cls", [KochCurve, DragonCurve, HilbertCurve, GosperCurve, PeanoCurve])
def test_the_open_grammars_do_not_pretend_to_close(cls):
    assert not only_path(cls(depth=3)).closed


def test_step_scales_a_grammar_fractal_without_changing_it():
    small = only_path(KochSnowflake(depth=3, step=1.0))
    large = only_path(KochSnowflake(depth=3, step=2.5))
    assert large.length == pytest.approx(small.length * 2.5)
    for near, far in zip(small.points, large.points, strict=True):
        assert far[0] == pytest.approx(near[0] * 2.5)
        assert far[1] == pytest.approx(near[1] * 2.5)


def test_the_sierpinski_triangle_and_arrowhead_cover_the_same_triangle():
    # Two grammars with nothing in common converging on one set. The gasket
    # closes around the triangle exactly at every depth; the arrowhead is an
    # open scalloped path that only reaches the corners in the limit, so its
    # box creeps up on the equilateral aspect ratio from below rather than
    # matching it outright.
    equilateral = math.sqrt(3.0) / 2.0
    gasket = SierpinskiTriangle(depth=5).build().bounds
    assert gasket.height / gasket.width == pytest.approx(equilateral)

    ratios = []
    for depth in (2, 4, 6):
        box = SierpinskiArrowhead(depth=depth).build().bounds
        ratios.append(box.height / box.width)
    assert ratios[0] < ratios[1] < ratios[2] < equilateral
    assert ratios[-1] == pytest.approx(equilateral, rel=2e-2)


# --- recursion --------------------------------------------------------------


@pytest.mark.parametrize("depth", [0, 1, 2, 3])
def test_the_carpet_cuts_one_hole_per_surviving_ninth(depth):
    carpet = SierpinskiCarpet(depth=depth)
    assert carpet.hole_count() == (8**depth - 1) // 7
    # One path for the outer square, one for each hole.
    assert len(carpet.build().paths) == carpet.hole_count() + 1


def test_the_carpet_holes_shrink_by_a_third_each_round():
    paths = SierpinskiCarpet(depth=3, size=270.0).build().paths
    sides = sorted({round(path.points[1][0] - path.points[0][0], 6) for path in paths})
    assert sides == [10.0, 30.0, 90.0, 270.0]


def test_the_carpet_fills_the_size_it_is_given():
    bounds = SierpinskiCarpet(size=200.0, center=(30.0, -10.0)).build().bounds
    assert bounds.width == pytest.approx(200.0)
    assert bounds.height == pytest.approx(200.0)
    assert (bounds.min_x + bounds.max_x) / 2.0 == pytest.approx(30.0)
    assert (bounds.min_y + bounds.max_y) / 2.0 == pytest.approx(-10.0)


@pytest.mark.parametrize("depth", [0, 1, 2, 5])
def test_the_cantor_set_doubles_its_bars_and_thirds_their_length(depth):
    cantor = CantorSet(depth=depth, width=243.0, gap=10.0)
    paths = cantor.build().paths
    assert cantor.bar_count() == 2 ** (depth + 1) - 1
    assert len(paths) == cantor.bar_count()
    # Every round keeps two thirds of what is left, so the surviving length
    # falls off geometrically even though the bar count doubles.
    assert math.fsum(path.length for path in paths) == pytest.approx(
        243.0 * math.fsum((2.0 / 3.0) ** row for row in range(depth + 1))
    )


def test_the_cantor_bars_are_open_strokes():
    assert not any(path.closed for path in CantorSet(depth=2).build().paths)


def test_the_cantor_rows_are_a_gap_apart():
    rows = sorted(
        {round(path.points[0][1], 6) for path in CantorSet(depth=4, gap=7.0).build().paths}
    )
    assert len(rows) == 5
    for lower, upper in pairwise(rows):
        assert upper - lower == pytest.approx(7.0)


@pytest.mark.parametrize("depth", [0, 1, 2, 6])
def test_the_pythagoras_tree_grows_two_squares_per_square(depth):
    tree = PythagorasTree(depth=depth, size=20.0)
    assert tree.square_count() == 2 ** (depth + 1) - 1
    assert len(tree.build().paths) == tree.square_count()


@pytest.mark.parametrize("lean", [math.pi / 6.0, math.pi / 4.0, 1.0, 1.4])
def test_the_pythagoras_tree_is_the_theorem(lean):
    # The two children stand on the legs of a right triangle whose hypotenuse
    # is the parent's top edge, so their areas add up to the parent's -- at
    # every lean, which is the whole content of the theorem.
    parent, left, right = PythagorasTree(depth=1, size=10.0, lean=lean).outlines()
    assert side_of(left) ** 2 + side_of(right) ** 2 == pytest.approx(side_of(parent) ** 2)


def test_the_pythagoras_trunk_stands_on_its_base():
    trunk = next(iter(PythagorasTree(size=40.0, base=(5.0, -3.0)).outlines()))
    assert trunk[0] == pytest.approx((-15.0, -3.0))
    assert trunk[1] == pytest.approx((25.0, -3.0))
    assert side_of(trunk) == pytest.approx(40.0)


def test_a_symmetric_pythagoras_tree_is_symmetric():
    bounds = PythagorasTree(depth=6, lean=math.pi / 4.0, size=30.0).build().bounds
    assert (bounds.min_x + bounds.max_x) / 2.0 == pytest.approx(0.0, abs=1e-9)


@pytest.mark.parametrize("depth", [0, 1, 2, 7])
def test_the_h_tree_doubles_its_bars_and_shortens_them_by_root_two(depth):
    tree = HTree(depth=depth, size=64.0)
    outlines = list(tree.outlines())
    assert tree.segment_count() == 2 ** (depth + 1) - 1
    assert len(outlines) == tree.segment_count()
    lengths = sorted({round(math.dist(*outline), 6) for outline in outlines})
    assert lengths == sorted(
        {round(64.0 / math.sqrt(2.0) ** level, 6) for level in range(depth + 1)}
    )


def test_the_h_tree_alternates_between_horizontal_and_vertical():
    outlines = list(HTree(depth=1, size=100.0).outlines())
    assert outlines[0][0][1] == outlines[0][1][1]  # the trunk lies flat
    for arm in outlines[1:]:
        assert arm[0][0] == arm[1][0]  # its two arms stand upright


def test_the_apollonian_gasket_has_integer_curvatures():
    # The starting configuration is (-1, 2, 2, 3), and Descartes' theorem
    # produces the next curvature by adding and subtracting the ones already
    # there -- so an integral gasket stays integral forever. Any arithmetic
    # slip in the reflection formula shows up here as a fractional curvature.
    circles = ApollonianGasket(depth=3, radius=1.0).circles()
    for _, radius in circles:
        curvature = 1.0 / radius
        assert curvature == pytest.approx(round(curvature), abs=1e-9)


def test_the_apollonian_circles_pack_without_overlapping():
    circles = ApollonianGasket(depth=2, radius=1.0).circles()
    (outer_center, outer_radius), *inner = circles
    assert outer_radius == pytest.approx(1.0)
    for center, radius in inner:
        assert math.dist(outer_center, center) + radius <= outer_radius + 1e-9
    for i, (center, radius) in enumerate(inner):
        for other_center, other_radius in inner[i + 1 :]:
            assert math.dist(center, other_center) >= radius + other_radius - 1e-9


def test_the_apollonian_seed_circles_are_mutually_tangent():
    circles = ApollonianGasket(depth=0, radius=1.0).circles()
    assert len(circles) == 4
    (_, outer_radius), *inner = circles
    assert sorted(round(1.0 / r) for _, r in inner) == [2, 2, 3]
    for i, (center, radius) in enumerate(inner):
        # Inside the outer circle they touch it from within, and each other
        # from outside.
        assert math.dist((0.0, 0.0), center) == pytest.approx(outer_radius - radius)
        for other_center, other_radius in inner[i + 1 :]:
            assert math.dist(center, other_center) == pytest.approx(radius + other_radius)


def test_the_gasket_scales_and_moves_with_its_parameters():
    bounds = ApollonianGasket(depth=1, radius=60.0, center=(10.0, 20.0)).build().bounds
    assert bounds.width == pytest.approx(120.0, rel=1e-3)
    assert (bounds.min_x + bounds.max_x) / 2.0 == pytest.approx(10.0, abs=1e-3)
    assert (bounds.min_y + bounds.max_y) / 2.0 == pytest.approx(20.0, abs=1e-3)


def test_a_deeper_gasket_holds_more_circles():
    counts = [len(ApollonianGasket(depth=d).circles()) for d in range(4)]
    assert counts == sorted(counts)
    assert counts[0] == 4
    assert counts[-1] > counts[0]


def test_min_radius_stops_the_packing_early():
    coarse = ApollonianGasket(depth=6, min_radius=0.05).circles()
    fine = ApollonianGasket(depth=6, min_radius=0.005).circles()
    assert len(coarse) < len(fine)
    assert all(radius >= 0.05 * 150.0 for _, radius in coarse)


def test_a_runaway_packing_is_refused():
    with pytest.raises(ValueError, match="circles"):
        ApollonianGasket(depth=12, min_radius=1e-9).build()


# --- chance -----------------------------------------------------------------


def test_the_chaos_game_lands_on_the_attractor():
    # The default maps halve towards the corners of a triangle, so every point
    # after the first must be inside that triangle -- and the warmup is there
    # to make sure the first one already is.
    points = IFSAttractor(count=2000, size=2.0, center=(0.0, 0.0)).build().points
    for x, y in points:
        assert -1.0 - 1e-9 <= x <= 1.0 + 1e-9
        assert -1.0 - 1e-9 <= y <= 1.0 + 1e-9


def test_an_attractor_is_scaled_to_the_size_it_is_given():
    bounds = IFSAttractor(count=3000, size=250.0, center=(-40.0, 15.0)).build().bounds
    assert max(bounds.width, bounds.height) == pytest.approx(250.0)
    assert (bounds.min_x + bounds.max_x) / 2.0 == pytest.approx(-40.0)
    assert (bounds.min_y + bounds.max_y) / 2.0 == pytest.approx(15.0)


def test_the_same_seed_gives_the_same_cloud():
    first = IFSAttractor(count=500, seed=7).build().points
    again = IFSAttractor(count=500, seed=7).build().points
    other = IFSAttractor(count=500, seed=8).build().points
    assert first == again
    assert first != other


def test_the_chaos_game_never_touches_the_global_random_stream():
    import random

    random.seed(1234)
    expected = random.random()
    random.seed(1234)
    BarnsleyFern(count=500).build()
    assert random.random() == expected


def test_weights_decide_how_often_each_map_is_chosen():
    # Two maps, one of them almost never taken: the cloud should sit almost
    # entirely on the fixed point of the heavy one.
    maps = (
        IFSMap(Affine(a=0.5, d=0.5, e=0.0, f=0.0), 999.0),
        IFSMap(Affine(a=0.5, d=0.5, e=1.0, f=0.0), 1.0),
    )
    points = IFSAttractor(maps=maps, count=2000, size=1.0, seed=3).build().points
    near_origin = sum(1 for x, _ in points if x < 0.5)
    assert near_origin > 0.9 * len(points)


def test_the_fern_is_taller_than_it_is_wide():
    bounds = BarnsleyFern(count=5000, size=300.0).build().bounds
    assert bounds.height == pytest.approx(300.0)
    assert bounds.width < bounds.height


def test_the_fern_is_a_point_set_rather_than_a_stroke():
    design = BarnsleyFern(count=200).build()
    assert design.paths == ()
    assert len(design.points) == 200


def test_more_points_fill_the_same_fern():
    sparse = BarnsleyFern(count=2000, size=100.0).build().bounds
    dense = BarnsleyFern(count=20000, size=100.0).build().bounds
    assert dense.width == pytest.approx(sparse.width, rel=0.05)
    assert dense.height == pytest.approx(sparse.height)


# --- validation -------------------------------------------------------------


@pytest.mark.parametrize(
    "make",
    [
        lambda: SierpinskiCarpet(depth=-1),
        lambda: SierpinskiCarpet(depth=40),
        lambda: SierpinskiCarpet(size=0.0),
        lambda: CantorSet(depth=-1),
        lambda: CantorSet(width=-1.0),
        lambda: CantorSet(gap=0.0),
        lambda: PythagorasTree(depth=-1),
        lambda: PythagorasTree(size=0.0),
        lambda: PythagorasTree(lean=0.0),
        lambda: PythagorasTree(lean=math.pi / 2.0),
        lambda: HTree(depth=-1),
        lambda: HTree(size=0.0),
        lambda: ApollonianGasket(radius=0.0),
        lambda: ApollonianGasket(min_radius=0.0),
        lambda: ApollonianGasket(min_radius=1.0),
        lambda: IFSAttractor(maps=()),
        lambda: IFSAttractor(count=0),
        lambda: IFSAttractor(count=10_000_000),
        lambda: IFSAttractor(size=0.0),
        lambda: IFSAttractor(maps=(IFSMap(Affine(), 0.0),)),
        lambda: BarnsleyFern(count=0),
        lambda: BarnsleyFern(size=-1.0),
    ],
)
def test_bad_parameters_are_refused(make):
    with pytest.raises(ValueError):
        make()


def test_an_attractor_that_collapses_to_a_point_says_so():
    frozen = (IFSMap(Affine(a=0.0, d=0.0)),)
    with pytest.raises(ValueError, match="single point"):
        IFSAttractor(maps=frozen, count=10).build()


def test_a_runaway_grammar_depth_is_refused():
    with pytest.raises(ValueError, match="symbols"):
        GosperCurve(depth=20).build()


def test_meta_records_the_parameters():
    design = HTree(depth=3, size=64.0).build()
    assert design.meta["motif"] == "fractal.h-tree"
    assert design.meta["depth"] == 3
    assert design.meta["size"] == 64.0
