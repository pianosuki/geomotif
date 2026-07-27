import itertools
import math

import pytest

from geomotif.motifs.primitives import (
    Arc,
    Circle,
    Egg,
    Ellipse,
    Line,
    PointGrid,
    PoissonDiscPoints,
    Rectangle,
    RegularPolygon,
    ReuleauxPolygon,
    RoundedRectangle,
    Sector,
    Squircle,
    Star,
    StarPolygon,
    Superellipse,
)


def only_path(motif):
    design = motif.build()
    assert len(design.paths) == 1
    return design.paths[0]


# --- circles, ellipses, arcs ------------------------------------------------


def test_a_circle_has_the_circumference_it_should():
    # A 512-segment polyline undercuts the true circumference by about 2e-5
    # relative, which is the whole reason the tolerance is not exact.
    assert only_path(Circle(radius=50.0)).length == pytest.approx(math.tau * 50.0, rel=1e-4)


def test_a_circle_is_closed_and_does_not_repeat_its_seam():
    path = only_path(Circle())
    assert path.closed
    assert path.points[0] != path.points[-1]


def test_a_circle_sits_where_it_is_told():
    bounds = Circle(radius=10.0, center=(100.0, -5.0)).build().bounds
    assert bounds.center == pytest.approx((100.0, -5.0))
    assert (bounds.width, bounds.height) == pytest.approx((20.0, 20.0))


def test_an_ellipse_with_equal_axes_is_a_circle():
    ellipse = list(Ellipse(rx=30.0, ry=30.0).build())
    assert all(math.dist((0.0, 0.0), p) == pytest.approx(30.0) for p in ellipse)


def test_rotating_an_ellipse_by_a_quarter_turn_swaps_its_extents():
    upright = Ellipse(rx=100.0, ry=40.0).build().bounds
    turned = Ellipse(rx=100.0, ry=40.0, rotation=math.pi / 2).build().bounds
    assert turned.width == pytest.approx(upright.height)
    assert turned.height == pytest.approx(upright.width)


def test_an_arc_is_as_long_as_its_radius_times_its_sweep():
    arc = Arc(radius=20.0, sweep=math.pi / 3)
    assert only_path(arc).length == pytest.approx(20.0 * math.pi / 3, rel=1e-4)


def test_an_arc_starts_and_ends_where_its_angles_say():
    path = only_path(Arc(radius=10.0, start_angle=0.0, sweep=math.pi / 2))
    assert path.points[0] == pytest.approx((10.0, 0.0))
    assert path.points[-1] == pytest.approx((0.0, 10.0))


def test_a_negative_sweep_runs_clockwise():
    path = only_path(Arc(radius=10.0, start_angle=0.0, sweep=-math.pi / 2))
    assert path.points[-1] == pytest.approx((0.0, -10.0))


def test_a_sector_starts_at_its_center_and_closes():
    path = only_path(Sector(radius=10.0, sweep=math.pi / 2, center=(1.0, 2.0)))
    assert path.points[0] == (1.0, 2.0)
    assert path.closed


def test_a_sector_is_its_arc_plus_two_radii():
    sector = Sector(radius=10.0, sweep=math.pi / 2)
    assert only_path(sector).length == pytest.approx(10.0 * math.pi / 2 + 20.0, rel=1e-4)


def test_a_sector_of_no_angle_is_rejected():
    with pytest.raises(ValueError, match="non-zero"):
        Sector(sweep=0.0)


# --- straight-edged shapes --------------------------------------------------


def test_a_line_is_two_points():
    path = only_path(Line(start=(0.0, 0.0), end=(3.0, 4.0)))
    assert path.points == ((0.0, 0.0), (3.0, 4.0))
    assert not path.closed
    assert path.length == pytest.approx(5.0)


def test_a_rectangle_is_four_corners_and_its_own_perimeter():
    path = only_path(Rectangle(width=8.0, height=6.0))
    assert len(path.points) == 4
    assert path.length == pytest.approx(28.0)


