import math

import pytest

from geomotif.motifs.curves import (
    Astroid,
    BowCurve,
    Butterfly,
    Cardioid,
    CassiniOval,
    Cochleoid,
    Cornoid,
    Cycloid,
    Deltoid,
    FishCurve,
    Folium,
    Heart,
    Lemniscate,
    LemniscateOfGerono,
    Limacon,
    Nephroid,
    Trochoid,
    Witch,
)

# Every curve whose single scale knob is `size`, which the module documents as
# the largest extent of the bounding box.
SIZED = [
    Astroid,
    BowCurve,
    Butterfly,
    Cardioid,
    Cochleoid,
    Cornoid,
    Deltoid,
    FishCurve,
    Heart,
    Lemniscate,
    LemniscateOfGerono,
    Nephroid,
]


def only_path(motif):
    design = motif.build()
    assert len(design.paths) == 1
    return design.paths[0]


def same_points(design, other, *, tol=1e-9):
    """Compare two point streams pairwise; approx() cannot handle pair lists."""
    a, b = list(design), list(other)
    assert len(a) == len(b)
    for first, second in zip(a, b, strict=True):
        assert first == pytest.approx(second, abs=tol)
    return True


def radii(design, center=(0.0, 0.0)):
    return [math.dist(center, point) for point in design]


def count_maxima(values):
    """Count strict local maxima of a cyclic sequence."""
    n = len(values)
    return sum(
        1 for i in range(n) if values[i] > values[i - 1] and values[i] >= values[(i + 1) % n]
    )


# --- the two conventions the whole module rests on --------------------------


@pytest.mark.parametrize("cls", SIZED, ids=lambda c: c.__name__)
def test_size_is_the_curves_largest_extent(cls):
    # This is what checks every hard-coded extent constant in the module: get
    # one wrong and its curve comes out the wrong size here.
    bounds = cls(size=250.0).build().bounds
    assert max(bounds.width, bounds.height) == pytest.approx(250.0, rel=2e-3)


def test_the_heart_is_the_right_size_in_either_form():
    bounds = Heart(size=250.0, form="cardioid").build().bounds
    assert max(bounds.width, bounds.height) == pytest.approx(250.0, rel=2e-3)


@pytest.mark.parametrize("cls", SIZED, ids=lambda c: c.__name__)
def test_center_translates_the_curve_and_nothing_else(cls):
    at_origin = cls(size=100.0).build().bounds
    moved = cls(size=100.0, center=(30.0, -40.0)).build().bounds
    assert moved.min_x - at_origin.min_x == pytest.approx(30.0)
    assert moved.min_y - at_origin.min_y == pytest.approx(-40.0)
    assert (moved.width, moved.height) == pytest.approx((at_origin.width, at_origin.height))


# --- hearts and cardioids ---------------------------------------------------


def test_the_two_hearts_are_not_the_same_curve():
    classic = Heart(size=100.0, form="classic").build()
    cardioid = Heart(size=100.0, form="cardioid").build()
    assert list(classic) != list(cardioid)


def test_the_cardioid_heart_is_a_cardioid_stood_on_end():
    # Both are r = 1 -/+ a sinusoid at the same scale, so their bounding boxes
    # are each other's transposed.
    heart = Heart(size=100.0, form="cardioid").build().bounds
    cardioid = Cardioid(size=100.0).build().bounds
    assert heart.width == pytest.approx(cardioid.height)
    assert heart.height == pytest.approx(cardioid.width)


def test_an_unknown_heart_form_is_refused():
    with pytest.raises(ValueError):
        Heart(form="anatomical").build()  # type: ignore[arg-type]


def test_a_cardioid_is_eight_times_its_defining_radius_around():
    # Perimeter of r = a(1 + cos(theta)) is exactly 8a.
    size = 100.0
    a = size / (3.0 * math.sqrt(3.0) / 2.0)
    assert only_path(Cardioid(size=size)).length == pytest.approx(8.0 * a, rel=1e-4)


def test_a_cardioids_cusp_sits_on_its_center():
    center = (12.0, -7.0)
    assert min(radii(Cardioid(size=100.0, center=center).build(), center)) == pytest.approx(0.0)


# --- lemniscates and ovals --------------------------------------------------


def test_bernoullis_lemniscate_satisfies_its_own_equation():
    size = 120.0
    a = size / 2.0
    for x, y in Lemniscate(size=size).build():
        assert (x * x + y * y) ** 2 == pytest.approx(a * a * (x * x - y * y), abs=1e-6 * a**4)


def test_geronos_lemniscate_satisfies_its_own_equation():
    size = 120.0
    a = size / 2.0
    for x, y in LemniscateOfGerono(size=size).build():
        assert (x / a) ** 4 == pytest.approx((x / a) ** 2 - (y / a) ** 2, abs=1e-9)


def test_the_two_lemniscates_are_different_curves():
    assert list(Lemniscate(size=100.0).build()) != list(LemniscateOfGerono(size=100.0).build())


