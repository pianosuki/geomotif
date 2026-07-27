import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import ClassVar

import pytest

from geomotif import Point, PolygonMotif


@dataclass(frozen=True, slots=True)
class Triangle(PolygonMotif):
    """Three corners, listed."""

    size: float = 1.0

    def outlines(self) -> Iterable[Sequence[Point]]:
        yield ((0.0, 0.0), (self.size, 0.0), (0.0, self.size))


@dataclass(frozen=True, slots=True)
class TwoTriangles(PolygonMotif):
    def outlines(self) -> Iterable[Sequence[Point]]:
        yield ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0))
        yield ((2.0, 0.0), (3.0, 0.0), (2.0, 1.0))


@dataclass(frozen=True, slots=True)
class OpenChain(PolygonMotif):
    closed: ClassVar[bool] = False

    def outlines(self) -> Iterable[Sequence[Point]]:
        yield ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0))


def test_corners_are_kept_exactly():
    design = Triangle(3.0).build()
    assert design.paths[0].points == ((0.0, 0.0), (3.0, 0.0), (0.0, 3.0))


def test_the_outline_is_closed_by_default():
    path = Triangle().build().paths[0]
    assert path.closed
    assert path.length == pytest.approx(2.0 + math.sqrt(2.0))


def test_a_class_variable_makes_the_outline_open():
    path = OpenChain().build().paths[0]
    assert not path.closed
    assert path.length == pytest.approx(2.0)


def test_each_outline_becomes_its_own_stroke():
    design = TwoTriangles().build()
    assert len(design.paths) == 2
    assert len(design) == 6


def test_the_design_records_its_parameters():
    assert Triangle(3.0).build().meta["size"] == 3.0


def test_no_outlines_is_an_error():
    @dataclass(frozen=True, slots=True)
    class Nothing(PolygonMotif):
        def outlines(self) -> Iterable[Sequence[Point]]:
            return ()

    with pytest.raises(ValueError, match="no outlines"):
        Nothing().build()


def test_an_outline_needs_at_least_two_corners():
    @dataclass(frozen=True, slots=True)
    class Lonely(PolygonMotif):
        def outlines(self) -> Iterable[Sequence[Point]]:
            yield ((0.0, 0.0),)

    with pytest.raises(ValueError, match="at least 2"):
        Lonely().build()


def test_the_failing_outline_is_named():
    @dataclass(frozen=True, slots=True)
    class SecondIsBad(PolygonMotif):
        def outlines(self) -> Iterable[Sequence[Point]]:
            yield ((0.0, 0.0), (1.0, 0.0))
            yield ((5.0, 5.0),)

    with pytest.raises(ValueError, match=r"outlines\(\)\[1\]"):
        SecondIsBad().build()


def test_the_base_is_abstract():
    with pytest.raises(TypeError):
        PolygonMotif()  # type: ignore[abstract]


def test_a_polygon_carries_no_instance_dict():
    assert not hasattr(Triangle(), "__dict__")