def test_a_rectangle_is_centered():
    bounds = Rectangle(width=8.0, height=6.0, center=(10.0, 20.0)).build().bounds
    assert bounds.center == pytest.approx((10.0, 20.0))


def test_a_regular_polygon_has_one_corner_per_side():
    assert len(only_path(RegularPolygon(sides=7)).points) == 7


def test_every_corner_of_a_regular_polygon_is_on_the_circumcircle():
    for x, y in RegularPolygon(sides=9, radius=25.0).build():
        assert math.dist((0.0, 0.0), (x, y)) == pytest.approx(25.0)


def test_a_regular_polygon_has_the_perimeter_the_formula_gives():
    sides, radius = 11, 30.0
    expected = 2 * sides * radius * math.sin(math.pi / sides)
    assert only_path(RegularPolygon(sides=sides, radius=radius)).length == pytest.approx(expected)


def test_a_regular_polygon_points_up_by_default():
    assert only_path(RegularPolygon(sides=5, radius=10.0)).points[0] == pytest.approx((0.0, 10.0))


def test_a_polygon_needs_three_sides():
    with pytest.raises(ValueError, match="sides must be >= 3"):
        RegularPolygon(sides=2)


def test_a_rounded_rectangle_keeps_its_stated_size():
    bounds = RoundedRectangle(width=80.0, height=50.0, corner_radius=10.0).build().bounds
    assert (bounds.width, bounds.height) == pytest.approx((80.0, 50.0), rel=1e-4)


def test_a_rounded_rectangle_is_four_straights_and_one_circle():
    width, height, radius = 80.0, 50.0, 10.0
    expected = 2 * (width - 2 * radius) + 2 * (height - 2 * radius) + math.tau * radius
    path = only_path(RoundedRectangle(width=width, height=height, corner_radius=radius))
    assert path.length == pytest.approx(expected, rel=1e-4)


def test_a_rounded_rectangle_with_no_radius_is_a_plain_rectangle():
    # The arcs would otherwise stamp their center out once per segment.
    path = only_path(RoundedRectangle(width=8.0, height=6.0, corner_radius=0.0))
    assert len(path.points) == 4
    assert path.length == pytest.approx(28.0)


def test_a_corner_radius_larger_than_the_shape_is_rejected():
    with pytest.raises(ValueError, match="corner_radius"):
        RoundedRectangle(width=80.0, height=50.0, corner_radius=25.1)


def test_a_negative_corner_radius_is_rejected():
    with pytest.raises(ValueError, match="corner_radius"):
        RoundedRectangle(corner_radius=-1.0)


# --- stars ------------------------------------------------------------------


def test_a_pentagram_is_one_stroke_of_five_corners():
    design = StarPolygon(points=5, step=2).build()
    assert len(design.paths) == 1
    assert len(design.paths[0].points) == 5


def test_the_star_of_david_is_two_triangles():
    design = StarPolygon(points=6, step=2).build()
    assert len(design.paths) == 2
    assert all(len(path.points) == 3 for path in design.paths)


def test_an_eight_pointed_star_with_a_coprime_step_stays_one_stroke():
    design = StarPolygon(points=8, step=3).build()
    assert len(design.paths) == 1
    assert len(design.paths[0].points) == 8


def test_a_star_polygon_needs_at_least_five_points():
    with pytest.raises(ValueError, match="points must be >= 5"):
        StarPolygon(points=4, step=2)


def test_step_one_is_rejected_as_a_convex_polygon():
    with pytest.raises(ValueError, match="step must be"):
        StarPolygon(points=7, step=1)


def test_a_step_of_half_the_points_is_rejected_as_diameters():
    with pytest.raises(ValueError, match="step must be"):
        StarPolygon(points=8, step=4)


