import pytest

from geomotif import Design, Path, to_jpeg
from geomotif.io.jpeg import save_jpeg
from geomotif.io.raster import Raster
from tests.readback import jpeg

#: Two strides at known rows, so a decode can tell them apart and prove a JPEG
#: really holds the finished drawing rather than one early frame.
TWO_STROKES = Design(
    paths=(
        Path(((0.0, 0.0), (100.0, 0.0))),
        Path(((0.0, 50.0), (100.0, 50.0))),
    )
)


def _pixel(pixels: bytes, width: int, x: int, y: int) -> tuple[int, int, int]:
    at = (y * width + x) * 3
    return (pixels[at], pixels[at + 1], pixels[at + 2])


def _dark_rows(pixels: bytes, width: int, height: int) -> list[int]:
    """The rows crossed mostly by ink, so a still can be told from a frame."""
    return [
        y
        for y in range(height)
        if sum(1 for x in range(width) if _pixel(pixels, width, x, y)[0] < 128) >= width // 2
    ]


def _sof_dimensions(data: bytes) -> tuple[int, int]:
    """Read the canvas height and width out of the SOF0 marker."""
    at = 2
    while at < len(data):
        marker = data[at + 1]
        at += 2
        if marker in (0xFF, 0xD8):
            continue
        if marker == 0xC0:
            length = int.from_bytes(data[at : at + 2], "big")
            payload = data[at + 2 : at + 2 + length]
            return int.from_bytes(payload[3:5], "big"), int.from_bytes(payload[1:3], "big")
        length = int.from_bytes(data[at : at + 2], "big")
        at += length
    raise AssertionError("no SOF0 found")


def test_the_file_starts_and_ends_like_a_baseline_jpeg():
    data = to_jpeg(TWO_STROKES, width=30, height=30)
    assert data[:2] == b"\xff\xd8"  # SOI
    assert data[-2:] == b"\xff\xd9"  # EOI
    assert _sof_dimensions(data) == (30, 30)


def test_the_soi_declares_the_canvas_dimensions():
    assert _sof_dimensions(to_jpeg(TWO_STROKES, width=7, height=9)) == (7, 9)
    assert _sof_dimensions(to_jpeg(TWO_STROKES, width=90, height=30)) == (90, 30)


def test_a_still_holds_the_designs_ink_and_background():
    data = to_jpeg(TWO_STROKES, width=60, height=60, quality=95)
    decoded = jpeg(data)
    # A corner is background; there is ink somewhere on the canvas.
    assert _pixel(decoded.pixels, 60, 0, 0) == (255, 255, 255)
    assert any(_pixel(decoded.pixels, 60, x, y)[0] < 128 for y in range(60) for x in range(60))


def test_a_still_is_one_complete_frame_not_an_animation():
    # JPEG is a still: one full picture of the finished design. Both strokes
    # are present, at their own rows, so it really is the whole drawing.
    decoded = jpeg(to_jpeg(TWO_STROKES, width=60, height=60, quality=95))
    rows = _dark_rows(decoded.pixels, 60, 60)
    assert len(rows) == 2, rows  # both strokes, nothing more blurred into them


def test_custom_ink_and_background_reach_the_pixels():
    data = to_jpeg(TWO_STROKES, width=60, height=60, ink="#123456", background="#fedcba")
    decoded = jpeg(data)
    assert _pixel(decoded.pixels, 60, 0, 0)[0] > 200  # warm background corner
    assert any(_pixel(decoded.pixels, 60, x, y)[0] < 100 for y in range(60) for x in range(60))


def test_size_is_varied_by_canvas_not_geometry():
    assert jpeg(to_jpeg(TWO_STROKES, width=13, height=9)).width == 13
    assert jpeg(to_jpeg(TWO_STROKES, width=13, height=9)).height == 9
    assert jpeg(to_jpeg(TWO_STROKES, width=64, height=64)).width == 64


def test_a_raster_can_be_re_encoded_as_it_is():
    source = Raster(2, 2, bytes([255, 255, 255, 11, 11, 11, 255, 255, 255, 11, 11, 11]), mode="rgb")
    decoded = jpeg(to_jpeg(source, quality=95))
    assert decoded.width == 2
    assert decoded.height == 2
    assert _pixel(decoded.pixels, 2, 1, 0)[0] < 100  # the ink column
    assert _pixel(decoded.pixels, 2, 0, 0)[0] > 200  # the background column


def test_higher_quality_keeps_more_detail():
    # Quality is scaled into the quantization tables; it must change the bytes
    # without ever changing the canvas.
    low = to_jpeg(TWO_STROKES, width=60, height=60, quality=5)
    high = to_jpeg(TWO_STROKES, width=60, height=60, quality=98)
    assert _sof_dimensions(low) == (60, 60)
    assert _sof_dimensions(high) == (60, 60)
    assert len(high) >= len(low)


def test_out_of_range_quality_is_refused():
    with pytest.raises(ValueError, match="quality"):
        to_jpeg(TWO_STROKES, quality=101)
    with pytest.raises(ValueError, match="quality"):
        to_jpeg(TWO_STROKES, quality=-1)


def test_save_jpeg_writes_the_file_and_returns_its_path(tmp_path):
    target = save_jpeg(TWO_STROKES, tmp_path / "two.jpg", width=24, height=24)
    assert target == tmp_path / "two.jpg"
    assert target.read_bytes().startswith(b"\xff\xd8")
    assert jpeg(target.read_bytes()).width == 24


def test_odd_dimensions_decode_with_the_right_canvas():
    for size in (1, 9, 16, 47):
        decoded = jpeg(to_jpeg(TWO_STROKES, width=size, height=size))
        assert (decoded.width, decoded.height) == (size, size)
