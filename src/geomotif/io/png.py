"""Write a PNG still, in pure standard library.

A still is the finished drawing one more time: where the GIF is a moving
picture, a PNG is a picture that does not move, and this module is its
release form. It renders a design once -- as a full-color, palette-free
frame, antialiased or hard-edged on request -- and then encodes that frame
with nothing but the standard library: the rows are filtered, ``zlib``
compresses them, and every chunk gets its CRC-32, which is the whole of
the PNG file format.

The writer answers to the same styling vocabulary as the GIF writer
(``ink``, ``background``, ``thickness``, ``padding``, ``antialias``), so a
design that looks right as a GIF looks the same way as a PNG. Unlike the
GIF it keeps every color it was drawn in, because a PNG has no 256-color
budget::

    from geomotif.io.png import save_png
    from geomotif.motifs import Rose

    save_png(Rose(n=7).build(), "rose.png")

It can write three ways, chosen by ``color``:

- **``"rgb"``** (the default) -- truecolor, three bytes a pixel. Lossless
  and full color; the picture to reach for by default.
- **``"rgba"``** -- truecolor with an alpha channel, four bytes a pixel.
  Handy when a design supplies its own transparency later; here the alpha
  is opaque.
- **``"indexed"``** -- a palette of at most 256 colors, one byte a pixel.
  The smallest files, at the cost of a palette; the same median-cut
  quantizer the GIF uses shrinks the frame down, with optional dithering.
"""

from __future__ import annotations

import pathlib
import struct
import zlib
from typing import TYPE_CHECKING, Any

from ._color import rgb as _rgb
from .raster import _AA_SCALE, Raster, colors_in, quantize, rasterize, rasterize_rgba

if TYPE_CHECKING:
    from os import PathLike

    from ..core.types import Design

__all__ = ["save_png", "to_png"]

#: The bytes every PNG starts with, marking it as a PNG before anything else.
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

#: How a requested ``color`` spells itself inside the format's IHDR chunk.
_COLOR_TYPE = {"rgb": 2, "rgba": 6, "indexed": 3}

#: zlib's default compression, and the floor for a PNG's ``--compression``.
_MIN_COMPRESSION = 0
_MAX_COMPRESSION = 9


