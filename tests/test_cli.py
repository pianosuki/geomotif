import json
import re

import pytest

from geomotif import load_design
from geomotif.cli import RESERVED, main
from geomotif.core import registry
from tests.readback import dxf_polylines, gif, svg_root, svg_strokes


def run(capsys, *argv):
    """Run the CLI and return (exit code, stdout, stderr)."""
    code = main(list(argv))
    out, err = capsys.readouterr()
    return code, out, err


# --- list and show ---------------------------------------------------------


def test_list_groups_the_catalogue_by_family(capsys):
    code, out, _ = run(capsys, "list")
    assert code == 0
    assert "spiral" in out
    assert f"{len(registry.names())} motifs" in out


def test_list_can_be_narrowed_to_one_family(capsys):
    _, out, _ = run(capsys, "list", "--family", "sacred")
    assert "sacred.vesica" in out
    assert "spiral.golden" not in out
    assert "1 family" in out  # not "1 families"


def test_list_can_print_bare_names_for_a_pipe(capsys):
    _, out, _ = run(capsys, "list", "--names", "--family", "sacred")
    assert out.splitlines() == list(registry.names(family="sacred"))


def test_an_empty_family_says_which_ones_exist(capsys):
    code, _, err = run(capsys, "list", "--family", "nope")
    assert code == 2
    assert "sacred" in err


def test_show_prints_the_prose_and_the_parameters(capsys):
    _, out, _ = run(capsys, "show", "rose")
    assert "rhodonea" in out
    assert "--n" in out
    assert "default: 5" in out


def test_show_leaves_out_the_docstring_section_it_is_already_replacing(capsys):
    # A numpydoc Parameters section says the same thing with no flag names and
    # no defaults; printing both would be twice the text and half the use.
    _, out, _ = run(capsys, "show", "rose")
    assert "Numerator of the angular frequency" not in out


def test_show_names_the_parameters_a_command_line_cannot_say(capsys):
    _, out, _ = run(capsys, "show", "kaleidoscope")
    assert "not settable" in out
    assert "unit" in out.split("not settable")[1]


def test_show_reports_a_missing_extra_rather_than_failing(capsys):
    info = registry.describe("voronoi.cells")
    code, out, _ = run(capsys, "show", "voronoi.cells")
    assert code == 0
    assert ("unavailable" in out) is not info.available


def test_an_unknown_motif_suggests_a_near_miss(capsys):
    code, _, err = run(capsys, "show", "spiral.golde")
    assert code == 2
    assert "spiral.golden" in err


# --- render ----------------------------------------------------------------


def test_render_writes_svg(capsys, tmp_path):
    out = tmp_path / "rose.svg"
    assert run(capsys, "render", "rose", "--out", str(out))[0] == 0
    assert svg_root(out.read_text()).get("viewBox")


def test_render_writes_dxf(capsys, tmp_path):
    out = tmp_path / "rose.dxf"
    run(capsys, "render", "rose", "--out", str(out))
    assert dxf_polylines(out.read_text())


def test_render_writes_an_animated_gif(capsys, tmp_path):
    out = tmp_path / "rose.gif"
    run(capsys, "render", "rose", "--out", str(out), "--frames", "6", "--fit", "60x60")
    decoded = gif(out.read_bytes())
    # Six drawn frames plus the hold that keeps a loop from restarting the
    # instant the drawing finishes.
    assert len(decoded.frames) > 6
    assert (decoded.width, decoded.height) == (60, 60)


def test_a_spinning_gif_holds_nothing_and_repeats_exactly(capsys, tmp_path):
    out = tmp_path / "rose.gif"
    run(capsys, "render", "rose", "--out", str(out), "--motion", "spin", "--frames", "8")
    assert len(gif(out.read_bytes()).frames) == 8


def test_the_frame_rate_reaches_the_file(capsys, tmp_path):
    out = tmp_path / "rose.gif"
    run(capsys, "render", "rose", "--out", str(out), "--frames", "4", "--fps", "10")
    assert gif(out.read_bytes()).frames[0].delay == 10


def test_canvas_sets_the_pixel_size_independently_of_geometry(capsys, tmp_path):
    out = tmp_path / "rose.gif"
    run(capsys, "render", "rose", "--out", str(out), "--canvas", "120x80", "--frames", "4")
    decoded = gif(out.read_bytes())
    assert (decoded.width, decoded.height) == (120, 80)


