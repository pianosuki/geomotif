import math

import pytest

from geomotif.motifs import SymmetricPointSet


def points(**params):
    return SymmetricPointSet(**params).build().points


def nearest_distances(pts):
    return [min(math.dist(p, q) for q in pts if q != p) for p in pts]


def spread(pts):
    """How far from equal the nearest-neighbour distances are: 1.0 is exact."""
    nearest = nearest_distances(pts)
    return max(nearest) / min(nearest)


# --- what the group allows --------------------------------------------------


@pytest.mark.parametrize(
    ("count", "group", "sizes"),
    [
        (15, "D5", (5, 10)),  # the fifteen-point star: one mirror orbit, one general
        (15, "C5", (5, 5, 5)),
        (10, "D5", (10,)),
        (21, "C5", (1, 5, 5, 5, 5)),  # the odd one out goes to the center
        (12, "D6", (12,)),
    ],
)
def test_a_count_breaks_into_the_orbits_the_group_has(count, group, sizes):
    motif = SymmetricPointSet(count=count, group=group)
    assert motif.orbit_sizes() == sizes
    assert sum(sizes) == count


@pytest.mark.parametrize(("count", "group"), [(12, "D5"), (13, "C5"), (8, "C3")])
def test_a_count_that_cannot_be_arranged_is_refused_with_two_that_can(count, group):
    with pytest.raises(ValueError, match="cannot be arranged"):
        SymmetricPointSet(count=count, group=group)


def test_the_refusal_names_counts_that_actually_work():
    with pytest.raises(ValueError) as caught:
        SymmetricPointSet(count=12, group="D5")
    suggested = [
        int(word) for word in str(caught.value).replace("--", " ").split() if word.isdigit()
    ]
    # The message ends "try 11 or 15"; both have to be counts D5 can build.
    for count in suggested[-2:]:
        assert SymmetricPointSet(count=count, group="D5").build()


@pytest.mark.parametrize("group", ["", "X5", "D", "C0", "five"])
def test_a_group_that_is_not_a_group_is_refused(group):
    with pytest.raises(ValueError, match="group must look like"):
        SymmetricPointSet(group=group)


# --- the symmetry itself ----------------------------------------------------


@pytest.mark.parametrize(("count", "group"), [(15, "D5"), (15, "C5"), (24, "D3"), (37, "C6")])
def test_the_point_set_is_carried_onto_itself_by_the_rotation(count, group):
    # The whole promise: the set is invariant under the group, not merely
    # arranged to look like it. Rotating it by one step must reproduce it.
    pts = points(count=count, group=group)
    order = int(group[1:])
    step = math.tau / order
    turned = {
        (
            round(x * math.cos(step) - y * math.sin(step), 6),
            round(x * math.sin(step) + y * math.cos(step), 6),
        )
        for x, y in pts
    }
    assert turned == {(round(x, 6), round(y, 6)) for x, y in pts}


def test_a_dihedral_set_is_also_carried_onto_itself_by_the_mirror():
    pts = points(count=15, group="D5")
    mirrored = {(round(x, 6), round(-y, 6)) for x, y in pts}
    assert mirrored == {(round(x, 6), round(y, 6)) for x, y in pts}


def test_a_cyclic_set_is_not_mirror_symmetric():
    # If it always were, asking for D rather than C would buy nothing. A
    # relaxed cyclic set turns its rings against each other and the mirror
    # goes with them.
    pts = points(count=15, group="C5")
    mirrored = {(round(x, 6), round(-y, 6)) for x, y in pts}
    assert mirrored != {(round(x, 6), round(y, 6)) for x, y in pts}


def test_the_count_is_exactly_what_was_asked_for():
    for count, group in ((15, "D5"), (21, "C5"), (33, "D4"), (48, "C12")):
        assert len(points(count=count, group=group)) == count


def test_the_outermost_point_sits_at_the_radius():
    pts = points(count=15, group="D5", radius=80.0)
    assert max(math.hypot(x, y) for x, y in pts) == pytest.approx(80.0)


def test_the_figure_is_centered_where_it_was_told_to_be():
    pts = points(count=15, group="D5", center=(50.0, -20.0))
    xs = [x for x, _ in pts]
    ys = [y for _, y in pts]
    assert sum(xs) / len(xs) == pytest.approx(50.0)
    assert sum(ys) / len(ys) == pytest.approx(-20.0)


# --- what the relaxation is for ---------------------------------------------


def test_relaxation_evens_out_the_spacing_it_was_given():
    seeded = spread(points(count=15, group="D5", relax=0))
    relaxed = spread(points(count=15, group="D5", relax=200))
    assert relaxed < seeded
    assert relaxed == pytest.approx(1.0, abs=1e-6)


def test_fifteen_points_under_d5_come_out_exactly_equally_spaced():
    # The problem the module exists for. Fifteen is not a multiple of ten, so
    # this is only possible at all because the mirror orbit holds five.
    assert spread(points(count=15, group="D5")) == pytest.approx(1.0, abs=1e-6)


def test_relaxing_further_does_not_undo_the_answer():
    assert spread(points(count=15, group="D5", relax=2000)) == pytest.approx(1.0, abs=1e-6)


