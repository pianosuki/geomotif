"""Write a JPEG still, in pure standard library.

A JPEG is the still picture that trades a little of a PNG's exactness for a
smaller file, and this module is the lossy half of the pair: where the GIF
squeezes into 256 colors and the PNG keeps every one, a JPEG throws away what
an eye would not miss -- the small high-frequency detail in an 8x8 block --
and codes what is left with Huffman's method. It renders a design once, as the
same full-color frame the PNG and GIF writers draw, and then encodes it with
nothing but the standard library and a little arithmetic.

Baseline JPEG is, at heart, a small pipeline that this module walks exactly
once: the RGB sample is changed into the luminance-plus-color space the human
eye is better at, the two color channels are halved (4:2:0, because the eye
cares less about their detail), every 8x8 block is transformed with the DCT,
the transformed coefficients are divided by a quality-scaled table (that is
the lossy step), and what survives is zig-zag-scanned and Huffman-coded
against the standard tables. ``quality`` chooses how much survives::

    from geomotif.io.jpeg import save_jpeg
    from geomotif.motifs import Rose

    save_jpeg(Rose(n=7).build(), "rose.jpg", quality=92)

The writer answers to the same styling vocabulary as the PNG and GIF writers
(``ink``, ``background``, ``thickness``, ``padding``, ``antialias``), so a
design that looks right in one looks the same way here.
"""

from __future__ import annotations

import math
import pathlib
import struct
from typing import TYPE_CHECKING, Any

from ._color import rgb as _rgb
from .raster import _AA_SCALE, Raster, rasterize_rgba

if TYPE_CHECKING:
    from os import PathLike

    from ..core.types import Design

__all__ = ["save_jpeg", "to_jpeg"]

#: The lowest and highest ``quality`` a JPEG may be asked for.
_MIN_QUALITY = 0
_MAX_QUALITY = 100

#: The standard luminance quantization table (Annex K.1). Higher means the eye
#: tolerates more error in that coefficient, so the file gives up less room to
#: the frequencies it barely sees.
_LUM_QUANT = (
    (16, 11, 10, 16, 24, 40, 51, 61),
    (12, 12, 14, 19, 26, 58, 60, 55),
    (14, 13, 16, 24, 40, 57, 69, 56),
    (14, 17, 22, 29, 51, 87, 80, 62),
    (18, 22, 37, 56, 68, 109, 103, 77),
    (24, 35, 55, 64, 81, 104, 113, 92),
    (49, 64, 78, 87, 103, 121, 120, 101),
    (72, 92, 95, 98, 112, 100, 103, 99),
)

#: The standard chrominance quantization table (Annex K.1). Coarser, because the
#: eye cannot resolve color detail as well as it resolves light.
_CHR_QUANT = (
    (17, 18, 24, 47, 99, 99, 99, 99),
    (18, 21, 26, 66, 99, 99, 99, 99),
    (24, 26, 56, 99, 99, 99, 99, 99),
    (47, 66, 99, 99, 99, 99, 99, 99),
    (99, 99, 99, 99, 99, 99, 99, 99),
    (99, 99, 99, 99, 99, 99, 99, 99),
    (99, 99, 99, 99, 99, 99, 99, 99),
    (99, 99, 99, 99, 99, 99, 99, 99),
)

#: The path a block's 64 coefficients are read in, DC first (Annex A).
_ZIGZAG = (
    0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18, 11, 4, 5,
    12, 19, 26, 33, 40, 48, 41, 34, 27, 20, 13, 6, 7, 14, 21, 28,
    35, 42, 49, 56, 57, 50, 43, 36, 29, 22, 15, 23, 30, 37, 44, 51,
    58, 59, 52, 45, 38, 31, 39, 46, 53, 60, 61, 54, 47, 55, 62, 63,
)

