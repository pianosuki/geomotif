import math

import pytest

from geomotif.motifs.graphs import (
    BipartiteGraph,
    ChordDiagram,
    CompleteGraph,
    CyclicGraph,
    ModularAddition,
    ModularMultiplication,
    PrimeChords,
    _primes_below,
)


def chords(motif):
    """Return each drawn segment as a sorted pair of rounded endpoints."""
    return {
        tuple(
            sorted(
                (
                    tuple(round(c, 9) for c in path.points[0]),
                    tuple(round(c, 9) for c in path.points[-1]),
                )
            )
        )
        for path in motif.build().paths
    }


def radii(points, center=(0.0, 0.0)):
    return [math.dist(center, point) for point in points]


# --- the sieve --------------------------------------------------------------


def test_the_sieve_finds_the_primes():
    assert _primes_below(30) == [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]
    assert _primes_below(3) == [2]
    assert len(_primes_below(1000)) == 168


# --- complete graph ---------------------------------------------------------


@pytest.mark.parametrize("order", [2, 3, 5, 8, 12])
def test_a_complete_graph_joins_every_pair_once(order):
    graph = CompleteGraph(order=order)
    assert graph.edge_count() == order * (order - 1) // 2
    assert len(graph.build().paths) == graph.edge_count()


def test_the_nodes_sit_on_the_circle_it_is_given():
    graph = CompleteGraph(order=9, radius=70.0, center=(4.0, -6.0))
    assert radii(graph.nodes(), (4.0, -6.0)) == pytest.approx([70.0] * 9)


def test_rotation_turns_the_whole_graph():
    upright = CompleteGraph(order=6, rotation=0.0).nodes()
    turned = CompleteGraph(order=6, rotation=math.pi / 2.0).nodes()
    for (x, y), (u, v) in zip(upright, turned, strict=True):
        assert (u, v) == pytest.approx((-y, x))


def test_merging_a_complete_graph_leaves_fewer_longer_strokes():
    plain = CompleteGraph(order=8).build()
    merged = CompleteGraph(order=8, merge=True).build()
    assert len(merged.paths) < len(plain.paths)
    assert math.fsum(p.length for p in merged.paths) == pytest.approx(
        math.fsum(p.length for p in plain.paths)
    )


def test_show_nodes_adds_the_nodes_as_loose_points():
    assert CompleteGraph(order=7).build().points == ()
    assert len(CompleteGraph(order=7, show_nodes=True).build().points) == 7


# --- circulant --------------------------------------------------------------


def test_one_step_is_the_plain_cycle():
    graph = CyclicGraph(order=9, steps=(1,))
    assert len(graph.build().paths) == 9


def test_each_step_contributes_its_own_ring():
    assert len(CyclicGraph(order=12, steps=(1, 5)).build().paths) == 24


def test_the_half_step_of_an_even_cycle_folds_onto_itself():
    # Node i to i+6 and node i+6 to i are the same chord, so a twelve-node
    # circulant gets six diameters rather than twelve.
    assert len(CyclicGraph(order=12, steps=(6,)).build().paths) == 6


def test_a_step_beyond_the_order_is_refused():
    with pytest.raises(ValueError, match="wrapped"):
        CyclicGraph(order=8, steps=(9,))


# --- bipartite --------------------------------------------------------------


@pytest.mark.parametrize(("left", "right"), [(1, 1), (3, 3), (4, 5), (1, 6)])
def test_a_bipartite_graph_joins_every_pair_across(left, right):
    assert len(BipartiteGraph(left=left, right=right).build().paths) == left * right


def test_the_two_ranks_stand_a_span_apart():
    nodes = BipartiteGraph(left=3, right=2, span=100.0, height=40.0).nodes()
    assert {round(x, 9) for x, _ in nodes} == {-50.0, 50.0}
    assert sorted(round(y, 9) for _, y in nodes[:3]) == [-20.0, 0.0, 20.0]


def test_a_rank_of_one_sits_on_the_axis():
    nodes = BipartiteGraph(left=1, right=1, height=200.0).nodes()
    assert [y for _, y in nodes] == [0.0, 0.0]


# --- chord diagram ----------------------------------------------------------