def test_a_cassini_oval_keeps_the_product_of_its_focal_distances():
    oval = CassiniOval(a=70.0, b=80.0)
    for point in oval.build():
        near = math.dist(point, (-70.0, 0.0))
        far = math.dist(point, (70.0, 0.0))
        assert near * far == pytest.approx(80.0**2, rel=1e-6)


def test_a_cassini_oval_below_the_separation_splits_into_two_lobes():
    design = CassiniOval(a=100.0, b=70.0).build()
    assert len(design.paths) == 2
    for point in design:
        near = math.dist(point, (-100.0, 0.0))
        far = math.dist(point, (100.0, 0.0))
        assert near * far == pytest.approx(70.0**2, rel=1e-4)


def test_the_two_lobes_sit_one_around_each_focus():
    right, left = CassiniOval(a=100.0, b=70.0).build().paths
    assert all(x > 0.0 for x, _ in right.points)
    assert all(x < 0.0 for x, _ in left.points)


def test_a_cassini_oval_above_the_separation_is_one_loop():
    assert len(CassiniOval(a=70.0, b=200.0).build().paths) == 1


@pytest.mark.parametrize(("a", "b"), [(0.0, 10.0), (-1.0, 10.0), (10.0, 0.0), (10.0, -1.0)])
def test_a_cassini_oval_needs_positive_parameters(a, b):
    with pytest.raises(ValueError):
        CassiniOval(a=a, b=b)


def test_the_degenerate_cassini_oval_points_at_the_lemniscate():
    with pytest.raises(ValueError, match="Lemniscate"):
        CassiniOval(a=50.0, b=50.0)


# --- limacon and folium -----------------------------------------------------


def test_a_limacon_with_equal_terms_is_a_cardioid():
    assert same_points(
        Limacon(a=40.0, b=40.0).build(),
        Cardioid(size=40.0 * 3.0 * math.sqrt(3.0) / 2.0).build(),
    )


def test_a_looped_limacon_passes_through_its_pole_twice():
    # The inner loop only exists because a negative radius reflects instead of
    # being clipped; if it were clipped the curve would never reach the pole.
    design = Limacon(a=100.0, b=60.0).build()
    assert min(radii(design)) == pytest.approx(0.0, abs=1.0)
    assert count_maxima(radii(design)) == 2


def test_a_convex_limacon_has_no_dimple_and_no_loop():
    design = Limacon(a=30.0, b=100.0).build()
    assert min(radii(design)) == pytest.approx(70.0, rel=1e-3)
    assert count_maxima(radii(design)) == 1


@pytest.mark.parametrize(
    ("a", "b", "petals"), [(100.0, 100.0, 3), (100.0, 0.0, 2), (25.0, 100.0, 1)]
)
def test_the_folium_has_the_petals_its_two_numbers_ask_for(a, b, petals):
    assert count_maxima(radii(Folium(a=a, b=b).build())) == petals


def test_half_a_revolution_draws_the_whole_folium():
    path = only_path(Folium())
    assert path.closed
    assert Folium.domain == (0.0, math.pi)
    # The stroke really does come home: the seam it implies is a hair long,
    # not a chord across the figure.
    assert math.dist(path.points[0], path.points[-1]) < 1.0


# --- the classical named curves ---------------------------------------------


def test_an_astroid_satisfies_its_own_equation():
    size = 140.0
    a = size / 2.0
    for x, y in Astroid(size=size).build():
        assert abs(x) ** (2 / 3) + abs(y) ** (2 / 3) == pytest.approx(a ** (2 / 3), rel=1e-9)


def test_an_astroid_is_three_sizes_around():
    # Perimeter of x = a cos(t)**3 is 6a, and size is 2a.
    assert only_path(Astroid(size=100.0)).length == pytest.approx(300.0, rel=1e-4)


def test_a_deltoid_is_sixteen_times_its_defining_radius_around():
    a = 100.0 / (3.0 * math.sqrt(3.0))
    assert only_path(Deltoid(size=100.0)).length == pytest.approx(16.0 * a, rel=1e-4)


def test_a_nephroid_is_twenty_four_times_its_defining_radius_around():
    a = 100.0 / 8.0
    assert only_path(Nephroid(size=100.0)).length == pytest.approx(24.0 * a, rel=1e-4)


@pytest.mark.parametrize(("cls", "cusps"), [(Astroid, 4), (Deltoid, 3), (Nephroid, 2)])
def test_the_cusped_curves_have_the_cusps_they_are_named_for(cls, cusps):
    # A cusp is where the curve reaches furthest from its center and turns
    # back, so counting radial maxima counts cusps.
    assert count_maxima(radii(cls(size=100.0).build())) == cusps


def test_a_bow_curve_pinches_at_its_center():
    bow = BowCurve(size=100.0, center=(5.0, 6.0))
    assert bow.position(-1.0) == pytest.approx((5.0, 6.0))
    assert bow.position(1.0) == pytest.approx((5.0, 6.0))


