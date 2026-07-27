"""Base for motifs that are straight lines between a set of points.

Nodes and edges, nothing more. That covers the complete graphs, chord
diagrams, modular-arithmetic circles (connect ``i`` to ``k*i mod n``, the
times-table cardioid) and every form of string art -- all of which are the
same motif with a different edge rule.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, override

from ..core.motif import Motif
from ..core.registry import spec
from ..core.types import Design, Path

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from ..core.types import Point

__all__ = ["SegmentMotif"]


@dataclass(frozen=True, slots=True)
class SegmentMotif(Motif, ABC):
    """Base for a motif built from straight segments between indexed points.

    Implement :meth:`nodes` and :meth:`edges`; :meth:`build` turns them into
    strokes. A ten-line class gets you the whole times-table family::

        @register("modular.multiplication", family="graph", example={"modulus": 200})
        @dataclass(frozen=True, slots=True)
        class ModularMultiplication(SegmentMotif):
            modulus: int = 200
            factor: int = 2

            def nodes(self) -> Sequence[Point]:
                step = math.tau / self.modulus
                return [(math.cos(i * step), math.sin(i * step)) for i in range(self.modulus)]

            def edges(self) -> Iterable[tuple[int, int]]:
                return ((i, self.factor * i % self.modulus) for i in range(self.modulus))

    Notes
    -----
    Edges are undirected: ``(i, j)`` and ``(j, i)`` are the same segment and
    the duplicate is dropped, as is any self-loop ``(i, i)``. Both are
    routine outputs of an arithmetic edge rule rather than mistakes, so
    neither is an error -- but drawing them would waste plotter time on
    nothing.
    """

    #: Chain segments that share an endpoint into longer polylines. Off by
    #: default, since one stroke per segment is the predictable result; on, it
    #: means far fewer pen lifts and a resampling budget spread along whole
    #: runs rather than restarted at every corner.
    merge: bool = field(default=False, kw_only=True)
    #: Also emit the nodes themselves as loose points.
    show_nodes: bool = field(default=False, kw_only=True)

    @abstractmethod
    def nodes(self) -> Sequence[Point]:
        """Return the points the edges are drawn between."""

    @abstractmethod
    def edges(self) -> Iterable[tuple[int, int]]:
        """Return index pairs into :meth:`nodes`, one per segment."""

    @override
    def build(self) -> Design:
        nodes = tuple(self.nodes())
        if not nodes:
            raise ValueError(f"{type(self).__name__}.nodes() returned no points")

        pairs = _unique_edges(self.edges(), node_count=len(nodes), owner=type(self).__name__)
        chains: list[tuple[int, ...]] = _chain(pairs) if self.merge else list(pairs)
        paths = tuple(Path(tuple(nodes[i] for i in chain)) for chain in chains)
        return Design(paths, nodes if self.show_nodes else (), meta=spec(self))


def _unique_edges(
    edges: Iterable[tuple[int, int]],
    *,
    node_count: int,
    owner: str,
) -> list[tuple[int, int]]:
    """Validate edges, dropping self-loops and undirected duplicates."""
    seen: set[tuple[int, int]] = set()
    unique: list[tuple[int, int]] = []
    for index, edge in enumerate(edges):
        try:
            i, j = edge
        except (TypeError, ValueError):
            raise TypeError(
                f"{owner}.edges()[{index}] must be an (i, j) index pair, got {edge!r}"
            ) from None
        if not (0 <= i < node_count and 0 <= j < node_count):
            raise IndexError(
                f"{owner}.edges()[{index}] refers to node {i if i >= node_count else j}, "
                f"but there are only {node_count} nodes"
            )
        if i == j:
            continue
        key = (i, j) if i < j else (j, i)
        if key in seen:
            continue
        seen.add(key)
        unique.append((i, j))
    return unique


def _chain(edges: Sequence[tuple[int, int]]) -> list[tuple[int, ...]]:
    """Greedily join edges that share an endpoint into runs of node indices.

    Greedy is enough here: the goal is fewer, longer strokes, not the provably
    minimal set of them. Ties are broken by edge order, so the result is
    deterministic for a given edge list.
    """
    incident: dict[int, list[int]] = {}
    for index, (i, j) in enumerate(edges):
        incident.setdefault(i, []).append(index)
        incident.setdefault(j, []).append(index)

    used = [False] * len(edges)

    def step_from(node: int) -> int | None:
        """Return the far end of an unused edge touching ``node``, marking it used."""
        for index in incident[node]:
            if used[index]:
                continue
            used[index] = True
            i, j = edges[index]
            return j if i == node else i
        return None

    chains: list[tuple[int, ...]] = []
    for index, (i, j) in enumerate(edges):
        if used[index]:
            continue
        used[index] = True
        run = [i, j]
        while (nxt := step_from(run[-1])) is not None:
            run.append(nxt)
        while (prev := step_from(run[0])) is not None:
            run.insert(0, prev)
        chains.append(tuple(run))
    return chains