def test_canvas_wins_over_fit_for_the_pixel_canvas(capsys, tmp_path):
    # --fit resizes the drawing's geometry; --canvas sizes the pixels. When
    # both are given the pixels come from --canvas and the geometry is still
    # fitted onto the world canvas it was asked for.
    out = tmp_path / "rose.gif"
    run(capsys, "render", "rose", "--out", str(out), "--fit", "60x60", "--canvas", "90x40", "--frames", "4")
    assert (gif(out.read_bytes()).width, gif(out.read_bytes()).height) == (90, 40)


def test_canvas_alone_and_fit_alone_degrade_to_each_other(capsys, tmp_path):
    sized, fitted = tmp_path / "a.gif", tmp_path / "b.gif"
    run(capsys, "render", "rose", "--out", str(sized), "--canvas", "70x70", "--frames", "4")
    run(capsys, "render", "rose", "--out", str(fitted), "--fit", "70x70", "--frames", "4")
    assert gif(sized.read_bytes()).width == gif(fitted.read_bytes()).width == 70


def test_stroke_width_reaches_the_gif(capsys, tmp_path):
    thin, thick = tmp_path / "t.gif", tmp_path / "k.gif"
    run(capsys, "render", "rose", "--out", str(thin), "--canvas", "60x60", "--frames", "4")
    run(
        capsys,
        "render",
        "rose",
        "--out",
        str(thick),
        "--canvas",
        "60x60",
        "--frames",
        "4",
        "--stroke-width",
        "4",
    )
    assert gif(thick.read_bytes()).frames[-1].pixels.count(1) > gif(thin.read_bytes()).frames[-1].pixels.count(1)


def test_loop_reaches_the_gif(capsys, tmp_path):
    out = tmp_path / "rose.gif"
    run(capsys, "render", "rose", "--out", str(out), "--frames", "4", "--loop", "3")
    assert gif(out.read_bytes()).loop == 2  # stored as repeats after the first


def test_a_motifs_size_flag_is_not_stolen_by_the_canvas_flag(capsys, tmp_path):
    # `size` is a real parameter on most of the catalogue, and reserving it for
    # the pixel canvas would silently change `render rose --size 800`. It stays
    # a motif flag; the pixel knob goes by `--canvas` instead.
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    run(capsys, "render", "rose", "--out", str(a), "--size", "100")
    run(capsys, "render", "rose", "--out", str(b), "--size", "400")
    ta, tb = load_design(a).bounds, load_design(b).bounds
    assert tb.width > ta.width  # a bigger rose, not a bigger canvas


def test_antialias_reaches_and_enriches_the_gif(capsys, tmp_path):
    sharp, soft = tmp_path / "s.gif", tmp_path / "o.gif"
    run(capsys, "render", "rose", "--out", str(sharp), "--canvas", "60x60", "--frames", "4")
    run(
        capsys,
        "render",
        "rose",
        "--out",
        str(soft),
        "--canvas",
        "60x60",
        "--frames",
        "4",
        "--antialias",
    )
    assert len(gif(soft.read_bytes()).palette) > len(gif(sharp.read_bytes()).palette)


def test_no_dither_is_accepted(capsys, tmp_path):
    out = tmp_path / "rose.gif"
    assert (
        run(
            capsys,
            "render",
            "rose",
            "--out",
            str(out),
            "--canvas",
            "40x40",
            "--frames",
            "3",
            "--antialias",
            "--no-dither",
        )[0]
        == 0
    )


def test_aa_level_zero_is_refused():
    with pytest.raises(SystemExit):
        main(["render", "rose", "--aa-level", "0", "--out", "x.gif"])


def test_hold_zero_means_no_repeated_frames(capsys, tmp_path):
    out = tmp_path / "rose.gif"
    run(capsys, "render", "rose", "--out", str(out), "--frames", "6", "--hold", "0")
    assert len(gif(out.read_bytes()).frames) == 6


def test_hold_n_holds_exactly_that_many_frames(capsys, tmp_path):
    out = tmp_path / "rose.gif"
    run(capsys, "render", "rose", "--out", str(out), "--frames", "6", "--hold", "4")
    decoded = gif(out.read_bytes()).frames
    # Six drawn frames, then four copies of the finished one to sit on.
    assert len(decoded) == 10
    assert decoded[-4:] == [decoded[5]] * 4


