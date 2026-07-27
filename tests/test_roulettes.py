import math

import pytest

from geomotif.motifs.curves import Astroid, Deltoid
from geomotif.motifs.roulettes import (
    Epicycles,
    Epicycloid,
    Epitrochoid,
    Hypocycloid,
    Hypotrochoid,
    Spirograph,
    _closing_turns,
)

SAMPLES = [i / 32.0 for i in range(33)]


def only_path(motif):
    design = motif.build()
    assert len(design.paths) == 1
    return design.paths[0]


def same_curve(one, other, *, tol=1e-9):
    """Check two motifs agree at the same parameter, sample count aside."""
    for u in SAMPLES:
        assert one.position(u) == pytest.approx(other.position(u), abs=tol)
    return True


def same_shape_over_one_turn(roulette, curve, *, tol=1e-9):
    """Compare a roulette against a curve whose parameter is the angle itself."""
    for u in SAMPLES:
        assert roulette.position(u) == pytest.approx(curve.position(u * math.tau), abs=tol)
    return True


def radii(design, center=(0.0, 0.0)):
    return [math.dist(center, point) for point in design]


def count_maxima(values):
    """Count strict local maxima of a cyclic sequence."""
    n = len(values)
    return sum(
        1 for i in range(n) if values[i] > values[i - 1] and values[i] >= values[(i + 1) % n]
    )


def count_minima(values):
    return count_maxima([-value for value in values])


# --- closure ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("outer", "inner", "turns"),
    [(100, 30, 3), (100, 25, 1), (96, 36, 3), (7, 3, 3), (12, 8, 2), (9, 9, 1)],
)
def test_the_wheel_comes_home_after_the_denominator_of_the_ratio(outer, inner, turns):
    assert _closing_turns(outer, inner) == turns


@pytest.mark.parametrize(
    "motif",
    [
        Hypotrochoid(outer=100, inner=30, offset=45.0),
        Hypocycloid(outer=100, inner=30),
        Epitrochoid(outer=100, inner=30, offset=45.0),
        Epicycloid(outer=100, inner=30),
        Spirograph(),
    ],
    ids=lambda m: type(m).__name__,
)
def test_a_roulette_returns_to_where_it_started(motif):
    assert motif.position(0.0) == pytest.approx(motif.position(1.0))
    assert only_path(motif).closed


# --- the trochoids and their cusped special cases ---------------------------


def test_a_hypotrochoid_with_the_pen_on_the_rim_is_a_hypocycloid():
    assert same_curve(
        Hypotrochoid(outer=100, inner=30, offset=30.0),
        Hypocycloid(outer=100, inner=30),
    )


def test_an_epitrochoid_with_the_pen_on_the_rim_is_an_epicycloid():
    assert same_curve(
        Epitrochoid(outer=100, inner=30, offset=30.0),
        Epicycloid(outer=100, inner=30),
    )


def test_a_hypotrochoid_with_the_pen_at_the_hub_is_a_circle():
    design = Hypotrochoid(outer=100, inner=30, offset=0.0).build()
    assert all(radius == pytest.approx(70.0) for radius in radii(design))


def test_a_four_to_one_hypocycloid_is_exactly_an_astroid():
    # x = 3r cos(t) + r cos(3t) collapses to 4r cos(t)**3 -- the same curve,
    # arrived at from the other direction.
    assert same_shape_over_one_turn(Hypocycloid(outer=100, inner=25), Astroid(size=200.0))


def test_a_three_to_one_hypocycloid_is_exactly_a_deltoid():
    assert same_shape_over_one_turn(
        Hypocycloid(outer=90, inner=30),
        Deltoid(size=30.0 * 3.0 * math.sqrt(3.0)),
    )


def test_a_hypocycloids_cusps_touch_the_ring_it_rolls_inside():
    design = Hypocycloid(outer=100, inner=30).build()
    assert count_maxima(radii(design)) == 10  # 100/30 reduces to 10/3
    assert max(radii(design)) == pytest.approx(100.0, rel=1e-4)


def test_an_epicycloids_cusps_touch_the_ring_it_rolls_around():
    design = Epicycloid(outer=100, inner=30).build()
    assert count_minima(radii(design)) == 10
    assert min(radii(design)) == pytest.approx(100.0, rel=1e-4)
    assert max(radii(design)) == pytest.approx(160.0, rel=1e-4)


@pytest.mark.parametrize("cls", [Hypotrochoid, Hypocycloid, Epitrochoid, Epicycloid])
def test_a_roulette_is_centered_where_it_is_told(cls):
    moved = cls(center=(20.0, -35.0)).build().bounds
    origin = cls().build().bounds
    assert moved.center == pytest.approx((origin.center[0] + 20.0, origin.center[1] - 35.0))