def test_a_star_alternates_outer_and_inner_corners():
    star = Star(points=5, radius=10.0, inner_ratio=0.5)
    distances = [math.dist((0.0, 0.0), p) for p in star.build()]
    assert len(distances) == 10
    assert distances[0::2] == pytest.approx([10.0] * 5)
    assert distances[1::2] == pytest.approx([5.0] * 5)


def test_a_star_may_have_an_even_number_of_arms():
    # The whole reason Star exists alongside StarPolygon: {6/k} cannot be
    # drawn in one stroke, but a six-armed star can.
    design = Star(points=6).build()
    assert len(design.paths) == 1
    assert len(design.paths[0].points) == 12


def test_a_star_needs_at_least_three_arms():
    with pytest.raises(ValueError, match="points must be >= 3"):
        Star(points=2)


@pytest.mark.parametrize("ratio", [0.0, 1.0, -0.5, 2.0])
def test_an_inner_ratio_outside_the_unit_interval_is_rejected(ratio):
    with pytest.raises(ValueError, match="inner_ratio"):
        Star(inner_ratio=ratio)


# --- superellipses and eggs -------------------------------------------------


def test_a_superellipse_of_exponent_two_is_an_ellipse():
    superellipse = list(Superellipse(exponent=2.0, rx=40.0, ry=20.0).build())
    ellipse = list(Ellipse(rx=40.0, ry=20.0).build())
    assert superellipse == pytest.approx(ellipse)


@pytest.mark.parametrize("exponent", [0.5, 1.0, 2.5, 4.0, 8.0])
def test_every_superellipse_point_satisfies_its_own_equation(exponent):
    rx, ry = 30.0, 20.0
    for x, y in Superellipse(exponent=exponent, rx=rx, ry=ry).build():
        assert abs(x / rx) ** exponent + abs(y / ry) ** exponent == pytest.approx(1.0)


def test_a_superellipse_needs_a_positive_exponent():
    with pytest.raises(ValueError, match="exponent"):
        Superellipse(exponent=0.0)


def test_a_squircle_is_the_fourth_power_superellipse():
    assert list(Squircle(radius=25.0).build()) == pytest.approx(
        list(Superellipse(exponent=4.0, rx=25.0, ry=25.0).build())
    )


def test_a_squircle_encloses_more_than_a_circle_of_the_same_radius():
    # It reaches the corners of its bounding box further than a circle does,
    # which is the entire point of the shape.
    squircle = Squircle(radius=10.0).build()
    diagonal = max(math.dist((0.0, 0.0), p) for p in squircle)
    assert diagonal > 10.0


def test_an_egg_without_taper_is_an_ellipse():
    egg = list(Egg(length=80.0, width=50.0, taper=0.0).build())
    ellipse = list(Ellipse(rx=40.0, ry=25.0).build())
    assert egg == pytest.approx(ellipse)


def test_an_egg_is_fatter_at_one_end():
    egg = Egg(length=100.0, width=60.0, taper=0.4).build()
    right = max(y for x, y in egg if x > 25.0)
    left = max(y for x, y in egg if x < -25.0)
    assert right > left


@pytest.mark.parametrize("taper", [1.0, -1.0, 1.5])
def test_a_taper_at_or_past_one_is_rejected(taper):
    with pytest.raises(ValueError, match="taper"):
        Egg(taper=taper)


# --- constant width ---------------------------------------------------------


def support_width(points, angle):
    """Return the extent of ``points`` measured along ``angle``."""
    projections = [x * math.cos(angle) + y * math.sin(angle) for x, y in points]
    return max(projections) - min(projections)


@pytest.mark.parametrize("sides", [3, 5, 7])
def test_a_reuleaux_polygon_is_the_same_width_in_every_direction(sides):
    points = list(ReuleauxPolygon(sides=sides, width=100.0).build())
    for i in range(24):
        # Sampling the arcs as a polyline shaves a hair off the extremes,
        # which is where the tolerance comes from.
        assert support_width(points, i * math.pi / 24) == pytest.approx(100.0, rel=1e-3)