def test_omitting_hold_keeps_the_default_quarter(capsys, tmp_path):
    out = tmp_path / "rose.gif"
    run(capsys, "render", "rose", "--out", str(out), "--frames", "8")
    assert len(gif(out.read_bytes()).frames) == 8 + max(1, 8 // 4)


def test_spin_respects_hold(capsys, tmp_path):
    out = tmp_path / "rose.gif"
    run(
        capsys,
        "render",
        "rose",
        "--out",
        str(out),
        "--motion",
        "spin",
        "--frames",
        "6",
        "--hold",
        "3",
    )
    assert len(gif(out.read_bytes()).frames) == 9


def test_spin_with_hold_zero_repeats_exactly(capsys, tmp_path):
    out = tmp_path / "rose.gif"
    run(
        capsys,
        "render",
        "rose",
        "--out",
        str(out),
        "--motion",
        "spin",
        "--frames",
        "6",
        "--hold",
        "0",
    )
    assert len(gif(out.read_bytes()).frames) == 6


def test_a_negative_hold_is_refused():
    with pytest.raises(SystemExit):
        main(["render", "rose", "--hold", "-1", "--out", "x.gif"])


def test_hold_collides_with_no_motif_parameter(capsys, tmp_path):
    # The reserved name is what lets --hold reach the GIF rather than a
    # parameter that happens to be called the same thing.
    out = tmp_path / "rose.gif"
    assert run(capsys, "render", "rose", "--out", str(out), "--frames", "6", "--hold", "2")[0] == 0
    assert len(gif(out.read_bytes()).frames) == 8


def test_paper_writes_an_svg_in_real_millimetres(capsys, tmp_path):
    out = tmp_path / "rose.svg"
    run(capsys, "render", "rose", "--out", str(out), "--paper", "a5")
    assert svg_root(out.read_text()).get("width") == "148mm"


def test_paper_can_be_turned_on_its_side(capsys, tmp_path):
    out = tmp_path / "rose.svg"
    run(capsys, "render", "rose", "--out", str(out), "--paper", "a5", "--landscape")
    assert svg_root(out.read_text()).get("width") == "210mm"


def test_optimize_joins_the_strokes_up(capsys, tmp_path):
    plain, tidied = tmp_path / "a.svg", tmp_path / "b.svg"
    run(capsys, "render", "tiling.truchet", "--out", str(plain))
    run(capsys, "render", "tiling.truchet", "--out", str(tidied), "--optimize")
    assert len(svg_strokes(tidied.read_text())) < len(svg_strokes(plain.read_text()))


def test_render_writes_a_design_file(capsys, tmp_path):
    out = tmp_path / "rose.json"
    run(capsys, "render", "rose", "--out", str(out))
    assert load_design(out).meta["motif"] == "rose"


def test_render_prints_csv_when_nothing_is_named(capsys):
    # So the command composes with a pipe, like any other unix tool.
    _, out, _ = run(capsys, "render", "polygon.regular", "--sides", "3")
    assert out.splitlines()[0] == "x,y"
    assert len(out.splitlines()) == 4


def test_a_generated_flag_changes_the_geometry(capsys, tmp_path):
    for sides in (3, 7):
        run(
            capsys,
            "render",
            "polygon.regular",
            "--sides",
            str(sides),
            "--out",
            str(tmp_path / f"{sides}.svg"),
        )
    assert len(svg_strokes((tmp_path / "3.svg").read_text())[0][0]) == 3
    assert len(svg_strokes((tmp_path / "7.svg").read_text())[0][0]) == 7


def test_a_parameter_the_command_line_cannot_say_comes_from_the_example(capsys, tmp_path):
    # kaleidoscope takes another motif; there is no flag for that, and the
    # motif still has to render.
    out = tmp_path / "k.svg"
    assert run(capsys, "render", "kaleidoscope", "--group", "D6", "--out", str(out))[0] == 0
    assert svg_strokes(out.read_text())


def test_a_boolean_parameter_becomes_a_pair_of_flags(capsys, tmp_path):
    plain = tmp_path / "a.svg"
    merged = tmp_path / "b.svg"
    run(capsys, "render", "solid.cube", "--no-merge", "--out", str(plain))
    run(capsys, "render", "solid.cube", "--merge", "--out", str(merged))
    assert len(svg_strokes(plain.read_text())) > len(svg_strokes(merged.read_text()))


def test_a_literal_parameter_becomes_a_choice(capsys, tmp_path):
    assert (
        run(capsys, "render", "girih.tile", "--shape", "bowtie", "--out", str(tmp_path / "g.svg"))[
            0
        ]
        == 0
    )
    with pytest.raises(SystemExit):
        main(["render", "girih.tile", "--shape", "octagon"])


def test_a_negative_coordinate_does_not_look_like_an_option(capsys, tmp_path):
    # argparse reads "-60,-60,60,60" as an option, because it starts with a
    # dash and is not a plain negative number.
    out = tmp_path / "t.json"
    assert (
        run(capsys, "render", "tiling.square", "--region", "-60,-60,60,60", "--out", str(out))[0]
        == 0
    )
    assert load_design(out).bounds.min_x >= -60.0


def test_the_equals_form_still_works(capsys, tmp_path):
    out = tmp_path / "t.json"
    assert (
        run(capsys, "render", "tiling.square", "--region=-60,-60,60,60", "--out", str(out))[0] == 0
    )


def test_samples_resamples(capsys):
    _, out, _ = run(capsys, "render", "spiral.golden", "--samples", "20")
    assert len(out.splitlines()) == 21


def test_a_stride_lets_the_count_fall_out_of_the_geometry(capsys):
    _, out, _ = run(capsys, "render", "circle", "--radius", "100", "--stride", "50")
    assert 10 <= len(out.splitlines()) <= 16


def test_an_easing_curve_moves_the_points(capsys):
    equal = run(capsys, "render", "spiral.golden", "--samples", "20")[1]
    eased = run(capsys, "render", "spiral.golden", "--samples", "20", "--ease", "power:2.5")[1]
    assert equal != eased
    assert len(equal.splitlines()) == len(eased.splitlines())


def test_an_easing_curve_without_a_count_says_what_is_missing(capsys):
    code, _, err = run(capsys, "render", "rose", "--ease", "power:2")
    assert code == 2
    assert "--samples" in err


def test_fit_scales_onto_a_canvas(capsys, tmp_path):
    out = tmp_path / "f.json"
    run(capsys, "render", "rose", "--fit", "100x100", "--out", str(out))
    bounds = load_design(out).bounds
    # Uniform scaling, centred in whichever axis has slack, so exactly one of
    # the two fills the canvas and neither overflows it.
    assert max(bounds.width, bounds.height) == pytest.approx(100.0)
    assert bounds.max_x <= 100.0
    assert bounds.max_y <= 100.0


def test_precision_reaches_the_writer(capsys):
    _, out, _ = run(capsys, "render", "polygon.regular", "--sides", "3", "--precision", "1")
    assert all(
        len(cell.partition(".")[2]) <= 1
        for line in out.splitlines()[1:]
        for cell in line.split(",")
    )


def _cells(out):
    """Every coordinate of the CSV on stdout, header dropped."""
    return [cell for line in out.splitlines()[1:] for cell in line.split(",")]


def test_snap_puts_every_coordinate_on_the_grid(capsys):
    _, out, _ = run(capsys, "render", "polygon.regular", "--sides", "7", "--snap", "25")
    assert _cells(out)
    assert all(float(cell) % 25.0 == pytest.approx(0.0) for cell in _cells(out))


def test_snap_mode_reaches_the_transform(capsys):
    args = ("render", "polygon.regular", "--sides", "4", "--samples", "8", "--snap", "1000")
    _, down, _ = run(capsys, *args, "--snap-mode", "floor", "--keep-duplicates")
    _, up, _ = run(capsys, *args, "--snap-mode", "ceil", "--keep-duplicates")
    assert down != up
    assert all(float(cell) <= 0.0 for cell in _cells(down))
    assert all(float(cell) >= 0.0 for cell in _cells(up))


def test_snap_drops_the_stacked_points_unless_told_not_to(capsys):
    args = ("render", "polygon.regular", "--sides", "5", "--samples", "40", "--snap", "100")
    _, dropped, _ = run(capsys, *args)
    _, kept, _ = run(capsys, *args, "--keep-duplicates")
    assert len(kept.splitlines()) == 41  # the header, then every point asked for
    assert 1 < len(dropped.splitlines()) < len(kept.splitlines())


def test_snap_applies_after_fit_so_the_grid_is_the_one_written(capsys):
    _, out, _ = run(capsys, "render", "rose", "--samples", "50", "--fit", "100x100", "--snap", "10")
    assert all(float(cell) % 10.0 == pytest.approx(0.0) for cell in _cells(out))


def test_a_spec_can_be_rendered_instead_of_a_name(capsys, tmp_path):
    from geomotif import save_spec

    spec = save_spec(registry.create("rose", n=7, d=3), tmp_path / "spec.json")
    out = tmp_path / "from-spec.svg"
    assert run(capsys, "render", "--spec", str(spec), "--out", str(out))[0] == 0
    title = svg_root(out.read_text()).find("{http://www.w3.org/2000/svg}title")
    assert title is not None
    assert title.text == "rose"


def test_a_name_and_a_spec_together_are_refused(capsys, tmp_path):
    from geomotif import save_spec

    spec = save_spec(registry.create("rose"), tmp_path / "spec.json")
    code, _, err = run(capsys, "render", "rose", "--spec", str(spec))
    assert code == 2
    assert "not both" in err


def test_rendering_nothing_at_all_is_refused(capsys):
    code, _, err = run(capsys, "render")
    assert code == 2
    assert "name a motif" in err


def test_an_unwritable_suffix_lists_the_ones_that_work(capsys, tmp_path):
    code, _, err = run(capsys, "render", "rose", "--out", str(tmp_path / "r.bmp"))
    assert code == 2
    assert ".svg" in err


def test_render_writes_a_figure(capsys, tmp_path):
    pytest.importorskip("matplotlib")
    import matplotlib

    matplotlib.use("Agg")
    out = tmp_path / "r.png"
    assert run(capsys, "render", "rose", "--samples", "50", "--out", str(out))[0] == 0
    assert out.stat().st_size > 0


# --- explore ---------------------------------------------------------------


def test_explore_writes_one_self_contained_page(capsys, tmp_path):
    out = tmp_path / "rose.html"
    assert run(capsys, "explore", "rose", "--out", str(out), "--steps", "3")[0] == 0
    markup = out.read_text()
    assert markup.startswith("<!DOCTYPE html>")
    assert 'src="' not in markup  # nothing to fetch, from anywhere


def test_explore_takes_a_whole_family(capsys, tmp_path):
    out = tmp_path / "sacred.html"
    run(capsys, "explore", "--family", "sacred", "--out", str(out), "--steps", "3")
    markup = out.read_text()
    # Every motif on the page is from the family, and a family is more than one
    # motif. A motif with nothing to sweep is dropped rather than shown blank.
    shown = re.findall(r'<section class="motif[^"]*" id="([^"]+)"', markup)
    assert len(shown) > 1
    assert set(shown) <= set(registry.names(family="sacred"))


def test_explore_with_nothing_to_explore_says_so(capsys, tmp_path):
    code, _, err = run(capsys, "explore", "--out", str(tmp_path / "x.html"))
    assert code == 2
    assert "name a motif" in err


# --- gallery and demo ------------------------------------------------------


def test_the_gallery_renders_everything_available_with_a_manifest(capsys, tmp_path):
    out = tmp_path / "gallery"
    assert run(capsys, "gallery", "--out", str(out), "--family", "sacred")[0] == 0
    manifest = json.loads((out / "manifest.json").read_text())
    assert len(manifest) == len(registry.names(family="sacred"))
    assert {entry["file"] for entry in manifest} <= {p.name for p in out.iterdir()}


def test_a_manifest_entry_rebuilds_its_motif(tmp_path, capsys):
    from geomotif import from_spec

    out = tmp_path / "gallery"
    run(capsys, "gallery", "--out", str(out), "--family", "knot")
    entry = json.loads((out / "manifest.json").read_text())[0]
    assert from_spec(entry["spec"]).build().paths


def test_a_motif_with_no_spec_still_gets_a_picture(tmp_path, capsys):
    out = tmp_path / "gallery"
    run(capsys, "gallery", "--out", str(out), "--family", "string-art")
    manifest = json.loads((out / "manifest.json").read_text())
    envelope = next(e for e in manifest if e["name"] == "string-art.envelope")
    assert envelope["spec"] is None
    assert (out / envelope["file"]).exists()


def test_the_demo_runs(capsys, tmp_path):
    pytest.importorskip("matplotlib")
    import matplotlib

    matplotlib.use("Agg")
    out = tmp_path / "demo.png"
    assert run(capsys, "demo", str(out))[0] == 0
    assert out.stat().st_size > 0


# --- the pieces the flags are built from -----------------------------------


def test_no_motif_parameter_collides_with_a_reserved_option():
    # argparse has one namespace: a motif parameter named `samples` would
    # shadow the sampling flag and lose its own. Renaming the parameter is the
    # fix; this test is here so the choice is made deliberately.
    taken = {p.name for name in registry.names() for p in registry.describe(name).params}
    assert not (taken & RESERVED)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("linear", "LinearSpacing"),
        ("power:2.5", "PowerSpacing(exponent=2.5, mode='in')"),
        ("power:2.5:out", "PowerSpacing(exponent=2.5, mode='out')"),
        ("exp:out:6", "ExponentialSpacing(mode='out', strength=6.0)"),
        ("smoothstep", "SmoothstepSpacing()"),
    ],
)
def test_the_spacing_mini_syntax_reads_left_to_right(text, expected):
    from geomotif.cli import _spacing

    curve = _spacing(text)
    assert repr(curve) == expected or type(curve).__name__ == expected