@pytest.mark.parametrize(
    ("count", "group"),
    [(13, "D4"), (17, "D4"), (29, "D4"), (16, "D5"), (41, "D5"), (8, "D2"), (48, "D6")],
)
def test_the_counts_that_used_to_fold_onto_a_mirror_line(count, group):
    # Named individually as well as swept, because each is a count with a
    # center point or a second ring -- the shapes that put a ring orbit next
    # to a mirror line and gave the relaxation somewhere degenerate to settle.
    assert spread(points(count=count, group=group)) < 2.0


def test_a_connect_rule_that_is_not_one_is_refused_at_construction():
    # Where every other parameter is refused, rather than surfacing from
    # edges() long after the motif was accepted and written to a spec.
    with pytest.raises(ValueError, match="connect must be one of"):
        SymmetricPointSet(connect="bogus")  # type: ignore[arg-type]


def test_a_center_given_as_a_list_is_taken_as_a_point():
    # The solver is memoized on its arguments, so an unhashable center used to
    # arrive as a TypeError naming neither the motif nor the parameter.
    assert SymmetricPointSet(center=[3.0, 4.0]).center == (3.0, 4.0)  # type: ignore[arg-type]
    assert len(SymmetricPointSet(center=[3.0, 4.0]).build().points) == 15  # type: ignore[arg-type]


def test_the_same_parameters_always_give_the_same_points():
    # No random numbers anywhere: symmetry comes from construction and spacing
    # from a deterministic relaxation, so this needs no seed to be reproducible.
    assert points(count=33, group="D4") == points(count=33, group="D4")


def test_no_two_points_land_on_top_of_each_other():
    for count, group in ((12, "D6"), (33, "D4"), (48, "C12"), (49, "D8")):
        pts = points(count=count, group=group)
        assert min(nearest_distances(pts)) > 0.0
        assert len(set(pts)) == count


@pytest.mark.parametrize("group", ["C2", "C3", "C4", "C5", "C6", "C8", "D2", "D3", "D4", "D5"])
def test_no_count_the_group_accepts_collapses(group):
    """Every arrangement it agrees to build is one you could actually draw.

    The relaxation only ever measures distances *between* neighbours, so a
    figure whose points have all crowded together scores as perfectly even.
    Under a dihedral group there is a way in: a ring orbit reaching a mirror
    line, where its points meet their own reflections in pairs. Five counts
    used to end up there, and the seeded angles walked straight into it.
    """
    radius = 120.0
    # Up to 42 rather than further: past it the low-order groups are all the
    # same shape with another ring on it, and the sweep costs more than it
    # finds. Every count that ever collapsed is inside this range.
    for count in range(2, 43):
        try:
            pts = points(count=count, group=group, radius=radius)
        except ValueError:
            continue  # a count this group cannot arrange at all, which is fine
        # Points spread over a disc of this radius sit roughly this far apart;
        # an eighth of that is far below anything an arrangement produces and
        # far above anything a collapse does.
        floor = 0.12 * 2.0 * radius / math.sqrt(count)
        assert min(nearest_distances(pts)) > floor, f"{group}, {count} points collapsed"


# --- joining them up --------------------------------------------------------


def test_equal_distance_joins_every_pair_the_shortest_distance_apart():
    design = SymmetricPointSet(count=15, group="D5", connect="equal-distance").build()
    pts = design.points
    shortest = min(math.dist(a, b) for i, a in enumerate(pts) for b in pts[i + 1 :])
    for path in design.paths:
        assert math.dist(path.points[0], path.points[-1]) == pytest.approx(shortest, rel=0.08)


def test_nearest_joins_each_point_to_the_number_asked_for():
    design = SymmetricPointSet(count=20, group="D5", connect="nearest", neighbors=1).build()
    # Undirected and deduplicated, so a mutual pair is one stroke, never two.
    assert 0 < len(design.paths) <= 20


def test_all_pairs_is_the_complete_graph():
    design = SymmetricPointSet(count=10, group="D5", connect="all-pairs").build()
    assert len(design.paths) == 10 * 9 // 2


def test_none_draws_the_points_and_nothing_else():
    design = SymmetricPointSet(count=15, group="D5", connect="none").build()
    assert design.paths == ()
    assert len(design.points) == 15


def test_a_design_with_neither_edges_nor_points_is_refused():
    with pytest.raises(ValueError, match="nothing in the design"):
        SymmetricPointSet(connect="none", show_nodes=False)


def test_an_unknown_connection_rule_says_what_the_rules_are():
    with pytest.raises(ValueError, match="connect must be"):
        SymmetricPointSet(connect="spiderweb").build()  # type: ignore[arg-type]


# --- input validation -------------------------------------------------------


@pytest.mark.parametrize(
    "params",
    [
        {"count": 0},
        {"radius": 0.0},
        {"radius": -1.0},
        {"relax": -1},
        {"neighbors": 0},
        {"tolerance": -0.1},
    ],
)
def test_impossible_parameters_are_refused(params):
    with pytest.raises(ValueError):
        SymmetricPointSet(**params)