@pytest.mark.parametrize("cls", [Hypotrochoid, Hypocycloid])
@pytest.mark.parametrize("kwargs", [{"inner": 0}, {"inner": 100}, {"inner": 140}])
def test_a_wheel_rolling_inside_has_to_fit(cls, kwargs):
    with pytest.raises(ValueError):
        cls(outer=100, **kwargs)


@pytest.mark.parametrize("cls", [Epitrochoid, Epicycloid])
def test_a_wheel_rolling_outside_still_has_to_exist(cls):
    with pytest.raises(ValueError):
        cls(outer=100, inner=0)


def test_a_ring_has_to_exist_too():
    with pytest.raises(ValueError):
        Epicycloid(outer=0, inner=10)


# --- spirograph -------------------------------------------------------------


def test_the_spirograph_scales_its_wheel_from_the_tooth_counts():
    assert Spirograph(ring_teeth=96, wheel_teeth=36, ring_radius=160.0).wheel_radius() == 60.0


def test_a_spirograph_with_the_pen_on_the_rim_is_a_hypocycloid():
    assert same_curve(
        Spirograph(ring_teeth=100, wheel_teeth=25, hole=1.0, ring_radius=100.0),
        Hypocycloid(outer=100, inner=25),
    )


def test_a_spirograph_with_the_pen_at_the_hub_draws_a_circle():
    design = Spirograph(ring_teeth=100, wheel_teeth=25, hole=0.0, ring_radius=100.0).build()
    assert all(radius == pytest.approx(75.0) for radius in radii(design))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"ring_teeth": 2},
        {"wheel_teeth": 0},
        {"wheel_teeth": 96},
        {"wheel_teeth": 120},
        {"hole": -0.1},
        {"hole": 1.5},
        {"ring_radius": 0.0},
    ],
)
def test_the_spirograph_refuses_a_set_of_parts_that_does_not_fit(kwargs):
    with pytest.raises(ValueError):
        Spirograph(**kwargs)


# --- epicycles --------------------------------------------------------------


def test_one_arm_draws_a_circle():
    design = Epicycles(arms=((50.0, 1.0, 0.0),), center=(3.0, 4.0)).build()
    assert all(radius == pytest.approx(50.0) for radius in radii(design, (3.0, 4.0)))


def test_two_arms_reproduce_an_epitrochoid():
    # (R+r) at frequency 1, then the pen arm at (R+r)/r turned half a turn
    # around, which is what the minus sign in the epitrochoid formula means.
    assert same_curve(
        Epicycles(arms=((125.0, 1.0, 0.0), (45.0, 5.0, math.pi))),
        Epitrochoid(outer=100, inner=25, offset=45.0),
        tol=1e-9,
    )


def test_whole_frequencies_close_the_stroke_and_fractional_ones_do_not():
    assert only_path(Epicycles(arms=((100.0, 1.0, 0.0), (30.0, 4.0, 0.0)))).closed
    assert not only_path(Epicycles(arms=((100.0, 1.0, 0.0), (30.0, 4.5, 0.0)))).closed


def test_a_fractional_sweep_leaves_the_stroke_open_too():
    assert not only_path(Epicycles(arms=((100.0, 1.0, 0.0),), turns=0.75)).closed


def test_a_negative_frequency_turns_the_other_way():
    forward = Epicycles(arms=((100.0, 1.0, 0.0), (30.0, 5.0, 0.0)))
    backward = Epicycles(arms=((100.0, 1.0, 0.0), (30.0, -5.0, 0.0)))
    assert forward.position(0.07) != pytest.approx(backward.position(0.07))
    # Reversing the fast arm mirrors its contribution across the x-axis.
    x_forward, y_forward = forward.position(0.07)
    x_back, y_back = backward.position(0.07)
    t = 0.07 * math.tau
    inner_x, inner_y = 100.0 * math.cos(t), 100.0 * math.sin(t)
    assert (x_forward - inner_x) == pytest.approx(x_back - inner_x)
    assert (y_forward - inner_y) == pytest.approx(-(y_back - inner_y))


def test_the_sample_density_follows_the_fastest_arm():
    slow = Epicycles(arms=((100.0, 1.0, 0.0),))
    fast = Epicycles(arms=((100.0, 1.0, 0.0), (5.0, 40.0, 0.0)))
    assert fast.sweep_turns() > slow.sweep_turns()
    assert len(fast.build()) > len(slow.build())


def test_epicycles_needs_at_least_one_arm():
    with pytest.raises(ValueError):
        Epicycles(arms=())


def test_an_arm_has_to_be_a_triple():
    with pytest.raises(ValueError, match=r"arms\[1\]"):
        Epicycles(arms=((100.0, 1.0, 0.0), (30.0, 4.0)))  # type: ignore[arg-type]


def test_a_zero_sweep_is_refused():
    with pytest.raises(ValueError):
        Epicycles(turns=0.0)