@pytest.mark.parametrize("text", ["nonsuch", "power:not-a-number", "exp:sideways"])
def test_a_bad_spacing_is_refused(text):
    import argparse

    from geomotif.cli import _spacing

    with pytest.raises(argparse.ArgumentTypeError):
        _spacing(text)


@pytest.mark.parametrize(
    ("parser", "text"),
    [
        ("_point", "1,2,3"),
        ("_point", "left"),
        ("_bounds", "1,2"),
        ("_size", "800"),
        ("_size", "axb"),
    ],
)
def test_a_malformed_coordinate_is_refused(parser, text):
    import argparse

    import geomotif.cli as cli

    with pytest.raises(argparse.ArgumentTypeError):
        getattr(cli, parser)(text)


def test_a_parameter_that_would_shadow_a_reserved_option_gets_no_flag():
    # No builtin does this -- the test above sees to that -- but a plugin
    # might, and losing the sampling flag would be worse than losing theirs.
    import argparse
    from dataclasses import replace

    import geomotif.cli as cli

    shadow = registry.ParamInfo(name="samples", annotation="int", default=1, required=False)
    info = replace(registry.describe("rose"), params=(shadow,))
    assert cli._flag_for(shadow, info, 1) is None

    parser = argparse.ArgumentParser()
    cli._add_motif_flags(parser, info)
    with pytest.raises(SystemExit):
        parser.parse_args(["--samples", "3"])