#: The reference Huffman tables (Annex K.3), as ``(counts per length, symbols)``.
_DC_LUM = ((0, 1, 5, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0), tuple(range(12)))
_DC_CHR = ((0, 3, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0), tuple(range(12)))
_AC_LUM = (
    (0, 2, 1, 3, 3, 2, 4, 3, 5, 5, 4, 4, 0, 0, 1, 125),
    (
        0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
        0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08,
        0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
        0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28,
        0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45,
        0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
        0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75,
        0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
        0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3,
        0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6,
        0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9,
        0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2,
        0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4,
        0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA,
    ),
)
_AC_CHR = (
    (0, 2, 1, 2, 4, 4, 3, 4, 7, 5, 4, 4, 0, 1, 2, 119),
    (
        0x00, 0x01, 0x02, 0x03, 0x11, 0x04, 0x05, 0x21, 0x31, 0x06, 0x12, 0x41,
        0x51, 0x07, 0x61, 0x71, 0x13, 0x22, 0x32, 0x81, 0x08, 0x14, 0x42, 0x91,
        0xA1, 0xB1, 0xC1, 0x09, 0x23, 0x33, 0x52, 0xF0, 0x15, 0x62, 0x72, 0xD1,
        0x0A, 0x16, 0x24, 0x34, 0xE1, 0x25, 0xF1, 0x17, 0x18, 0x19, 0x1A, 0x26,
        0x27, 0x28, 0x29, 0x2A, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44,
        0x45, 0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58,
        0x59, 0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74,
        0x75, 0x76, 0x77, 0x78, 0x79, 0x7A, 0x82, 0x83, 0x84, 0x85, 0x86, 0x87,
        0x88, 0x89, 0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A,
        0xA2, 0xA3, 0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4,
        0xB5, 0xB6, 0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7,
        0xC8, 0xC9, 0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA,
        0xE2, 0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF2, 0xF3, 0xF4,
        0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA,
    ),
)

#: Cosines for the DCT, indexed as ``_COS[h][f] = cos((2h+1) f pi / 16)``.
_COS = [[math.cos((2 * row + 1) * freq * math.pi / 16) for freq in range(8)] for row in range(8)]


def to_jpeg(
    source: Design | Raster,
    *,
    width: int = 480,
    height: int = 480,
    padding: float = 8.0,
    ink: str = "#0b0b0b",
    background: str = "#ffffff",
    thickness: int = 1,
    dot_radius: int | None = None,
    antialias: bool = False,
    aa_level: int = 8,
    quality: int = 85,
) -> bytes:
    """Render a design -- or re-encode a :class:`~geomotif.io.Raster` -- as JPEG.

    A still is drawn once, exactly the way :func:`to_png` draws a frame, and
    then encoded with baseline JPEG: 4:2:0 chroma subsampling, an 8x8 DCT on
    each block, quality-scaled quantization, and Huffman coding against the
    reference tables. The styling parameters are shared with the PNG and GIF
    writers so one summoning controls all three.

    Parameters
    ----------
    source : Design or Raster
        What to write. A design is drawn; a raster is encoded as it is.
    width, height : int
        Canvas size in pixels. Ignored when ``source`` is already a raster.
    padding : float
        Margin reserved on all four sides, in pixels.
    ink, background : str
        Default stroke color and the color behind everything.
    thickness : int
        Stroke width in pixels.
    dot_radius : int, optional
        Radius for loose points. Defaults to ``thickness``.
    antialias : bool
        Supersample and blend edges. Off by default, so the edges are the
        same hard Bresenham edges they have always been.
    aa_level : int
        How many shades an antialiased edge may blend into. A JPEG keeps full
        color anyway, so this only bounds the drawing, not the encode.
    quality : int
        From 0 (smallest, most loss) to 100 (closest to the original). This is
        what the quantization tables are scaled by.

    Returns
    -------
    bytes
        A complete baseline JPEG file.

    Raises
    ------
    ValueError
        If ``quality`` is outside 0-100.
    """
    if not _MIN_QUALITY <= quality <= _MAX_QUALITY:
        raise ValueError(
            f"quality must be between {_MIN_QUALITY} and {_MAX_QUALITY}, got {quality}"
        )

    rgb_frame = _rgb_frame(
        source,
        width=width,
        height=height,
        padding=padding,
        ink=ink,
        background=background,
        thickness=thickness,
        dot_radius=dot_radius,
        antialias=antialias,
        aa_level=aa_level,
    )
    return _encode(rgb_frame, quality)


def save_jpeg(source: Design | Raster, path: str | PathLike[str], **kwargs: Any) -> pathlib.Path:
    """Render a design -- or re-encode a raster -- as JPEG and write it.

    Keyword arguments are passed straight through to :func:`to_jpeg`.
    """
    target = pathlib.Path(path)
    target.write_bytes(to_jpeg(source, **kwargs))
    return target