def test_a_bow_curve_sits_entirely_above_its_center():
    # y = t**2 - t**4 is non-negative across the whole domain.
    assert all(y >= 6.0 - 1e-9 for _, y in BowCurve(size=100.0, center=(5.0, 6.0)).build())


def test_the_fish_curve_closes():
    assert only_path(FishCurve()).closed


def test_the_butterfly_takes_twelve_turns_to_close():
    assert Butterfly().sweep_turns() == pytest.approx(12.0)
    assert only_path(Butterfly()).closed


def test_the_cornoid_is_symmetric_about_its_center_line():
    bounds = Cornoid(size=100.0, center=(0.0, 0.0)).build().bounds
    assert bounds.min_y == pytest.approx(-bounds.max_y)
    assert bounds.min_x == pytest.approx(-bounds.max_x)


# --- cochleoid --------------------------------------------------------------


def test_the_cochleoid_radius_is_sin_theta_over_theta():
    cochleoid = Cochleoid(size=100.0, loops=3)
    scale = 100.0 / 1.4492227075519726
    for u in (0.05, 0.2, 0.37, 0.6, 0.81, 0.95):
        theta = (2.0 * u - 1.0) * 3.0 * math.pi
        expected = abs(scale * math.sin(theta) / theta)
        assert math.dist((0.0, 0.0), cochleoid.position(u)) == pytest.approx(expected)


def test_the_cochleoid_is_finite_at_the_pole():
    scale = 100.0 / 1.4492227075519726
    assert Cochleoid(size=100.0).position(0.5) == pytest.approx((scale, 0.0))


def test_the_cochleoid_is_symmetric_about_the_x_axis():
    bounds = Cochleoid(size=100.0).build().bounds
    assert bounds.min_y == pytest.approx(-bounds.max_y)


def test_extra_cochleoid_loops_nest_inside_the_first():
    one = Cochleoid(size=100.0, loops=1).build().bounds
    many = Cochleoid(size=100.0, loops=6).build().bounds
    assert (many.width, many.height) == pytest.approx((one.width, one.height), rel=1e-3)


def test_a_cochleoid_needs_at_least_one_loop():
    with pytest.raises(ValueError):
        Cochleoid(loops=0)


# --- cycloid and trochoid ---------------------------------------------------


def test_a_cycloid_arch_is_eight_radii_long():
    assert only_path(Cycloid(radius=10.0, arches=3)).length == pytest.approx(240.0, rel=1e-4)


def test_a_cycloid_arch_is_a_circumference_wide_and_two_radii_tall():
    bounds = Cycloid(radius=10.0, arches=1).build().bounds
    assert (bounds.width, bounds.height) == pytest.approx((math.tau * 10.0, 20.0))


def test_a_cycloid_starts_on_the_ground_at_its_center():
    assert only_path(Cycloid(center=(3.0, 4.0))).points[0] == pytest.approx((3.0, 4.0))


def test_a_trochoid_with_its_point_on_the_rim_is_a_cycloid():
    assert same_points(
        Trochoid(radius=25.0, arm=25.0, arches=2).build(),
        Cycloid(radius=25.0, arches=2).build(),
    )


def test_a_prolate_trochoid_runs_backwards_and_a_curtate_one_does_not():
    prolate = Trochoid(radius=20.0, arm=40.0, arches=2).build().bounds
    curtate = Trochoid(radius=20.0, arm=10.0, arches=2).build().bounds
    assert prolate.min_x < 0.0
    assert curtate.min_x >= 0.0


@pytest.mark.parametrize(
    "kwargs",
    [{"radius": 0.0}, {"radius": -1.0}, {"arches": 0}],
)
def test_a_cycloid_needs_a_wheel_and_an_arch(kwargs):
    with pytest.raises(ValueError):
        Cycloid(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [{"radius": 0.0}, {"arm": -1.0}, {"arches": 0}],
)
def test_a_trochoid_validates_its_wheel(kwargs):
    with pytest.raises(ValueError):
        Trochoid(**kwargs)


# --- witch of agnesi --------------------------------------------------------


def test_the_witch_satisfies_its_own_equation():
    a = 30.0
    for x, y in Witch(radius=a).build():
        assert y == pytest.approx(8.0 * a**3 / (x * x + 4.0 * a * a))


def test_the_witch_peaks_at_twice_its_radius_above_its_center():
    bounds = Witch(radius=30.0, center=(4.0, 5.0)).build().bounds
    assert bounds.max_y == pytest.approx(5.0 + 60.0)
    assert bounds.max_x == pytest.approx(4.0 + 60.0 * 3.0)


@pytest.mark.parametrize("kwargs", [{"radius": 0.0}, {"extent": 0.0}, {"extent": -2.0}])
def test_the_witch_validates_its_circle(kwargs):
    with pytest.raises(ValueError):
        Witch(**kwargs)