def test_a_point_parameter_takes_a_pair(capsys, tmp_path):
    out = tmp_path / "c.json"
    run(capsys, "render", "circle", "--center", "10,-20", "--out", str(out))
    assert load_design(out).bounds.center == pytest.approx((10.0, -20.0))


def test_a_bare_literal_annotation_also_becomes_a_choice(capsys, tmp_path):
    # girih.rosette-tiling writes Literal['hex', 'square'] inline rather than
    # behind a named alias, so the string has to be read directly.
    out = tmp_path / "g.svg"
    assert (
        run(capsys, "render", "girih.rosette-tiling", "--lattice", "square", "--out", str(out))[0]
        == 0
    )
    with pytest.raises(SystemExit):
        main(["render", "girih.rosette-tiling", "--lattice", "octagonal"])


def test_an_unknown_motif_is_reported_rather_than_crashing_the_parser(capsys):
    # The look-ahead that adds a motif's flags has to survive a bad name and
    # leave the complaining to the registry, which does it better.
    code, _, err = run(capsys, "render", "no-such-motif")
    assert code == 2
    assert "no motif registered" in err


def test_an_unavailable_motif_is_described_and_skipped(capsys, tmp_path, monkeypatch):
    monkeypatch.setattr(registry.MotifInfo, "available", property(lambda self: False))
    _, out, _ = run(capsys, "show", "rose")
    assert "pip install" in out

    gallery = tmp_path / "gallery"
    _, _, err = run(capsys, "gallery", "--out", str(gallery), "--family", "sacred")
    assert json.loads((gallery / "manifest.json").read_text()) == []
    assert "skipped" in err


def test_writing_a_figure_without_matplotlib_says_how_to_get_it(tmp_path, monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "geomotif.plotting", None)
    with pytest.raises(SystemExit, match=r"geomotif\[plot\]"):
        main(["render", "rose", "--out", str(tmp_path / "r.png")])


def test_the_version_is_reported(capsys):
    from geomotif import __version__

    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert __version__ in capsys.readouterr().out