def test_a_chord_diagram_draws_the_chords_it_is_given():
    diagram = ChordDiagram(order=6, chords=((0, 3), (1, 4)))
    assert len(diagram.build().paths) == 2


def test_repeated_and_reversed_chords_collapse_to_one():
    diagram = ChordDiagram(order=6, chords=((0, 3), (3, 0), (0, 3)))
    assert len(diagram.build().paths) == 1


def test_a_chord_from_a_node_to_itself_is_dropped():
    diagram = ChordDiagram(order=6, chords=((0, 0), (1, 4)))
    assert len(diagram.build().paths) == 1


def test_a_chord_diagram_shows_its_nodes_by_default():
    # Alone in the module: a handful of chords does not imply where the nodes
    # are the way a dense arithmetic rule does.
    assert len(ChordDiagram(order=10, chords=((0, 5),)).build().points) == 10


def test_a_chord_out_of_range_is_refused():
    with pytest.raises(IndexError):
        ChordDiagram(order=6, chords=((0, 99),)).build()


# --- times table ------------------------------------------------------------


def test_the_times_table_joins_each_number_to_its_multiple():
    table = ModularMultiplication(modulus=12, factor=5, radius=1.0, rotation=0.0)
    nodes = table.nodes()
    assert chords(table) == {
        tuple(
            sorted(
                (
                    tuple(round(c, 9) for c in nodes[i]),
                    tuple(round(c, 9) for c in nodes[5 * i % 12]),
                )
            )
        )
        for i in range(12)
        if 5 * i % 12 != i
    }


@pytest.mark.parametrize(("factor", "cusps"), [(2, 1), (3, 2), (4, 3), (7, 6)])
def test_the_envelope_has_one_cusp_fewer_than_the_factor(factor, cusps):
    assert ModularMultiplication(factor=factor).cusp_count() == cusps


def test_the_two_times_table_envelopes_a_cardioid():
    # The chord joining the point at angle t to the point at angle 2t is
    # tangent to (2/3)e^(it) + (1/3)e^(2it) -- two rotating arms, which is a
    # cardioid. So the tangency point is known in closed form, and every chord
    # must pass exactly through its own, somewhere along its length rather
    # than out on the extension.
    modulus, radius, rotation = 360, 100.0, math.pi
    table = ModularMultiplication(modulus=modulus, factor=2, radius=radius, rotation=rotation)
    nodes = table.nodes()

    for i in range(1, modulus):
        t = math.tau * i / modulus
        touch = (
            radius * (2.0 / 3.0 * math.cos(rotation + t) + math.cos(rotation + 2.0 * t) / 3.0),
            radius * (2.0 / 3.0 * math.sin(rotation + t) + math.sin(rotation + 2.0 * t) / 3.0),
        )
        (ax, ay), (bx, by) = nodes[i], nodes[2 * i % modulus]
        dx, dy = bx - ax, by - ay
        assert (dx * (touch[1] - ay) - dy * (touch[0] - ax)) == pytest.approx(0.0, abs=1e-6)
        along = ((touch[0] - ax) * dx + (touch[1] - ay) * dy) / (dx * dx + dy * dy)
        assert 0.0 <= along <= 1.0


def test_the_cardioid_envelope_is_the_cardioid_the_catalogue_draws():
    # ...and that closed form is the same curve `Cardioid` builds: cusp a
    # third of the radius from the middle, opening to the far side, and
    # r = (2R/3)(1 + cos t) -- which `Cardioid` takes as the largest extent of
    # its box, so 3*sqrt(3)/2 times that.
    from geomotif.motifs.curves import Cardioid

    radius = 100.0
    envelope = [
        (
            radius * (2.0 / 3.0 * math.cos(t) + math.cos(2.0 * t) / 3.0),
            radius * (2.0 / 3.0 * math.sin(t) + math.sin(2.0 * t) / 3.0),
        )
        # Thirteen samples rather than twelve so none of them lands on the
        # cusp itself, where the radius is zero and the angle undefined.
        for t in (math.tau * k / 13.0 for k in range(13))
    ]
    cusp = (-radius / 3.0, 0.0)
    for x, y in envelope:
        dx, dy = x - cusp[0], y - cusp[1]
        assert math.hypot(dx, dy) == pytest.approx(
            2.0 * radius / 3.0 * (1.0 + math.cos(math.atan2(dy, dx)))
        )

    # And that is the curve `Cardioid` draws, at the size and place it takes.
    drawn = Cardioid(size=radius * math.sqrt(3.0), center=cusp).build().bounds
    assert drawn.height == pytest.approx(radius * math.sqrt(3.0), rel=1e-4)
    # Its far point is the one place the envelope touches the circle of nails.
    assert drawn.max_x == pytest.approx(radius, rel=1e-4)


