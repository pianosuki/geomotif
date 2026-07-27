import math

import pytest

from geomotif.motifs.polar import (
    GOLDEN_ANGLE,
    Harmonic,
    Harmonograph,
    Lissajous,
    MaurerRose,
    Pendulum,
    Phyllotaxis,
    PolarExpression,
    Rose,
    VogelSpiral,
)

SAMPLES = [i / 32.0 for i in range(33)]


def only_path(motif):
    design = motif.build()
    assert len(design.paths) == 1
    return design.paths[0]


def radii(design, center=(0.0, 0.0)):
    return [math.dist(center, point) for point in design]


def count_maxima(values):
    """Count strict local maxima of a cyclic sequence."""
    n = len(values)
    return sum(
        1 for i in range(n) if values[i] > values[i - 1] and values[i] >= values[(i + 1) % n]
    )


# --- rose -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("n", "d", "petals"),
    [
        (1, 1, 1),
        (2, 1, 4),
        (3, 1, 3),
        (4, 1, 8),
        (5, 1, 5),
        (6, 1, 12),
        (3, 2, 6),
        (5, 2, 10),
        (7, 3, 7),
        (4, 3, 8),
    ],
)
def test_a_rose_has_the_petals_the_parity_rule_says(n, d, petals):
    rose = Rose(n=n, d=d)
    assert rose.petal_count() == petals
    assert count_maxima(radii(rose.build())) == petals


def test_a_rose_closes_exactly_once():
    rose = Rose(n=5, d=1)
    assert rose.position(0.0) == pytest.approx(rose.position(1.0))
    assert only_path(rose).closed


def test_a_reducible_rose_is_the_rose_it_reduces_to():
    assert Rose(n=4, d=2).closure() == Rose(n=2, d=1).closure()
    for u in SAMPLES:
        assert Rose(n=4, d=2).position(u) == pytest.approx(Rose(n=2, d=1).position(u))


@pytest.mark.parametrize(
    ("n", "d", "closure"), [(5, 1, math.pi), (4, 1, math.tau), (7, 3, 3 * math.pi)]
)
def test_the_sweep_stops_where_the_curve_comes_home(n, d, closure):
    assert Rose(n=n, d=d).closure() == pytest.approx(closure)


def test_a_petal_is_as_long_as_the_size_asks():
    assert max(radii(Rose(n=5, size=70.0).build())) == pytest.approx(70.0, rel=1e-4)


def test_a_rose_grows_from_its_center():
    assert min(radii(Rose(n=5, center=(4.0, 9.0)).build(), (4.0, 9.0))) == pytest.approx(0.0)


def test_a_many_petalled_rose_is_still_measured_finely_enough():
    # Density has to follow the oscillation, not the half-revolution sweep.
    assert len(Rose(n=21).build()) > len(Rose(n=3).build())


@pytest.mark.parametrize("kwargs", [{"n": 0}, {"n": -1}, {"d": 0}])
def test_a_rose_needs_a_positive_frequency(kwargs):
    with pytest.raises(ValueError):
        Rose(**kwargs)


# --- maurer rose ------------------------------------------------------------


@pytest.mark.parametrize(
    ("degrees", "chords"), [(71, 360), (72, 5), (90, 4), (29, 360), (-71, 360)]
)
def test_the_walk_closes_after_360_over_the_common_factor(degrees, chords):
    assert MaurerRose(degrees=degrees).chord_count() == chords


def test_a_maurer_rose_is_one_closed_stroke_of_listed_corners():
    path = only_path(MaurerRose(n=6, degrees=71))
    assert path.closed
    assert len(path.points) == 360


def test_every_maurer_vertex_sits_on_the_rose_underneath_it():
    rose = MaurerRose(n=6, degrees=71, size=80.0)
    for k, point in enumerate(only_path(rose).points):
        theta = math.radians(k * 71)
        expected = abs(80.0 * math.sin(6 * theta))
        assert math.dist((0.0, 0.0), point) == pytest.approx(expected, abs=1e-9)


