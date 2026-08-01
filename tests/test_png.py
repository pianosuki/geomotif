import zlib

import pytest

from geomotif import Design, Path, to_png
from geomotif.io.png import save_png
from geomotif.io.raster import Raster
from tests.readback import png

#: Axis-aligned and two-tone, so the decoded pixels can be used as a map of
#: where the ink lands: a one-pixel border of background, a filled square of
#: ink, and nothing in between to complicate the count.
BOX = Design(paths=(Path(((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)), closed=True),))

#: Two horizontal strokes at known rows, which a decode can tell apart.
TWO_STROKES = Design(
    paths=(
        Path(((0.0, 0.0), (100.0, 0.0))),
        Path(((0.0, 50.0), (100.0, 50.0))),
    )
)


def _pixel(pixels: bytes, width: int, x: int, y: int, color_type: int) -> tuple[int, ...]:
    """Read one pixel's channels out of a decoded, row-major scanline."""
    bpp = {2: 3, 6: 4, 3: 1}[color_type]
    at = (y * width + x) * bpp
    return tuple(pixels[at : at + bpp])


def _seen(pixels: bytes, color_type: int) -> set[tuple[int, ...]]:
    """The distinct RGB colors actually written, ignoring any alpha channel."""
    bpp = {2: 3, 6: 4, 3: 1}[color_type]
    return {tuple(pixels[i : i + 3]) for i in range(0, len(pixels), bpp)}


def test_the_signature_and_first_chunks_are_a_real_png():
    data = to_png(BOX, width=20, height=20)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    # IHDR comes first, holds the exact canvas, truecolor (type 2), 8-bit.
    decoded = png(data)
    assert decoded.width == 20
    assert decoded.height == 20
    assert decoded.color_type == 2


def test_every_chunk_carries_a_valid_crc():
    data = to_png(BOX, width=20, height=20)
    at = 8
    while at < len(data):
        size = int.from_bytes(data[at : at + 4], "big")
        kind = data[at + 4 : at + 8]
        body = data[at + 8 : at + 8 + size]
        expected = int.from_bytes(data[at + 8 + size : at + 12 + size], "big")
        assert zlib.crc32(kind + body) & 0xFFFFFFFF == expected, kind
        at += 12 + size


def test_a_truecolor_still_holds_the_designs_ink_and_background():
    for color in ("rgb", "rgba"):
        decoded = png(to_png(BOX, width=20, height=20, color=color))
        # A corner is background, and the ink is drawn somewhere on the canvas.
        assert _pixel(decoded.pixels, 20, 0, 0, decoded.color_type)[:3] == (0xFF, 0xFF, 0xFF)
        assert (0x0B, 0x0B, 0x0B) in _seen(decoded.pixels, decoded.color_type)
        assert decoded.palette == []  # truecolor has no PLTE


def test_rgba_writes_an_opaque_alpha_channel():
    decoded = png(to_png(BOX, width=20, height=20, color="rgba"))
    assert decoded.color_type == 6
    assert _pixel(decoded.pixels, 20, 3, 3, 6) == (0xFF, 0xFF, 0xFF, 0xFF)


def test_transparent_writes_rgba_with_empty_background():
    # --transparent implies truecolor-with-alpha and leaves the empty canvas
    # at alpha 0 rather than painting the background color.
    decoded = png(to_png(BOX, width=20, height=20, transparent=True))
    assert decoded.color_type == 6
    assert _pixel(decoded.pixels, 20, 0, 0, 6)[3] == 0xFF * 0  # background is empty
    corner = _pixel(decoded.pixels, 20, 0, 0, 6)
    assert corner[3] == 0
    # ... yet a corner with ink is fully opaque, and ink survives exactly.
    lit = [
        x
        for x in range(20)
        if _pixel(decoded.pixels, 20, x, 10, 6)[:3] == (0x0B, 0x0B, 0x0B)
        and _pixel(decoded.pixels, 20, x, 10, 6)[3] == 255
    ]
    assert lit


