import itertools

import pytest

from spiralgen import (
    CircularSpacing,
    CubicSpacing,
    ExponentialSpacing,
    LinearSpacing,
    PowerSpacing,
    QuadraticSpacing,
    SineSpacing,
    SmoothstepSpacing,
    SpacingCurve,
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
