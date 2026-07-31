import math

import pytest

from geomotif import Design, Path, Style, layer, styled, to_gif
from geomotif.animate import draw_on, spin, sweep
from geomotif.io.raster import rasterize
from geomotif.motifs import KochSnowflake, Phyllotaxis, RegularPolygon, Rose
from tests.readback import gif

SQUARE = RegularPolygon(sides=4, radius=100.0).build()

#: Axis-aligned, unlike SQUARE, so that "the edge of the drawing" and "the edge
#: of the canvas" are the same pixels and a clipped border is visible as one.
BOX = Design(paths=(Path(((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)), closed=True),))

TWO_STROKES = Design(
    paths=(
        Path(((0.0, 0.0), (100.0, 0.0))),
        Path(((0.0, 50.0), (100.0, 50.0))),
    )
)


def drawn_length(design):
    return math.fsum(path.length for path in design.paths)


def _near(pixel, lit, width):
    """Is this pixel index lit, or a neighbour of one, in ``lit``?"""
    row, col = divmod(pixel, width)
    return any((row + dy) * width + (col + dx) in lit for dy in (-1, 0, 1) for dx in (-1, 0, 1))


# --- draw_on ----------------------------------------------------------------


def test_draw_on_returns_the_frames_it_was_asked_for():
    assert len(draw_on(SQUARE, 20)) == 20
    assert len(draw_on(SQUARE, 20, hold=5)) == 25


def test_the_last_frame_is_the_whole_design():
    last = draw_on(SQUARE, 12)[-1]
    assert [p.points for p in last.paths] == [p.points for p in SQUARE.paths]
    assert last.paths[0].closed is SQUARE.paths[0].closed


def test_each_frame_draws_more_than_the_one_before():
    lengths = [drawn_length(frame) for frame in draw_on(KochSnowflake(depth=3).build(), 15)]
    assert lengths == sorted(lengths)
    assert lengths[0] > 0.0  # never a blank frame at the start of a loop


def test_progress_is_measured_in_length_rather_than_vertices():
    # Two strokes of equal length: halfway through is the end of the first.
    halfway = draw_on(TWO_STROKES, 2)[0]
    assert drawn_length(halfway) == pytest.approx(100.0)


def test_a_partly_drawn_stroke_is_cut_where_the_pen_is():
    frame = draw_on(Design(paths=(Path(((0.0, 0.0), (100.0, 0.0))),)), 4)[0]
    assert frame.paths[0].points[-1] == pytest.approx((25.0, 0.0))


def test_a_partly_drawn_closed_path_is_not_claimed_to_be_closed():
    # Half a square is not a square, and drawing it as one would close a gap
    # the pen has not been round yet.
    frame = draw_on(SQUARE, 4)[0]
    assert frame.paths[0].closed is False
    assert draw_on(SQUARE, 4)[-1].paths[0].closed is True


def test_a_trail_forgets_what_the_pen_has_left_behind():
    full = draw_on(SQUARE, 8)[-1]
    comet = draw_on(SQUARE, 8, trail=50.0)[-1]
    assert drawn_length(comet) == pytest.approx(50.0)
    assert drawn_length(comet) < drawn_length(full)


def test_loose_points_arrive_in_step_with_the_strokes():
    dots = Phyllotaxis(count=40).build()
    counts = [len(frame.points) for frame in draw_on(dots, 4)]
    assert counts == [10, 20, 30, 40]


def test_styles_follow_the_geometry_they_belong_to():
    from geomotif import styles_of

    design = layer(styled(TWO_STROKES, stroke="red"), styled(SQUARE, stroke="blue"))
    frames = draw_on(design, 6)
    # The red strokes are drawn first, so the early frames are entirely red and
    # the last one has the blue square on the end of them.
    assert set(styles_of(frames[0])) == {Style(stroke="red")}
    assert styles_of(frames[-1]) == (Style(stroke="red"),) * 2 + (Style(stroke="blue"),)


@pytest.mark.parametrize("params", [{"frames": 0}, {"hold": -1}, {"trail": 0.0}])
def test_impossible_animations_are_refused(params):
    with pytest.raises(ValueError):
        draw_on(SQUARE, **params)


# --- spin -------------------------------------------------------------------


def test_spin_returns_a_frame_per_step_and_never_repeats_the_first():
    frames = spin(TWO_STROKES, 8)
    assert len(frames) == 8
    assert frames[0].paths[0].points == TWO_STROKES.paths[0].points
    assert frames[-1].paths[0].points != frames[0].paths[0].points