def to_png(
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
    color: str = "rgb",
    compression: int = 6,
) -> bytes:
    """Render a design -- or re-encode a :class:`~geomotif.io.Raster` -- as PNG.

    A still is drawn once, exactly the way :func:`to_gif` draws a frame, and
    then written as a PNG instead of being quantized toward a GIF's colors.
    The styling parameters are shared with the GIF writer so one summoning
    controls both.

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
        When antialiasing into an indexed frame, how many shades an edge
        may blend into per color pair. Ignored for the truecolor paths,
        which keep every level.
    color : str
        ``"rgb"``, ``"rgba"`` or ``"indexed"`` -- how the PNG stores the
        picture. See the module docstring for what each means.
    compression : int
        zlib level from 0 (fast, big) to 9 (slow, small). Must be an
        integer in that range.

    Returns
    -------
    bytes
        A complete PNG file.

    Raises
    ------
    ValueError
        If ``color`` is not one of the three, ``compression`` is out of
        range, or an indexed frame would need more than 256 palette colors.
    """
    if color not in _COLOR_TYPE:
        raise ValueError(f"color must be one of {sorted(_COLOR_TYPE)}, got {color!r}")
    if not _MIN_COMPRESSION <= compression <= _MAX_COMPRESSION:
        raise ValueError(
            f"compression must be between {_MIN_COMPRESSION} and {_MAX_COMPRESSION}, "
            f"got {compression}"
        )

    raster = _frame(
        source,
        color=color,
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
    return _encode(raster, _COLOR_TYPE[color], compression)


def save_png(source: Design | Raster, path: str | PathLike[str], **kwargs: Any) -> pathlib.Path:
    """Render a design -- or re-encode a raster -- as a PNG and write it.

    Keyword arguments are passed straight through to :func:`to_png`.
    """
    target = pathlib.Path(path)
    target.write_bytes(to_png(source, **kwargs))
    return target


def _frame(
    source: Design | Raster,
    *,
    color: str,
    width: int,
    height: int,
    padding: float,
    ink: str,
    background: str,
    thickness: int,
    dot_radius: int | None,
    antialias: bool,
    aa_level: int,
) -> Raster:
    """Return the raster to encode: a design drawn, or a raster as it is."""
    if isinstance(source, Raster):
        return source

    palette = colors_in([source], ink=ink, background=background)
    scale = _AA_SCALE if antialias else 1
    if color == "indexed" and not antialias:
        return rasterize(
            source,
            width=width,
            height=height,
            padding=padding,
            palette=palette,
            ink=ink,
            background=background,
            thickness=thickness,
            dot_radius=dot_radius,
        )

    rgba = rasterize_rgba(
        source,
        width=width,
        height=height,
        padding=padding,
        ink=ink,
        background=background,
        thickness=thickness,
        dot_radius=dot_radius,
        scale=scale,
        aa_level=None if color != "indexed" else aa_level,
    )
    if color == "indexed":
        return quantize([rgba], seeds=palette, max_colors=256, dither=True)[0]
    return rgba


# --- the file ---------------------------------------------------------------


def _encode(raster: Raster, color_type: int, compression: int) -> bytes:
    """Assemble a PNG from a raster and the color type it is stored as.

    Every scanline is prefixed with filter ``0`` (none) -- a valid choice
    that keeps the encode honest without pretending to predict the decoder --
    and the whole run of them is the payload of one compressed IDAT chunk.
    """
    bit_depth = 8
    bpp = {2: 3, 6: 4, 3: 1}[color_type]
    plane, palette = _plane(raster, color_type)
    parts = bytearray(_PNG_SIGNATURE)
    parts.extend(
        _chunk(b"IHDR", struct.pack(">IIBBBBB", raster.width, raster.height, bit_depth, color_type, 0, 0, 0))
    )
    if color_type == 3:
        parts.extend(_chunk(b"PLTE", palette))

    raw = bytearray()
    stride = raster.width * bpp
    for row in range(raster.height):
        raw.append(0)
        start = row * stride
        raw.extend(plane[start : start + stride])
    parts.extend(_chunk(b"IDAT", zlib.compress(bytes(raw), compression)))
    parts.extend(_chunk(b"IEND", b""))
    return bytes(parts)


def _plane(raster: Raster, color_type: int) -> tuple[bytes, bytes]:
    """Return the pixel bytes for a color type, plus its palette if indexed.

    A raster can arrive in any of its three modes; whichever color type the
    caller asked for, the data is laid out to match, converting where the two
    disagree -- expanding an indexed picture to truecolor, dropping an opaque
    alpha, or adding one. The alpha here is always opaque: the raster side
    draws over a solid background.
    """
    pixels = raster.pixels
    mode = raster.mode
    if mode == "indexed":
        entries = [_rgb(color) for color in raster.palette]
        if color_type == 3:
            if len(entries) > 256:
                raise ValueError(f"a PNG palette holds at most 256 colors, got {len(entries)}")
            table = bytearray()
            for r, g, b in entries:
                table.extend((r, g, b))
            return pixels, bytes(table)
        alpha = 4 if color_type == 6 else 3
        out = bytearray(len(pixels) * alpha)
        for at, index in enumerate(pixels):
            r, g, b = entries[index]
            slot = at * alpha
            out[slot : slot + 3] = (r, g, b)
            if alpha == 4:
                out[slot + 3] = 255
        return bytes(out), b""

    # Direct rgb(rgba) modes agree with the request, or lose/gain opaque alpha.
    incoming = 4 if mode == "rgba" else 3
    outgoing = 4 if color_type == 6 else 3
    if incoming == outgoing:
        return pixels, b""
    out = bytearray()
    for at in range(0, len(pixels), incoming):
        out.extend(pixels[at : at + 3])
        if outgoing == 4:
            out.append(255)
    return bytes(out), b""


def _chunk(kind: bytes, data: bytes) -> bytes:
    """Return one PNG chunk: length, type, data, and its CRC-32 over type+data."""
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
