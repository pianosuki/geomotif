import itertools
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import pytest

from geomotif import Point, SegmentMotif


@dataclass(frozen=True, slots=True)
class CompleteGraph(SegmentMotif):
    n: int = 4

    def nodes(self) -> Sequence[Point]:
        step = math.tau / self.n
        return [(math.cos(i * step), math.sin(i * step)) for i in range(self.n)]

    def edges(self) -> Iterable[tuple[int, int]]:
        return itertools.combinations(range(self.n), 2)


@dataclass(frozen=True, slots=True)
class Zigzag(SegmentMotif):
    """Consecutive edges, so merging has something to chain."""

    n: int = 5

    def nodes(self) -> Sequence[Point]:
        return [(float(i), float(i % 2)) for i in range(self.n)]

    def edges(self) -> Iterable[tuple[int, int]]:
        return ((i, i + 1) for i in range(self.n - 1))


def test_one_path_per_edge():
    design = CompleteGraph().build()
    assert len(design.paths) == 6
    assert all(len(path.points) == 2 for path in design.paths)


def test_nodes_are_not_emitted_by_default():
    assert CompleteGraph().build().points == ()


def test_show_nodes_emits_them_as_loose_points():
    assert len(CompleteGraph(show_nodes=True).build().points) == 4


def test_self_loops_are_dropped():
    @dataclass(frozen=True, slots=True)
    class Looped(Zigzag):
        def edges(self) -> Iterable[tuple[int, int]]:
            return ((0, 0), (0, 1))

    assert len(Looped().build().paths) == 1


def test_undirected_duplicates_are_dropped():
    @dataclass(frozen=True, slots=True)
    class Doubled(Zigzag):
        def edges(self) -> Iterable[tuple[int, int]]:
            return ((0, 1), (1, 0), (0, 1))

    assert len(Doubled().build().paths) == 1


def test_out_of_range_edges_are_rejected():
    @dataclass(frozen=True, slots=True)
    class Wrong(Zigzag):
        def edges(self) -> Iterable[tuple[int, int]]:
            return ((0, 99),)

    with pytest.raises(IndexError, match="only 5 nodes"):
        Wrong().build()


def test_malformed_edges_are_rejected():
    @dataclass(frozen=True, slots=True)
    class Wrong(Zigzag):
        def edges(self) -> Iterable[tuple[int, int]]:
            return ((0, 1, 2),)  # type: ignore[return-value]

    with pytest.raises(TypeError, match="index pair"):
        Wrong().build()


def test_a_motif_without_nodes_is_an_error():
    @dataclass(frozen=True, slots=True)
    class Empty(SegmentMotif):
        def nodes(self) -> Sequence[Point]:
            return ()

        def edges(self) -> Iterable[tuple[int, int]]:
            return ()

    with pytest.raises(ValueError, match="no points"):
        Empty().build()


def test_merge_chains_shared_endpoints_into_one_stroke():
    assert len(Zigzag().build().paths) == 4
    merged = Zigzag(merge=True).build()
    assert len(merged.paths) == 1
    assert len(merged.paths[0].points) == 5


def test_merge_extends_a_chain_in_both_directions():
    # The run starts from the middle edge, so it has to grow backwards as
    # well as forwards to pick up the whole zigzag.
    @dataclass(frozen=True, slots=True)
    class Shuffled(Zigzag):
        def edges(self) -> Iterable[tuple[int, int]]:
            return ((2, 3), (1, 2), (0, 1), (3, 4))

    merged = Shuffled(merge=True).build()
    assert len(merged.paths) == 1
    assert merged.paths[0].points[0] == (0.0, 0.0)


def test_merge_leaves_disjoint_segments_alone():
    @dataclass(frozen=True, slots=True)
    class Disjoint(Zigzag):
        def edges(self) -> Iterable[tuple[int, int]]:
            return ((0, 1), (2, 3))

    assert len(Disjoint(merge=True).build().paths) == 2


def test_merge_preserves_total_length():
    plain = sum(path.length for path in Zigzag().build().paths)
    merged = sum(path.length for path in Zigzag(merge=True).build().paths)
    assert merged == pytest.approx(plain)


def test_merge_is_deterministic():
    first = Zigzag(merge=True).build()
    second = Zigzag(merge=True).build()
    assert [p.points for p in first.paths] == [p.points for p in second.paths]


def test_merge_terminates_on_a_closed_ring():
    @dataclass(frozen=True, slots=True)
    class Ring(Zigzag):
        def edges(self) -> Iterable[tuple[int, int]]:
            return tuple((i, (i + 1) % self.n) for i in range(self.n))

    merged = Ring(merge=True).build()
    assert len(merged.paths) == 1
    assert merged.paths[0].points[0] == merged.paths[0].points[-1]


def test_generate_spreads_points_over_the_segments():
    design = CompleteGraph().generate(120)
    assert len(design) == 120


def test_meta_records_the_parameters():
    meta = CompleteGraph(n=5, merge=True).build().meta
    assert meta["motif"] == "CompleteGraph"
    assert meta["n"] == 5
    assert meta["merge"] is True