def test_spinning_a_full_turn_comes_back_to_where_it_started():
    frames = spin(SQUARE, 4)
    for a, b in zip(frames[0].paths[0].points, frames[-1].paths[0].points, strict=True):
        assert a != pytest.approx(b, abs=1e-9)  # a quarter turn along
    almost = spin(SQUARE, 360)[-1]
    assert drawn_length(almost) == pytest.approx(drawn_length(SQUARE))


def test_spinning_keeps_the_design_where_it_was():
    # Rotating about the origin would swing an off-centre design out of frame.
    shifted = SQUARE.transformed(__import__("geomotif").Affine.translate(500.0, 0.0))
    for frame in spin(shifted, 6):
        assert frame.bounds.center == pytest.approx(shifted.bounds.center)


def test_spin_refuses_no_frames():
    with pytest.raises(ValueError):
        spin(SQUARE, 0)


# --- sweep ------------------------------------------------------------------


def test_sweep_rebuilds_the_motif_once_per_value():
    frames = sweep(Rose(), "n", [3, 4, 5])
    assert len(frames) == 3
    assert frames[0].meta["n"] == 3
    assert frames[2].meta["n"] == 5


def test_sweeping_a_parameter_that_is_not_there_lists_the_ones_that_are():
    with pytest.raises(ValueError, match="has no parameter 'petals'"):
        sweep(Rose(), "petals", [1, 2])


def test_sweeping_something_that_is_not_a_dataclass_says_so():
    class Handmade:
        def build(self):
            return SQUARE

    with pytest.raises(TypeError, match="not a dataclass"):
        sweep(Handmade(), "n", [1])


# --- rasterizing ------------------------------------------------------------


def test_a_raster_is_one_index_per_pixel():
    raster = rasterize(SQUARE, width=40, height=30)
    assert len(raster.pixels) == 40 * 30
    assert set(raster.pixels) == {0, 1}


def test_an_empty_canvas_stays_empty_and_a_drawn_one_does_not():
    assert sum(rasterize(SQUARE, width=60, height=60).pixels) > 0
    assert rasterize(Design(points=((0.0, 0.0),)), width=60, height=60).pixels.count(1) >= 1


def test_the_far_edges_of_a_drawing_are_on_the_canvas():
    # A w-pixel row addresses 0..w-1. Scaling by the full width put the right
    # and bottom edges on index w, where they were silently dropped -- which
    # at padding=0 is half the picture.
    raster = rasterize(BOX, width=12, height=12, padding=0.0)
    rows = [raster.pixels[y * 12 : (y + 1) * 12] for y in range(12)]
    assert all(rows[0]), "top row"
    assert all(rows[-1]), "bottom row"
    assert all(row[0] for row in rows), "left column"
    assert all(row[-1] for row in rows), "right column"


def test_padding_is_the_border_it_says_it_is():
    raster = rasterize(BOX, width=12, height=12, padding=2.0)
    rows = [raster.pixels[y * 12 : (y + 1) * 12] for y in range(12)]
    assert not any(any(row) for row in rows[:2]), "nothing inside the top margin"
    assert not any(any(row) for row in rows[-2:]), "nothing inside the bottom margin"
    assert all(not any(row[:2]) and not any(row[-2:]) for row in rows), "nor the side margins"
    # And the drawing starts exactly where the margin ends, on both axes.
    assert list(rows[2]) == [0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0]


def test_a_negative_margin_is_refused_rather_than_drawn_off_canvas():
    with pytest.raises(ValueError):
        rasterize(BOX, width=20, height=20, padding=-4.0)


def test_a_styled_stroke_rasterizes_in_its_own_palette_entry():
    design = layer(styled(SQUARE, stroke="#ff0000"), styled(TWO_STROKES, stroke="#0000ff"))
    raster = rasterize(design, width=80, height=80)
    assert raster.palette[2:] == ("#ff0000", "#0000ff")
    assert {2, 3} <= set(raster.pixels)


