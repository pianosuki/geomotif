import itertools

import pytest

from geomotif import (
    CircularSpacing,
    CompositeSpacing,
    CubicSpacing,
    ExponentialSpacing,
    LinearSpacing,
    PowerSpacing,
    QuadraticSpacing,
    ReversedSpacing,
    SineSpacing,
    SmoothstepSpacing,
    SpacingCurve,
    TableSpacing,
    coerce_spacing,
)

ALL_CURVES = [
    LinearSpacing(),
    PowerSpacing(2.5),
    PowerSpacing(0.5),
    PowerSpacing(3.0, mode="out"),
    QuadraticSpacing("in"),
    QuadraticSpacing("out"),
    CubicSpacing("in_out"),
    SineSpacing("in"),
    SineSpacing("in_out"),
    ExponentialSpacing("out"),
    ExponentialSpacing("in", strength=4),
    CircularSpacing("in"),
    CircularSpacing("out"),
    SmoothstepSpacing(),
    ReversedSpacing(PowerSpacing(2.0)),
    ReversedSpacing(lambda t: t * t),
    CompositeSpacing(QuadraticSpacing(), SmoothstepSpacing()),
    TableSpacing([(0.5, 0.25)]),
    TableSpacing([(0.0, 0.0), (0.25, 0.6), (1.0, 1.0)]),
]


@pytest.mark.parametrize("curve", ALL_CURVES, ids=repr)
def test_endpoints_fixed(curve):
    assert curve(0.0) == pytest.approx(0.0, abs=1e-12)
    assert curve(1.0) == pytest.approx(1.0, abs=1e-9)


@pytest.mark.parametrize("curve", ALL_CURVES, ids=repr)
def test_monotonic_and_bounded(curve):
    values = [curve(i / 200) for i in range(201)]
    assert all(0.0 <= v <= 1.0 + 1e-9 for v in values)
    assert all(b >= a - 1e-12 for a, b in itertools.pairwise(values))


@pytest.mark.parametrize("curve", ALL_CURVES, ids=repr)
def test_rejects_out_of_range_t(curve):
    with pytest.raises(ValueError):
        curve(-0.01)
    with pytest.raises(ValueError):
        curve(1.01)


def test_linear_is_identity():
    curve = LinearSpacing()
    assert curve(0.37) == 0.37


def test_power_one_matches_linear():
    curve = PowerSpacing(1.0)
    for i in range(11):
        assert curve(i / 10) == pytest.approx(i / 10)


def test_invalid_mode_rejected():
    with pytest.raises(ValueError):
        SineSpacing(mode="sideways")  # type: ignore[arg-type]


def test_invalid_params_rejected():
    with pytest.raises(ValueError):
        PowerSpacing(0)
    with pytest.raises(ValueError):
        ExponentialSpacing(strength=-1)


def test_base_class_is_abstract():
    with pytest.raises(TypeError):
        SpacingCurve()  # type: ignore[abstract]


def test_reversed_matches_modal_out():
    # ReversedSpacing generalizes what mode="out" does for modal curves, so
    # on a modal curve the two must agree exactly.
    reversed_in = ReversedSpacing(PowerSpacing(2.5, mode="in"))
    modal_out = PowerSpacing(2.5, mode="out")
    for i in range(21):
        t = i / 20
        assert reversed_in(t) == pytest.approx(modal_out(t))


def test_reversed_twice_is_identity():
    curve = ReversedSpacing(ReversedSpacing(CubicSpacing()))
    for i in range(11):
        t = i / 10
        assert curve(t) == pytest.approx(CubicSpacing()(t))


def test_composite_applies_left_to_right():
    a, b = QuadraticSpacing(), CubicSpacing()
    composite = CompositeSpacing(a, b)
    assert composite(0.7) == pytest.approx(b(a(0.7)))


def test_composite_of_one_is_that_curve():
    assert CompositeSpacing(SmoothstepSpacing())(0.3) == pytest.approx(SmoothstepSpacing()(0.3))


def test_composite_needs_a_curve():
    with pytest.raises(ValueError):
        CompositeSpacing()


def test_table_interpolates_linearly_between_control_points():
    curve = TableSpacing([(0.5, 0.25)])
    assert curve(0.5) == pytest.approx(0.25)
    assert curve(0.25) == pytest.approx(0.125)  # halfway to the control point
    assert curve(0.75) == pytest.approx(0.625)  # halfway from it to (1, 1)


def test_table_supplies_missing_endpoints():
    curve = TableSpacing([(0.5, 0.5)])
    assert curve(0.0) == pytest.approx(0.0)
    assert curve(1.0) == pytest.approx(1.0)


def test_table_allows_vertical_step():
    # A repeated t carrying two values is an instantaneous jump, not an error.
    # The curve is continuous from the left, so the jump happens just after t.
    curve = TableSpacing([(0.5, 0.2), (0.5, 0.8)])
    assert curve(0.5) == pytest.approx(0.2)
    assert curve(0.75) == pytest.approx(0.9)  # already on the far side


def test_table_rejects_decreasing_points():
    with pytest.raises(ValueError):
        TableSpacing([(0.3, 0.9), (0.7, 0.2)])


def test_table_rejects_out_of_range_points():
    with pytest.raises(ValueError):
        TableSpacing([(0.5, 1.5)])


def test_coerce_none_is_linear():
    assert isinstance(coerce_spacing(None), LinearSpacing)


def test_coerce_passes_curves_through():
    curve = CubicSpacing()
    assert coerce_spacing(curve) is curve


def test_coerce_wraps_callables():
    curve = coerce_spacing(lambda t: t * t)
    assert isinstance(curve, SpacingCurve)
    assert curve(0.5) == pytest.approx(0.25)


def test_coerce_rejects_non_callables():
    with pytest.raises(TypeError):
        coerce_spacing("linear")  # type: ignore[arg-type]