def test_a_maurer_rose_is_drawn_around_its_center():
    bounds = MaurerRose(center=(10.0, -20.0)).build().bounds
    assert bounds.center == pytest.approx((10.0, -20.0), abs=1e-9)


def test_changing_the_step_by_one_degree_changes_the_whole_figure():
    assert only_path(MaurerRose(degrees=71)).points != only_path(MaurerRose(degrees=72)).points


@pytest.mark.parametrize("degrees", [0, 360, -720])
def test_a_step_of_a_whole_turn_is_refused(degrees):
    with pytest.raises(ValueError):
        MaurerRose(degrees=degrees)


def test_a_maurer_rose_needs_a_positive_frequency():
    with pytest.raises(ValueError):
        MaurerRose(n=0)


# --- lissajous and harmonics ------------------------------------------------


def test_equal_frequencies_a_quarter_turn_apart_give_a_circle():
    figure = Lissajous(a=1, b=1, delta=math.pi / 2, width=100.0, height=100.0)
    assert all(radius == pytest.approx(50.0) for radius in radii(figure.build()))


def test_a_lissajous_fills_the_extents_it_is_given():
    bounds = Lissajous(a=3, b=2, width=160.0, height=90.0).build().bounds
    assert (bounds.width, bounds.height) == pytest.approx((160.0, 90.0), rel=1e-3)


def test_a_lissajous_is_centered_where_it_is_told():
    bounds = Lissajous(center=(7.0, -3.0)).build().bounds
    assert bounds.center == pytest.approx((7.0, -3.0), abs=1e-6)


@pytest.mark.parametrize("kwargs", [{"a": 0}, {"b": 0}, {"a": -2}])
def test_a_lissajous_needs_whole_positive_frequencies(kwargs):
    with pytest.raises(ValueError):
        Lissajous(**kwargs)


def test_one_term_per_axis_is_a_lissajous():
    harmonic = Harmonic(
        x_terms=((80.0, 3.0, math.pi / 2),),
        y_terms=((45.0, 2.0, 0.0),),
    )
    lissajous = Lissajous(a=3, b=2, delta=math.pi / 2, width=160.0, height=90.0)
    for u in SAMPLES:
        assert harmonic.position(u * math.tau) == pytest.approx(lissajous.position(u * math.tau))


def test_a_second_term_rides_on_top_of_the_first():
    plain = Harmonic(y_terms=((100.0, 3.0, 0.0),))
    rippled = Harmonic(y_terms=((100.0, 3.0, 0.0), (40.0, 17.0, 0.0)))
    assert rippled.build().bounds.height > plain.build().bounds.height


@pytest.mark.parametrize("terms", [{"x_terms": ()}, {"y_terms": ()}])
def test_a_harmonic_needs_a_term_on_each_axis(terms):
    with pytest.raises(ValueError):
        Harmonic(**terms)


def test_a_harmonic_refuses_a_frequency_that_would_never_close():
    with pytest.raises(ValueError, match="whole"):
        Harmonic(y_terms=((100.0, 2.5, 0.0),))


def test_a_harmonic_term_has_to_be_a_triple():
    with pytest.raises(ValueError, match=r"x_terms\[0\]"):
        Harmonic(x_terms=((100.0, 1.0),))  # type: ignore[arg-type]


# --- harmonograph -----------------------------------------------------------


def test_an_undamped_pendulum_keeps_its_amplitude():
    pendulum = Pendulum(amplitude=50.0, frequency=1.0, phase=0.0, damping=0.0)
    assert max(abs(pendulum.at(t / 10.0)) for t in range(100)) == pytest.approx(50.0, rel=1e-3)


def test_damping_runs_a_pendulum_down():
    pendulum = Pendulum(amplitude=50.0, frequency=1.0, phase=math.pi / 2, damping=0.1)
    assert abs(pendulum.at(0.0)) == pytest.approx(50.0)
    assert abs(pendulum.at(20.0)) < 10.0