def test_frames_share_one_canvas_so_the_drawing_does_not_swim():
    # Each frame's own bounds grow as it is drawn; rasterizing against them
    # would rescale every frame and the figure would crawl about.
    frames = draw_on(SQUARE, 6)
    decoded = gif(to_gif(frames, width=60, height=60))
    finished = decoded.frames[-1].pixels
    assert all(len(frame.pixels) == len(finished) for frame in decoded.frames)
    lit = [{i for i, p in enumerate(frame.pixels) if p} for frame in decoded.frames]
    assert len(lit[0]) < len(lit[-1]), "the drawing grows"
    # Every pixel the first frame lit is still drawn on at the end -- give or
    # take one, because a line stopped part way is a shorter Bresenham run
    # than the whole of it and may step across a diagonal one pixel sooner.
    assert all(_near(pixel, lit[-1], 60) for pixel in lit[0]), "and does not move while it does"


# --- the GIF itself ---------------------------------------------------------


def test_a_gif_round_trips_through_a_reader_that_is_not_this_writer():
    frames = draw_on(KochSnowflake(depth=2).build(), 5)
    decoded = gif(to_gif(frames, width=80, height=80, fps=10))
    assert decoded.width == decoded.height == 80
    assert len(decoded.frames) == 5
    for frame, design in zip(decoded.frames, frames, strict=True):
        assert (
            frame.pixels
            == rasterize(
                design,
                width=80,
                height=80,
                bounds=frames[-1].bounds,
                palette=decoded_palette(decoded),
            ).pixels
        )


def decoded_palette(decoded):
    """The writer's palette strings, rebuilt from the colour table it wrote."""
    return tuple(f"#{r:02x}{g:02x}{b:02x}" for r, g, b in decoded.palette)


def test_the_frame_rate_is_written_in_what_gif_can_say():
    # Hundredths of a second, so 20fps is 5 and nothing finer exists.
    assert gif(to_gif(draw_on(SQUARE, 3), fps=20)).frames[0].delay == 5
    assert gif(to_gif(draw_on(SQUARE, 3), fps=1000)).frames[0].delay == 2


def test_a_gif_loops_forever_unless_told_otherwise():
    assert gif(to_gif(draw_on(SQUARE, 3))).loop == 0
    assert gif(to_gif(draw_on(SQUARE, 3), loop=3)).loop == 2  # stored as repeats after the first


def test_playing_once_means_no_looping_block_at_all():
    # A repeat count of zero is the block's way of saying "forever", so
    # loop=1 has to be the absence of the block rather than a count in it.
    assert gif(to_gif(draw_on(SQUARE, 3), loop=1)).loop is None


def test_a_single_frame_is_a_plain_still_image():
    decoded = gif(to_gif([SQUARE], width=50, height=50))
    assert len(decoded.frames) == 1
    assert decoded.loop is None  # no looping block, because there is nothing to loop


def test_the_colours_are_the_ones_that_were_asked_for():
    decoded = gif(to_gif([SQUARE], ink="#123456", background="#fedcba"))
    assert decoded.palette[:2] == [(0xFE, 0xDC, 0xBA), (0x12, 0x34, 0x56)]


def test_a_short_hex_colour_is_understood():
    assert gif(to_gif([SQUARE], ink="#f00")).palette[1] == (0xFF, 0x00, 0x00)


def test_a_colour_that_is_not_one_is_refused():
    with pytest.raises(ValueError, match="expected a colour"):
        to_gif([SQUARE], ink="crimson")


@pytest.mark.parametrize(
    ("frames", "params"),
    [
        ([], {}),
        ([SQUARE], {"fps": 0}),
        ([SQUARE], {"loop": -1}),
        ([Design()], {}),
    ],
)
def test_an_unwritable_gif_is_refused(frames, params):
    with pytest.raises(ValueError):
        to_gif(frames, **params)


def test_a_gif_is_written_to_a_file(tmp_path):
    from geomotif import save_gif

    target = save_gif(draw_on(SQUARE, 4), tmp_path / "square.gif", width=40, height=40)
    assert target.read_bytes()[:6] == b"GIF89a"
    assert len(gif(target.read_bytes()).frames) == 4


def test_pillow_reads_what_this_writer_wrote():
    # An independent implementation, and the only real check that the LZW is
    # right rather than merely self-consistent. Not a dependency: skipped
    # wherever Pillow is not installed.
    image = pytest.importorskip("PIL.Image")
    blob = to_gif(draw_on(KochSnowflake(depth=3).build(), 6), width=100, height=100)
    opened = image.open(__import__("io").BytesIO(blob))
    assert opened.n_frames == 6
    assert opened.size == (100, 100)
    assert opened.convert("P").tobytes() == gif(blob).frames[0].pixels
