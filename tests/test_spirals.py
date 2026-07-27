import itertools
import math

import pytest

from geomotif import PowerSpacing
from geomotif.motifs import (
    PHI,
    ArchimedeanSpiral,
    CircleInvolute,
    EulerSpiral,
    FermatSpiral,
    FibonacciSpiral,
    GoldenSpiral,
    HyperbolicSpiral,
    Lituus,
    LogarithmicSpiral,
    SpiralBetween,
    TheodorusSpiral,
)
from geomotif.motifs.spirals import _fresnel


def gaps(points):
    return [math.dist(a, b) for a, b in itertools.pairwise(points)]


def only_path(motif):
    design = motif.build()
    assert len(design.paths) == 1
    return design.paths[0]


def first_point(motif):
    return only_path(motif).points[0]


def test_endpoints_exact():
    points = list(SpiralBetween((200, 0), (20, 0), turns=3).generate(120))
    assert points[0] == pytest.approx((200, 0))
    assert points[-1] == pytest.approx((20, 0))


def test_point_count():
    assert len(SpiralBetween((200, 0), (20, 0), turns=2).generate(57)) == 57


def test_default_center_is_origin():
    points = list(SpiralBetween((100, 0), (50, 0), turns=1).generate(20))
    radii = [math.dist(p, (0, 0)) for p in points]
    assert radii[0] == pytest.approx(100)
    assert radii[-1] == pytest.approx(50)


def test_equal_spacing_is_equal_real_distance():
    points = list(SpiralBetween((200, 0), (20, 0), turns=3).generate(120))
    g = gaps(points)
    # Chord lengths vary slightly from arc lengths in the tight center;
    # they must still be equal to within a few percent.
    assert max(g) / min(g) < 1.05


def test_radial_line_gaps_exact():
    points = list(SpiralBetween((0, 0), (200, 0)).generate(11))
    for gap in gaps(points):
        assert gap == pytest.approx(20.0, abs=1e-6)