def test_an_undamped_harmonograph_is_a_lissajous():
    machine = Harmonograph(
        x_pendulums=(Pendulum(80.0, 3.0, math.pi / 2, 0.0),),
        y_pendulums=(Pendulum(45.0, 2.0, 0.0, 0.0),),
        duration=math.tau,
    )
    lissajous = Lissajous(a=3, b=2, delta=math.pi / 2, width=160.0, height=90.0)
    for u in SAMPLES:
        assert machine.position(u) == pytest.approx(lissajous.position(u * math.tau))


def test_a_harmonograph_winds_down_towards_its_center():
    machine = Harmonograph(center=(5.0, -5.0))
    points = list(machine.build())
    early = max(math.dist((5.0, -5.0), p) for p in points[:200])
    late = max(math.dist((5.0, -5.0), p) for p in points[-200:])
    assert late < early


def test_a_harmonograph_does_not_pretend_to_close():
    assert not only_path(Harmonograph()).closed


@pytest.mark.parametrize(
    "kwargs",
    [{"x_pendulums": ()}, {"y_pendulums": ()}, {"duration": 0.0}, {"duration": -1.0}],
)
def test_a_harmonograph_needs_pendulums_and_time(kwargs):
    with pytest.raises(ValueError):
        Harmonograph(**kwargs)


# --- phyllotaxis ------------------------------------------------------------


def test_the_seed_head_is_loose_points_and_not_a_stroke():
    design = Phyllotaxis(count=200).build()
    assert design.paths == ()
    assert len(design.points) == 200


def test_every_seed_sits_at_the_square_root_of_its_index():
    seeds = Phyllotaxis(count=50, spacing=6.0, center=(2.0, 3.0)).build().points
    for i, seed in enumerate(seeds):
        assert math.dist((2.0, 3.0), seed) == pytest.approx(6.0 * math.sqrt(i))


def test_consecutive_seeds_are_a_golden_angle_apart():
    seeds = Phyllotaxis(count=10).build().points
    for i in range(1, len(seeds) - 1):
        first = math.atan2(seeds[i][1], seeds[i][0])
        second = math.atan2(seeds[i + 1][1], seeds[i + 1][0])
        assert (second - first) % math.tau == pytest.approx(GOLDEN_ANGLE % math.tau)


def test_the_first_seed_is_the_center():
    assert Phyllotaxis(center=(9.0, 9.0)).build().points[0] == (9.0, 9.0)


def test_vogels_spiral_is_the_same_construction():
    assert VogelSpiral is Phyllotaxis


@pytest.mark.parametrize("kwargs", [{"count": 0}, {"spacing": 0.0}, {"spacing": -1.0}])
def test_a_seed_head_needs_seeds_and_room(kwargs):
    with pytest.raises(ValueError):
        Phyllotaxis(**kwargs)


# --- polar expression -------------------------------------------------------


def test_a_constant_expression_draws_a_circle():
    motif = PolarExpression(formula=lambda theta: 40.0)
    assert all(radius == pytest.approx(40.0) for radius in radii(motif.build()))


def test_the_expression_is_the_radius():
    motif = PolarExpression(formula=lambda theta: 10.0 + theta, theta_span=math.pi)
    assert motif.radius(1.5) == pytest.approx(11.5)
    assert math.dist((0.0, 0.0), motif.position(1.0)) == pytest.approx(10.0 + math.pi)


def test_the_default_expression_is_a_seven_fold_flower():
    motif = PolarExpression()
    for u in SAMPLES:
        x, y = motif.position(u)
        turned_x, turned_y = motif.position(u + 1.0 / 7.0)
        angle = math.tau / 7.0
        assert turned_x == pytest.approx(x * math.cos(angle) - y * math.sin(angle))
        assert turned_y == pytest.approx(x * math.sin(angle) + y * math.cos(angle))


def test_an_expression_can_be_swept_partway():
    partial = PolarExpression(theta_span=math.pi)
    assert partial.sweep_turns() == pytest.approx(0.5)