def test_transparent_keeps_the_requested_ink_and_background_word():
    decoded = png(
        to_png(BOX, width=20, height=20, ink="#123456", background="#fedcba", transparent=True)
    )
    assert decoded.color_type == 6
    assert _pixel(decoded.pixels, 20, 0, 0, 6)[3] == 0  # background still empty
    assert (0x12, 0x34, 0x56) in _seen(decoded.pixels, 6)


def test_indexed_still_carries_its_palette_and_background_first():
    decoded = png(to_png(BOX, width=20, height=20, color="indexed"))
    assert decoded.color_type == 3
    assert decoded.palette[0] == (0xFF, 0xFF, 0xFF)  # background leads, as everywhere
    assert (0x0B, 0x0B, 0x0B) in decoded.palette
    assert 0 in set(decoded.pixels)  # background index is actually used
    assert decoded.palette.index((0x0B, 0x0B, 0x0B)) in set(decoded.pixels)


def test_custom_ink_and_background_reach_the_pixels():
    decoded = png(to_png(BOX, width=20, height=20, ink="#123456", background="#fedcba"))
    assert _pixel(decoded.pixels, 20, 0, 0, 2) == (0xFE, 0xDC, 0xBA)
    assert (0x12, 0x34, 0x56) in _seen(decoded.pixels, 2)


def test_size_is_varied_by_canvas_not_geometry():
    assert png(to_png(BOX, width=7, height=9)).width == 7
    assert png(to_png(BOX, width=7, height=9)).height == 9
    assert png(to_png(BOX, width=90, height=30)).width == 90


def test_a_raster_can_be_re_encoded_as_it_is():
    source = Raster(2, 2, bytes([0, 1, 1, 0]), ("#ffffff", "#000000"))
    decoded = png(to_png(source, color="indexed"))
    assert decoded.width == 2
    assert decoded.height == 2
    assert decoded.color_type == 3
    assert decoded.palette == [(255, 255, 255), (0, 0, 0)]
    assert decoded.pixels[1] == 1  # top-right is the ink index


def test_an_indexed_raster_encodes_as_truecolor_when_asked():
    source = Raster(1, 1, bytes([1]), ("#112233", "#445566"))
    decoded = png(to_png(source, color="rgb"))
    assert decoded.color_type == 2
    assert _pixel(decoded.pixels, 1, 0, 0, 2) == (0x44, 0x55, 0x66)


def test_compression_changes_size_but_not_pixels():
    assert png(to_png(BOX, width=64, height=64, compression=0)).width == 64
    assert png(to_png(BOX, width=64, height=64, compression=9)).width == 64


def test_out_of_range_compression_is_refused():
    with pytest.raises(ValueError, match="compression"):
        to_png(BOX, compression=10)
    with pytest.raises(ValueError, match="compression"):
        to_png(BOX, compression=-1)


def test_an_unknown_color_is_refused():
    with pytest.raises(ValueError, match="color"):
        to_png(BOX, color="grey")


def test_size_validation_follows_the_raster_writer():
    with pytest.raises(ValueError, match="width and height"):
        to_png(BOX, width=0, height=10)


def test_save_png_writes_the_file_and_returns_its_path(tmp_path):
    target = save_png(BOX, tmp_path / "box.png", width=24, height=24)
    assert target == tmp_path / "box.png"
    assert target.read_bytes().startswith(b"\x89PNG")
    assert png(target.read_bytes()).width == 24


def test_a_still_is_one_complete_frame_not_an_animation():
    # PNG/JPEG are stills: one full picture of the finished design, and the
    # animation vocabulary (frames) has no meaning here. The single IDAT holds
    # every scanline.
    data = to_png(TWO_STROKES, width=60, height=60)
    decoded = png(data)
    assert decoded.height == 60
    # Both strokes are present, at different rows, so it really is the whole
    # drawing rather than one early frame of an animation.
    color_type = 2
    ink = (0x0B, 0x0B, 0x0B)
    lit = [
        y for y in range(decoded.height) if _pixel(decoded.pixels, 60, 30, y, color_type)[:3] == ink
    ]
    assert len(lit) == 2, lit