def test_power_spacing_increases_gaps():
    design = SpiralBetween((200, 0), (20, 0), turns=2).generate(40, spacing=PowerSpacing(2))
    g = gaps(list(design))
    assert g[0] < g[len(g) // 2] < g[-1]


def test_power_out_decreases_gaps():
    design = SpiralBetween((200, 0), (20, 0), turns=2).generate(
        40, spacing=PowerSpacing(2, mode="out")
    )
    g = gaps(list(design))
    assert g[0] > g[len(g) // 2] > g[-1]


def test_clockwise_vs_counterclockwise():
    # Math convention, y-up: counter-clockwise initially moves +y from
    # a point right of center; clockwise moves -y.
    ccw = list(SpiralBetween((100, 0), (0, 100), clockwise=False).generate(50))
    cw = list(SpiralBetween((100, 0), (0, -100), clockwise=True).generate(50))
    assert ccw[1][1] > 0
    assert cw[1][1] < 0


def test_flipping_y_reverses_the_apparent_direction():
    # The old y_down flag is gone: mirroring the design is strictly more
    # general, and this is the identity that makes it equivalent. A spiral
    # mirrored about the x-axis is the mirrored-endpoint spiral wound the
    # other way.
    flipped = SpiralBetween((100, 0), (0, 100), turns=1, clockwise=True).build().flipped_y()
    expected = SpiralBetween((100, 0), (0, -100), turns=1, clockwise=False).build()
    for a, b in zip(flipped.paths[0].points, expected.paths[0].points, strict=True):
        assert a == pytest.approx(b, abs=1e-9)


def test_turns_add_full_revolutions():
    points = list(SpiralBetween((100, 0), (100, 0), turns=2, clockwise=False).generate(500))
    assert math.dist(points[0], points[-1]) < 1e-9
    total_length = sum(gaps(points))
    # Two full circles of radius 100, minus polyline shortfall.
    assert total_length == pytest.approx(2 * 2 * math.pi * 100, rel=1e-3)


def test_start_at_center_degenerates_to_radial_line():
    points = list(SpiralBetween((0, 0), (200, 0)).generate(10))
    assert points[0] == pytest.approx((0, 0))
    assert points[-1] == pytest.approx((200, 0))
    assert all(y == pytest.approx(0.0, abs=1e-9) for _, y in points)


def test_end_at_center_degenerates_to_radial_line():
    points = list(SpiralBetween((200, 0), (0, 0)).generate(10))
    assert all(y == pytest.approx(0.0, abs=1e-9) for _, y in points)


def test_start_equals_end_no_sweep():
    points = list(SpiralBetween((50, 50), (50, 50)).generate(5))
    assert all(p == pytest.approx((50, 50)) for p in points)


def test_both_endpoints_at_center():
    points = list(SpiralBetween((0, 0), (0, 0)).generate(4))
    assert all(p == pytest.approx((0, 0)) for p in points)


def test_parametric_mode_compresses_toward_center():
    design = SpiralBetween((200, 0), (20, 0), turns=3).generate(120, by="parameter")
    g = gaps(list(design))
    assert max(g) / min(g) > 3  # visibly unequal, unlike arc-length mode


def test_custom_callable_spacing():
    design = SpiralBetween((200, 0), (20, 0), turns=1).generate(30, spacing=lambda t: t * t)
    points = list(design)
    assert len(points) == 30
    assert points[0] == pytest.approx((200, 0))


def test_custom_center():
    design = SpiralBetween((400, 150), (350, 150), center=(300, 150), turns=1).generate(20)
    radii = [math.dist(p, (300, 150)) for p in design]
    assert radii[0] == pytest.approx(100)
    assert radii[-1] == pytest.approx(50)


def test_step_mode_gives_fixed_gaps():
    design = SpiralBetween((200, 0), (20, 0), turns=3).generate(step=10.0)
    g = gaps(list(design))
    # Gaps are exactly 10 *along the curve*; measured as straight lines they
    # fall a little short wherever the spiral is winding tightly, and a
    # 10-unit step near radius 20 cuts a visible corner.
    assert all(9.8 <= gap <= 10.0 + 1e-9 for gap in g)


def test_resolution_override_changes_measurement_density():
    coarse = SpiralBetween((200, 0), (20, 0), turns=3, resolution=8).build()
    assert len(coarse.paths[0]) == 9


def test_build_records_reproducible_meta():
    meta = SpiralBetween((200, 0), (20, 0), turns=3).build().meta
    assert meta["motif"] == "spiral.between"
    assert meta["turns"] == 3
    assert meta["clockwise"] is True


def test_invalid_args_rejected():
    with pytest.raises(ValueError):
        SpiralBetween((0, 0), (1, 1), turns=-1)
    with pytest.raises(ValueError):
        SpiralBetween((0, 0), (1, 1), resolution=0)
    with pytest.raises(ValueError):
        SpiralBetween((0, 0), (1, 1)).generate(1)
    with pytest.raises(TypeError):
        SpiralBetween((0, 0), (1, 1)).generate(10, spacing="linear")  # type: ignore[arg-type]


# --- the polar spiral family ------------------------------------------------


def test_a_spiral_sweeps_three_turns_by_default():
    # One revolution of a spiral barely reads as one, so the family default
    # differs from PolarMotif's.
    assert ArchimedeanSpiral().theta_span == pytest.approx(3 * math.tau)


def test_with_turns_sets_the_sweep_in_revolutions():
    assert LogarithmicSpiral().with_turns(5).theta_span == pytest.approx(5 * math.tau)


def test_with_turns_clockwise_reverses_the_sweep():
    assert LogarithmicSpiral().with_turns(5, clockwise=True).theta_span == pytest.approx(
        -5 * math.tau
    )


def test_a_clockwise_spiral_mirrors_its_counter_clockwise_twin():
    # Mirrored in x rather than y: a negative angle gives r = b*theta a
    # negative radius, and PolarMotif places a negative radius on the
    # opposite ray. The curve still winds the other way, which is the point.
    right = list(ArchimedeanSpiral().with_turns(2).build())
    left = list(ArchimedeanSpiral().with_turns(2, clockwise=True).build())
    assert [(-x, y) for x, y in right] == pytest.approx(left)


def test_with_turns_keeps_every_other_parameter():
    spiral = ArchimedeanSpiral(a=3.0, b=7.0, center=(1.0, 2.0)).with_turns(4)
    assert (spiral.a, spiral.b, spiral.center) == (3.0, 7.0, (1.0, 2.0))


def test_successive_archimedean_turns_are_evenly_spaced():
    # The defining property: r = a + b*theta puts every winding the same
    # radial distance from the last.
    spiral = ArchimedeanSpiral(a=5.0, b=2.0)
    for theta in (0.5, 3.0, 11.0):
        gap = spiral.radius(theta + math.tau) - spiral.radius(theta)
        assert gap == pytest.approx(2.0 * math.tau)


def test_an_archimedean_spiral_starts_at_its_inner_radius():
    assert first_point(ArchimedeanSpiral(a=5.0, b=2.0)) == pytest.approx((5.0, 0.0))


def test_successive_logarithmic_turns_grow_by_a_constant_factor():
    spiral = LogarithmicSpiral(a=1.0, b=0.3)
    ratios = [spiral.radius(t + math.tau) / spiral.radius(t) for t in (0.0, 2.0, 9.0)]
    assert ratios == pytest.approx([math.exp(0.3 * math.tau)] * 3)


def test_a_logarithmic_spiral_with_no_growth_is_a_circle():
    points = list(LogarithmicSpiral(a=10.0, b=0.0).build())
    assert all(math.dist((0.0, 0.0), p) == pytest.approx(10.0) for p in points)


def test_the_golden_spiral_widens_by_phi_every_quarter_turn():
    spiral = GoldenSpiral(a=1.0)
    for theta in (0.0, 1.0, 5.0):
        ratio = spiral.radius(theta + math.pi / 2) / spiral.radius(theta)
        assert ratio == pytest.approx(PHI)


def test_the_golden_spiral_is_a_logarithmic_spiral_with_a_fixed_growth():
    golden = GoldenSpiral(a=2.0).build()
    same = LogarithmicSpiral(a=2.0, b=GoldenSpiral.GROWTH).with_turns(2).build()
    assert list(golden) == pytest.approx(list(same))


def test_fermat_squares_its_radius_against_the_angle():
    spiral = FermatSpiral(a=4.0)
    for theta in (0.5, 3.0, 15.0):
        assert spiral.radius(theta) ** 2 == pytest.approx(16.0 * theta)


def test_fermat_draws_both_arms_by_default():
    assert len(FermatSpiral().build().paths) == 2


def test_the_second_fermat_arm_is_the_first_reflected_through_the_center():
    design = FermatSpiral(center=(5.0, -3.0)).build()
    first, second = design.paths
    mirrored = [(10.0 - x, -6.0 - y) for x, y in first.points]
    assert list(second.points) == pytest.approx(mirrored)


def test_one_fermat_arm_can_be_asked_for():
    assert len(FermatSpiral(both_branches=False).build().paths) == 1


def test_fermat_rejects_a_sweep_into_negative_angles():
    with pytest.raises(ValueError, match="square root"):
        FermatSpiral(theta_start=-1.0)


def test_the_hyperbolic_spiral_keeps_radius_times_angle_constant():
    spiral = HyperbolicSpiral(a=50.0)
    for theta in (0.2, 4.0, 18.0):
        assert spiral.radius(theta) * theta == pytest.approx(50.0)


def test_the_lituus_keeps_radius_squared_times_angle_constant():
    spiral = Lituus(a=50.0)
    for theta in (0.2, 4.0, 18.0):
        assert spiral.radius(theta) ** 2 * theta == pytest.approx(2500.0)


@pytest.mark.parametrize("cls", [HyperbolicSpiral, Lituus])
def test_a_spiral_with_a_pole_refuses_to_sweep_through_zero(cls):
    with pytest.raises(ValueError, match="pole"):
        cls(theta_start=0.0)


@pytest.mark.parametrize("cls", [HyperbolicSpiral, Lituus])
def test_a_spiral_with_a_pole_refuses_a_sweep_that_straddles_it(cls):
    with pytest.raises(ValueError, match="pole"):
        cls(theta_start=-1.0, theta_span=2.0)


def test_the_lituus_refuses_a_sweep_below_the_pole():
    # Unlike the hyperbolic spiral it cannot take the negative branch at all:
    # its radius is a square root, so there is nothing there to draw.
    with pytest.raises(ValueError, match="square root"):
        Lituus(theta_start=-1.0, theta_span=-5.0)


def test_a_hyperbolic_spiral_may_sweep_entirely_below_the_pole():
    # Negative angles are a perfectly good branch; only crossing zero is not.
    assert len(HyperbolicSpiral(theta_start=-1.0, theta_span=-5.0).build()) > 0


# --- the spirals that are not polar functions -------------------------------


def test_theodorus_puts_its_nth_vertex_at_the_root_of_n():
    corners = only_path(TheodorusSpiral(triangles=12, size=3.0)).points
    for index, point in enumerate(corners):
        assert math.dist((0.0, 0.0), point) == pytest.approx(3.0 * math.sqrt(index + 1))


def test_every_theodorus_triangle_adds_a_leg_of_the_same_length():
    corners = only_path(TheodorusSpiral(triangles=12, size=3.0)).points
    assert gaps(corners) == pytest.approx([3.0] * 12)


def test_theodorus_is_drawn_as_an_open_chain():
    assert not only_path(TheodorusSpiral()).closed


def test_theodorus_needs_at_least_one_triangle():
    with pytest.raises(ValueError, match="triangles"):
        TheodorusSpiral(triangles=0)


def test_the_fibonacci_spiral_uses_fibonacci_radii():
    assert FibonacciSpiral(quarters=8, size=2.0)._radii() == [2, 2, 4, 6, 10, 16, 26, 42]


def test_the_fibonacci_arcs_join_without_a_jump():
    # Each arc's center is shifted so the next starts exactly where the last
    # ended. A sign error there leaves a gap, and the polyline gets longer
    # than the arcs it is supposed to be made of.
    spiral = FibonacciSpiral(quarters=9, size=10.0)
    expected = math.pi / 2.0 * sum(spiral._radii())
    assert only_path(spiral).length == pytest.approx(expected, rel=1e-3)


def test_the_fibonacci_spiral_needs_at_least_one_quarter():
    with pytest.raises(ValueError, match="quarters"):
        FibonacciSpiral(quarters=0)


def test_an_involute_unwinds_a_string_of_the_right_length():
    # The taut string from the tangent point is exactly the arc it came off,
    # so the distance to the center is radius * sqrt(1 + t**2).
    involute = CircleInvolute(radius=4.0, turns=2.0)
    for u in (0.0, 0.25, 0.5, 1.0):
        t = math.tau * 2.0 * u
        distance = math.dist((0.0, 0.0), involute.position(u))
        assert distance == pytest.approx(4.0 * math.sqrt(1.0 + t * t))


def test_an_involute_starts_on_the_circle_it_unwinds_from():
    assert first_point(CircleInvolute(radius=4.0)) == pytest.approx((4.0, 0.0))


def test_an_involute_needs_a_positive_turn_count():
    with pytest.raises(ValueError, match="turns"):
        CircleInvolute(turns=0.0)


@pytest.mark.parametrize(
    ("z", "expected"),
    [
        (0.0, (0.0, 0.0)),
        (0.5, (0.49234422, 0.06473243)),
        (1.0, (0.77989340, 0.43825915)),
        (2.0, (0.48825340, 0.34341568)),
        (3.0, (0.60572079, 0.49631300)),
    ],
)
def test_the_fresnel_integrals_match_their_published_values(z, expected):
    assert _fresnel(z) == pytest.approx(expected, abs=1e-8)


def test_the_fresnel_integrals_are_odd():
    assert _fresnel(-1.7) == pytest.approx([-v for v in _fresnel(1.7)])


def test_the_fresnel_approximations_agree_where_they_hand_over():
    # The series stops being trustworthy past this point and a rational
    # approximation takes over; the seam must not be a visible kink.
    series = _fresnel(4.0)
    rational = _fresnel(4.0 + 1e-9)
    assert rational == pytest.approx(series, abs=2e-3)


def test_the_euler_spiral_passes_through_its_center_halfway():
    assert EulerSpiral(center=(7.0, -2.0)).position(0.5) == pytest.approx((7.0, -2.0))


def test_the_euler_spiral_is_symmetric_about_its_center():
    spiral = EulerSpiral(scale=100.0, extent=2.0)
    for u in (0.0, 0.1, 0.37):
        near = spiral.position(u)
        far = spiral.position(1.0 - u)
        assert (near[0] + far[0], near[1] + far[1]) == pytest.approx((0.0, 0.0))


def test_the_euler_spiral_needs_a_positive_extent():
    with pytest.raises(ValueError, match="extent"):
        EulerSpiral(extent=0.0)


def test_archimedean_between_builds_the_endpoint_constrained_spiral():
    direct = SpiralBetween((200, 0), (20, 0), turns=2)
    via_class = ArchimedeanSpiral.between((200, 0), (20, 0), turns=2)
    assert isinstance(via_class, SpiralBetween)
    assert list(via_class.build()) == list(direct.build())