def _rgb_frame(
    source: Design | Raster,
    *,
    width: int,
    height: int,
    padding: float,
    ink: str,
    background: str,
    thickness: int,
    dot_radius: int | None,
    antialias: bool,
    aa_level: int,
) -> tuple[int, int, bytes]:
    """Return the RGB plane to encode: a design drawn, or a raster as it is.

    A JPEG has no alpha and no palette, so whatever the raster holds is
    flattened to a run of RGB bytes: an indexed picture spread through its
    palette, an RGBA one with its opaque alpha dropped, an RGB one as it is.
    """
    if isinstance(source, Raster):
        return source.width, source.height, _to_rgb(source)
    rgba = rasterize_rgba(
        source,
        width=width,
        height=height,
        padding=padding,
        ink=ink,
        background=background,
        thickness=thickness,
        dot_radius=dot_radius,
        scale=_AA_SCALE if antialias else 1,
        aa_level=aa_level if antialias else None,
    )
    return rgba.width, rgba.height, _to_rgb(rgba)


def _to_rgb(raster: Raster) -> bytes:
    """Flatten any raster to RGB bytes: index through the palette, strip alpha."""
    pixels = raster.pixels
    mode = raster.mode
    if mode == "indexed":
        entries = [_rgb(color) for color in raster.palette]
        out = bytearray(len(pixels) * 3)
        for at, index in enumerate(pixels):
            out[at * 3 : at * 3 + 3] = entries[index]
        return bytes(out)
    if mode == "rgba":
        out = bytearray()
        for at in range(0, len(pixels), 4):
            out.extend(pixels[at : at + 3])
        return bytes(out)
    return pixels


# --- the encode -------------------------------------------------------------