def test_a_factor_that_moves_nothing_is_refused():
    with pytest.raises(ValueError, match="leaves every number"):
        ModularMultiplication(modulus=200, factor=1)
    with pytest.raises(ValueError, match="leaves every number"):
        ModularMultiplication(modulus=200, factor=201)


# --- modular addition -------------------------------------------------------


@pytest.mark.parametrize(
    ("modulus", "addend", "loops"),
    [(12, 5, 1), (12, 4, 4), (12, 6, 6), (60, 37, 1), (60, 24, 12)],
)
def test_adding_a_constant_walks_in_that_many_loops(modulus, addend, loops):
    assert ModularAddition(modulus=modulus, addend=addend).loop_count() == loops


def test_adding_a_constant_draws_one_chord_per_node():
    # Except when the step is exactly half way round, where each chord is a
    # diameter drawn from both ends.
    assert len(ModularAddition(modulus=15, addend=4).build().paths) == 15
    assert len(ModularAddition(modulus=16, addend=8).build().paths) == 8


def test_an_addend_that_goes_nowhere_is_refused():
    with pytest.raises(ValueError, match="nothing to draw"):
        ModularAddition(modulus=60, addend=60)


# --- primes -----------------------------------------------------------------


def test_every_prime_chord_joins_a_pair_that_sums_to_a_prime():
    limit = 40
    diagram = PrimeChords(limit=limit, radius=1.0, rotation=0.0)
    nodes = list(diagram.nodes())
    primes = set(_primes_below(2 * limit))
    for i, j in diagram.edges():
        assert i + j in primes
        assert nodes[i] != nodes[j]


def test_the_prime_web_is_bipartite_apart_from_one_chord():
    # Two numbers of the same parity sum to an even number, and the only even
    # prime is two -- so zero-to-two is the single chord joining like to like.
    same_parity = [(i, j) for i, j in PrimeChords(limit=50).edges() if (i + j) % 2 == 0]
    assert same_parity == [(0, 2)]


def test_the_chord_count_matches_a_direct_count():
    limit = 30
    primes = set(_primes_below(2 * limit))
    expected = sum(1 for i in range(limit) for j in range(i + 1, limit) if i + j in primes)
    assert len(PrimeChords(limit=limit).build().paths) == expected


def test_a_larger_limit_draws_more_chords():
    assert len(PrimeChords(limit=20).build().paths) < len(PrimeChords(limit=40).build().paths)


# --- shared -----------------------------------------------------------------


@pytest.mark.parametrize(
    "make",
    [
        lambda: CompleteGraph(order=1),
        lambda: CompleteGraph(radius=0.0),
        lambda: CyclicGraph(order=2),
        lambda: CyclicGraph(steps=()),
        lambda: CyclicGraph(steps=(0,)),
        lambda: BipartiteGraph(left=0),
        lambda: BipartiteGraph(right=0),
        lambda: BipartiteGraph(span=0.0),
        lambda: BipartiteGraph(height=-1.0),
        lambda: ChordDiagram(chords=()),
        lambda: ChordDiagram(order=1),
        lambda: ModularMultiplication(modulus=1),
        lambda: ModularAddition(radius=-1.0),
        lambda: PrimeChords(limit=3),
    ],
)
def test_bad_parameters_are_refused(make):
    with pytest.raises(ValueError):
        make()


def test_meta_records_the_parameters():
    design = ModularMultiplication(modulus=64, factor=3).build()
    assert design.meta["motif"] == "modular.multiplication"
    assert design.meta["modulus"] == 64
    assert design.meta["factor"] == 3