def test_a_reuleaux_polygon_is_closed_without_a_repeated_seam():
    path = only_path(ReuleauxPolygon(sides=3))
    assert path.closed
    assert math.dist(path.points[0], path.points[-1]) > 0.0


def test_a_reuleaux_triangle_has_the_perimeter_barbier_predicts():
    # Barbier's theorem: every curve of constant width w has perimeter pi*w.
    assert only_path(ReuleauxPolygon(sides=3, width=60.0)).length == pytest.approx(
        math.pi * 60.0, rel=1e-4
    )


@pytest.mark.parametrize("sides", [2, 4, 6])
def test_an_even_sided_reuleaux_polygon_is_rejected(sides):
    with pytest.raises(ValueError, match="odd"):
        ReuleauxPolygon(sides=sides)


def test_a_reuleaux_polygon_needs_a_positive_width():
    with pytest.raises(ValueError, match="width"):
        ReuleauxPolygon(width=0.0)


# --- point fields -----------------------------------------------------------


def test_a_grid_has_one_point_per_cell():
    design = PointGrid(columns=4, rows=3).build()
    assert len(design.points) == 12
    assert design.paths == ()


def test_a_grid_is_centered_on_its_center():
    bounds = PointGrid(columns=5, rows=5, dx=10.0, dy=10.0, center=(3.0, 7.0)).build().bounds
    assert bounds.center == pytest.approx((3.0, 7.0))
    assert (bounds.width, bounds.height) == pytest.approx((40.0, 40.0))


def test_stagger_offsets_alternate_rows():
    plain = PointGrid(columns=2, rows=2, dx=10.0, dy=10.0).build().points
    staggered = PointGrid(columns=2, rows=2, dx=10.0, dy=10.0, stagger=0.5).build().points
    assert staggered[0] == plain[0]
    assert staggered[2][0] == pytest.approx(plain[2][0] + 5.0)


def test_an_empty_grid_is_rejected():
    with pytest.raises(ValueError, match="columns and rows"):
        PointGrid(columns=0)


def test_poisson_points_never_come_closer_than_the_minimum():
    points = PoissonDiscPoints(width=200.0, height=200.0, min_distance=25.0).build().points
    assert len(points) > 10
    for a, b in itertools.combinations(points, 2):
        assert math.dist(a, b) >= 25.0 - 1e-9


def test_poisson_points_stay_inside_their_area():
    field = PoissonDiscPoints(width=100.0, height=60.0, center=(5.0, -5.0)).build()
    bounds = field.bounds
    assert bounds.min_x >= -45.0
    assert bounds.max_x <= 55.0
    assert bounds.min_y >= -35.0
    assert bounds.max_y <= 25.0


def test_the_same_seed_gives_the_same_field():
    first = PoissonDiscPoints(seed=7).build().points
    second = PoissonDiscPoints(seed=7).build().points
    assert first == second


def test_a_different_seed_gives_a_different_field():
    assert PoissonDiscPoints(seed=1).build().points != PoissonDiscPoints(seed=2).build().points


def test_poisson_does_not_disturb_the_global_random_stream():
    # A motif that reached for the module-level random would make every
    # design after it depend on how many were built before.
    import random

    random.seed(1234)
    expected = random.random()
    random.seed(1234)
    PoissonDiscPoints(seed=99).build()
    assert random.random() == expected


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"width": 0.0}, "width and height"),
        ({"height": -1.0}, "width and height"),
        ({"min_distance": 0.0}, "min_distance"),
        ({"attempts": 0}, "attempts"),
    ],
)
def test_poisson_rejects_impossible_parameters(kwargs, match):
    with pytest.raises(ValueError, match=match):
        PoissonDiscPoints(**kwargs)


def test_poisson_refuses_a_spacing_that_would_scatter_millions():
    with pytest.raises(ValueError, match="limit"):
        PoissonDiscPoints(width=10_000.0, height=10_000.0, min_distance=0.5)