def _encode(rgb_frame: tuple[int, int, bytes], quality: int) -> bytes:
    """Run the baseline pipeline once and assemble the file."""
    width, height, rgb = rgb_frame

    y_plane, cb_plane, cr_plane = _planes(rgb, width, height)

    q_lum = _scale_table(_LUM_QUANT, quality)
    q_chr = _scale_table(_CHR_QUANT, quality)
    dc_lum = _huffman(_DC_LUM)
    dc_chr = _huffman(_DC_CHR)
    ac_lum = _huffman(_AC_LUM)
    ac_chr = _huffman(_AC_CHR)

    # MCU grid: 16x16 pixels, four 8x8 luminance blocks and one of each chroma.
    mcu_w = (width + 15) // 16
    mcu_h = (height + 15) // 16
    y_w = mcu_w * 16
    y_h = mcu_h * 16
    c_w = mcu_w * 8
    c_h = mcu_h * 8
    y_pad = _pad(y_plane, width, height, y_w, y_h)
    cb_pad = _pad(cb_plane, (width + 1) // 2, (height + 1) // 2, c_w, c_h)
    cr_pad = _pad(cr_plane, (width + 1) // 2, (height + 1) // 2, c_w, c_h)

    bits = _Bits()
    prev = [0, 0, 0]  # last DC per component, in scan order (Y, Cb, Cr)
    for my in range(mcu_h):
        for mx in range(mcu_w):
            for by, bx in (
                (my * 2, mx * 2),
                (my * 2, mx * 2 + 1),
                (my * 2 + 1, mx * 2),
                (my * 2 + 1, mx * 2 + 1),
            ):
                prev[0] = _encode_block(bits, y_pad, y_w, by, bx, q_lum, dc_lum, ac_lum, prev[0])
            prev[1] = _encode_block(bits, cb_pad, c_w, my, mx, q_chr, dc_chr, ac_chr, prev[1])
            prev[2] = _encode_block(bits, cr_pad, c_w, my, mx, q_chr, dc_chr, ac_chr, prev[2])

    entropy = bits.finish()
    out = bytearray(b"\xff\xd8")  # SOI
    out += _segment(b"\xff\xe0", _app0())
    out += _segment(b"\xff\xdb", _dqt(q_lum, q_chr))
    out += _segment(b"\xff\xc0", _sof0(height, width))
    out += _segment(b"\xff\xc4", _dht())
    out += _segment(b"\xff\xda", _sos())
    out += entropy
    out += b"\xff\xd9"  # EOI
    return bytes(out)


def _planes(rgb: bytes, width: int, height: int) -> tuple[bytearray, bytearray, bytearray]:
    """Split RGB pixels into Y, Cb and Cr, chroma subsampled 4:2:0 (2x2)."""
    y = bytearray(width * height)
    cb = bytearray(width * height)
    cr = bytearray(width * height)
    at = 0
    for i in range(width * height):
        r, g, b = rgb[at], rgb[at + 1], rgb[at + 2]
        at += 3
        y[i] = round(0.299 * r + 0.587 * g + 0.114 * b)
        cb[i] = round(-0.168736 * r - 0.331264 * g + 0.5 * b) + 128
        cr[i] = round(0.5 * r - 0.418688 * g - 0.081312 * b) + 128

    cw = (width + 1) // 2
    chh = (height + 1) // 2
    sub_cb = bytearray(cw * chh)
    sub_cr = bytearray(cw * chh)
    for oy in range(chh):
        for ox in range(cw):
            cy = cr_sum = total = 0
            for sy in range(2):
                py = oy * 2 + sy
                if py >= height:
                    continue
                for sx in range(2):
                    px = ox * 2 + sx
                    if px >= width:
                        continue
                    at = py * width + px
                    cy += cb[at]
                    cr_sum += cr[at]
                    total += 1
            slot = oy * cw + ox
            sub_cb[slot] = round(cy / total)
            sub_cr[slot] = round(cr_sum / total)
    return y, sub_cb, sub_cr


def _pad(plane: bytearray | bytes, width: int, height: int, out_w: int, out_h: int) -> bytearray:
    """Copy a plane into a larger one, repeating the last row and column."""
    out = bytearray(out_w * out_h)
    for y in range(height):
        src = plane[y * width : y * width + width]
        row = y * out_w
        out[row : row + width] = src
        edge = src[width - 1]
        for x in range(width, out_w):
            out[row + x] = edge
    last_row = out[(height - 1) * out_w : height * out_w]
    for y in range(height, out_h):
        out[y * out_w : y * out_w + out_w] = last_row
    return out


def _encode_block(
    bits: _Bits,
    plane: bytearray,
    width: int,
    by: int,
    bx: int,
    quant: tuple[tuple[int, ...], ...],
    dc_table: dict[int, tuple[int, int]],
    ac_table: dict[int, tuple[int, int]],
    prev_dc: int,
) -> int:
    """One 8x8 block: DCT, quantize, zig-zag, Huffman. Returns the new DC."""
    zz = _dct_quant(plane, width, by, bx, quant)
    diff = zz[0] - prev_dc
    _write_dc(bits, diff, dc_table)
    _write_ac(bits, zz, ac_table)
    return zz[0]


def _dct_quant(
    plane: bytearray, width: int, by: int, bx: int, quant: tuple[tuple[int, ...], ...]
) -> list[int]:
    """Quantize a block's DCT and scan it into one zig-zag run of 64 values."""
    block = [[plane[(by * 8 + y) * width + bx * 8 + x] - 128 for x in range(8)] for y in range(8)]
    zz = [0] * 64
    for v in range(8):
        for u in range(8):
            cu = math.sqrt(0.5) if u == 0 else 1.0
            cv = math.sqrt(0.5) if v == 0 else 1.0
            total = 0.0
            for y in range(8):
                row = block[y]
                c_v = _COS[y][v]
                for x in range(8):
                    total += row[x] * _COS[x][u] * c_v
            value = 0.25 * cu * cv * total
            step = quant[v][u]
            zz[_ZIGZAG[v * 8 + u]] = round(value / step)
    return zz


def _write_dc(bits: _Bits, diff: int, table: dict[int, tuple[int, int]]) -> None:
    """DC coefficient: category via the DC Huffman table, then the value bits."""
    size = _size(diff)
    _write_huff(bits, table, size)
    if size:
        bits.write(_value_bits(diff, size), size)


def _write_ac(bits: _Bits, zz: list[int], table: dict[int, tuple[int, int]]) -> None:
    """AC coefficients: run-length of zeros plus category, Huffman, then value.

    The end-of-block marker is written only when a block has a run of trailing
    zeros to say so -- a block whose last coefficient sits at zig-zag position
    63 has none, and claiming one would leak a spurious symbol into the next
    block.
    """
    i = 1
    run = 0
    last = 0  # the position of the last nonzero coefficient, 0 if the AC is empty
    while i < 64:
        while i < 64 and zz[i] == 0:
            run += 1
            i += 1
        if i >= 64:
            break
        while run > 15:
            _write_huff(bits, table, 0xF0)  # ZRL: sixteen zeros
            run -= 16
        coefficient = zz[i]
        size = _size(coefficient)
        _write_huff(bits, table, (run << 4) | size)
        bits.write(_value_bits(coefficient, size), size)
        last = i
        run = 0
        i += 1
    if last < 63:
        _write_huff(bits, table, 0x00)  # EOB


def _size(value: int) -> int:
    """Return how many bits a value needs: 0 is special, else its magnitude."""
    return 0 if value == 0 else abs(value).bit_length()


def _value_bits(value: int, size: int) -> int:
    """Return the ``size`` low bits of a signed value, DC and AC alike."""
    if value >= 0:
        return value
    return value + (1 << size) - 1


def _huffman(data: tuple[tuple[int, ...], tuple[int, ...]]) -> dict[int, tuple[int, int]]:
    """Build ``{symbol: (length, code)}`` from counts-per-length plus symbols.

    The reference DC tables declare one more code slot than they fill (a quirk
    of Annex K's published tables); the loop hands out codes only while symbols
    remain, which leaves that unused slot unassigned and harmless.
    """
    counts, values = data
    codes: dict[int, tuple[int, int]] = {}
    code = 0
    k = 0
    for length in range(1, 17):
        for _ in range(counts[length - 1]):
            if k >= len(values):
                break
            codes[values[k]] = (length, code)
            k += 1
            code += 1
        code <<= 1
    return codes


def _write_huff(bits: _Bits, table: dict[int, tuple[int, int]], symbol: int) -> None:
    """Write one Huffman symbol."""
    length, code = table[symbol]
    bits.write(code, length)


class _Bits:
    """A Huffman bit writer: MSB-first, with JPEG's 0xFF byte-stuffing."""

    def __init__(self) -> None:
        self._out = bytearray()
        self._acc = 0
        self._n = 0

    def write(self, code: int, length: int) -> None:
        for i in range(length - 1, -1, -1):
            self._acc = (self._acc << 1) | ((code >> i) & 1)
            self._n += 1
            if self._n == 8:
                self._emit()

    def _emit(self) -> None:
        self._out.append(self._acc)
        if self._acc == 0xFF:
            self._out.append(0)  # a 0xFF in the scan is stuffed with 0x00
        self._acc = 0
        self._n = 0

    def finish(self) -> bytes:
        if self._n:
            pad = 8 - self._n
            self._acc = (self._acc << pad) | ((1 << pad) - 1)  # pad with ones
            self._emit()
        return bytes(self._out)


def _scale_table(table: tuple[tuple[int, ...], ...], quality: int) -> tuple[tuple[int, ...], ...]:
    """Scale a quantization table to a quality: IJG's mapping of 0-100."""
    q = quality if quality >= 1 else 1
    scale = 5000 // q if q < 50 else 200 - q * 2
    return tuple(
        tuple(max(1, min(255, (value * scale + 50) // 100)) for value in row)
        for row in table
    )


# --- the file ---------------------------------------------------------------


def _segment(kind: bytes, payload: bytes) -> bytes:
    """One marker segment: its marker, a big-endian length that counts itself, payload."""
    return kind + struct.pack(">H", len(payload) + 2) + payload


def _app0() -> bytes:
    """Build the JFIF identification segment geomotif writes."""
    return b"JFIF\x00\x01\x01\x00" + struct.pack(">HH", 1, 1) + b"\x00\x00"


def _dqt(lum: tuple[tuple[int, ...], ...], chroma: tuple[tuple[int, ...], ...]) -> bytes:
    """Assemble both quantization tables, luminance first (id 0, then id 1)."""
    return _dqt_table(0, lum) + _dqt_table(1, chroma)


def _dqt_table(tid: int, table: tuple[tuple[int, ...], ...]) -> bytes:
    payload = bytearray([tid])
    for row in table:
        payload.extend(row)
    return bytes(payload)


def _sof0(height: int, width: int) -> bytes:
    """Build the start-of-frame-marker payload: baseline, 8-bit, three components.

    Luminance is sampled 2x2 and the two chroma channels 1x1 -- that is the
    4:2:0 arrangement the encoder and this frame marker agree on, so each MCU
    is four luminance blocks and one of each chroma.
    """
    return (
        bytes([8])
        + struct.pack(">HH", height, width)
        + bytes([3])
        + bytes([1, 0x22, 0, 2, 0x11, 1, 3, 0x11, 1])
    )


def _dht() -> bytes:
    """All four Huffman tables: DC and AC, luminance and chrominance."""
    return (
        _dht_table(0, 0, *_DC_LUM)
        + _dht_table(0, 1, *_DC_CHR)
        + _dht_table(1, 0, *_AC_LUM)
        + _dht_table(1, 1, *_AC_CHR)
    )


def _dht_table(cls: int, tid: int, counts: tuple[int, ...], values: tuple[int, ...]) -> bytes:
    return bytes([(cls << 4) | tid]) + bytes(counts) + bytes(values)


def _sos() -> bytes:
    """Build the start-of-scan payload: all three components, standard selectors."""
    return bytes([3]) + bytes([1, 0x00, 2, 0x11, 3, 0x11]) + bytes([0, 63, 0])
