"""Write an animated GIF, in pure standard library.

A design that draws itself on, a motif whose parameter sweeps, a figure
turning: an animation says something a still image cannot, and GIF is the one
animated format that plays everywhere with nothing installed -- a README, a
chat window, an issue comment.

It is also, unusually for a 1989 format, small enough to write by hand. The
file is a colour table, a run of frames, and a trailer; the only real work is
**LZW**, and GIF's variant of it is about eighty lines: build a dictionary of
byte strings as you go, emit each match as a code, widen the code as the
dictionary fills, and start again from empty when it is full at 4096 entries.
That is the whole of it, and it keeps the zero-dependency core zero-dependency
out to the animation as well as out to the file.

The frames come from :mod:`geomotif.animate` and the pixels from
:mod:`geomotif.io.raster`; this module is only the container::

    from geomotif.animate import draw_on
    from geomotif.io.gif import save_gif
    from geomotif.motifs import KochSnowflake

    save_gif(draw_on(KochSnowflake(depth=4).build(), frames=60), "koch.gif")
"""

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING, Any

from .raster import colours_in, rasterize

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from os import PathLike

    from ..core.types import Bounds, Design
    from .raster import Raster

__all__ = ["save_gif", "to_gif"]

#: GIF measures a frame's delay in hundredths of a second, and nothing else.
#: Two is the practical floor: browsers treat 0 and 1 as "as fast as you like"
#: and each has its own idea of what that means.
_MIN_DELAY = 2

#: The largest code an LZW dictionary may hold before it has to start over.
_MAX_CODE = 4096


def to_gif(
    frames: Sequence[Design],
    *,
    width: int = 480,
    height: int = 480,
    padding: float = 8.0,
    fps: float = 20.0,
    loop: int = 0,
    ink: str = "#0b0b0b",
    background: str = "#ffffff",
    thickness: int = 1,
    dot_radius: int | None = None,
) -> bytes:
    """Render a sequence of designs as an animated GIF.

    Every frame is drawn against the **same** world rectangle -- the union of
    all of their bounds -- and the same colour table, so a drawing that grows
    stays put instead of swimming about as its own extent changes.

    Parameters
    ----------
    frames : sequence of Design
        What to draw, in order. At least one is needed.
    width, height : int
        Canvas size in pixels.
    padding : float
        Margin reserved on all four sides, in pixels.
    fps : float
        Frames per second. GIF stores a delay in hundredths of a second, so
        the rate is rounded to what the format can actually say.
    loop : int
        How many times to repeat; ``0`` means forever, which is what everyone
        expects of a GIF. ``1`` plays it once.
    ink, background : str
        Default stroke colour and the colour behind everything. A stroke with
        a style of its own is drawn in that instead.
    thickness : int
        Stroke width in pixels.
    dot_radius : int, optional
        Radius for loose points. Defaults to ``thickness``.

    Returns
    -------
    bytes
        A complete GIF89a file.

    Raises
    ------
    ValueError
        If there are no frames, the rate is not positive, or the designs need
        more than 256 colours between them -- which is GIF's limit, not this
        writer's.
    """
    if not frames:
        raise ValueError("cannot write a GIF with no frames")
    if fps <= 0:
        raise ValueError(f"fps must be > 0, got {fps}")
    if loop < 0:
        raise ValueError(f"loop must be >= 0, got {loop}")

    palette = colours_in(frames, ink=ink, background=background)
    if len(palette) > 256:
        raise ValueError(
            f"a GIF has at most 256 colours and these designs need {len(palette)}; "
            f"restyle them onto fewer, or write them as SVG instead"
        )
    shared = _union(frames)
    delay = max(_MIN_DELAY, round(100.0 / fps))

    rasters = [
        rasterize(
            frame,
            width=width,
            height=height,
            padding=padding,
            bounds=shared,
            palette=palette,
            thickness=thickness,
            dot_radius=dot_radius,
        )
        for frame in frames
    ]

    depth = _depth(len(palette))
    parts = [_header(width, height, depth), _colour_table(palette, depth)]
    if len(rasters) > 1:
        parts.append(_looping(loop))
    parts.extend(_frame(raster, delay=delay, animated=len(rasters) > 1) for raster in rasters)
    parts.append(b";")
    return b"".join(parts)


def save_gif(frames: Sequence[Design], path: str | PathLike[str], **kwargs: Any) -> pathlib.Path:
    """Write an animated GIF and return the path written.

    Keyword arguments are passed straight through to :func:`to_gif`.
    """
    target = pathlib.Path(path)
    target.write_bytes(to_gif(frames, **kwargs))
    return target


# --- the container -----------------------------------------------------------


def _union(frames: Iterable[Design]) -> Bounds:
    """Return the rectangle every frame is drawn against.

    An empty frame -- the first frame of a drawing that has not started yet --
    contributes nothing rather than raising, which is why this is not simply a
    reduce over ``design.bounds``.
    """
    combined = None
    for frame in frames:
        if not len(frame):
            continue
        combined = frame.bounds if combined is None else combined.union(frame.bounds)
    if combined is None:
        raise ValueError("cannot write a GIF in which no frame has any geometry")
    return combined


def _depth(colours: int) -> int:
    """Return the number of bits a colour table of this size needs, at least one."""
    bits = 1
    while (1 << bits) < colours:
        bits += 1
    return bits


def _header(width: int, height: int, depth: int) -> bytes:
    """Return the signature and the logical screen descriptor."""
    # 0x80 says a global colour table follows; the low three bits give its
    # size as 2**(n+1), which is why the depth is written one less than it is.
    packed = 0x80 | ((depth - 1) << 4) | (depth - 1)
    return b"GIF89a" + _short(width) + _short(height) + bytes([packed, 0, 0])


def _colour_table(palette: Sequence[str], depth: int) -> bytes:
    """Return the global colour table, padded to the power of two it has to be."""
    table = bytearray()
    for colour in palette:
        table.extend(_rgb(colour))
    table.extend(bytes(3 * ((1 << depth) - len(palette))))
    return bytes(table)


def _looping(loop: int) -> bytes:
    """Return the Netscape application extension: the only way a GIF says "repeat"."""
    # Nothing about looping is in the GIF specification; this block is a
    # convention from Netscape 2.0 that every reader since has implemented.
    return b"\x21\xff\x0bNETSCAPE2.0\x03\x01" + _short(0 if loop == 0 else loop - 1) + b"\x00"


def _frame(raster: Raster, *, delay: int, animated: bool) -> bytes:
    """Return one frame: how long to hold it, where it goes, and its pixels."""
    parts = bytearray()
    if animated:
        # Disposal method 1, "leave it there": every frame here is a full
        # canvas, so there is nothing to restore between them.
        parts.extend(b"\x21\xf9\x04" + bytes([0x04]) + _short(delay) + b"\x00\x00")
    parts.extend(b"\x2c" + _short(0) + _short(0) + _short(raster.width) + _short(raster.height))
    parts.append(0x00)  # no local colour table, not interlaced

    minimum = max(2, _depth(len(raster.palette)))
    parts.append(minimum)
    parts.extend(_blocks(_compress(raster.pixels, minimum)))
    return bytes(parts)


def _short(value: int) -> bytes:
    """Return two bytes, little end first -- every number in a GIF header is one."""
    return value.to_bytes(2, "little")


def _rgb(colour: str) -> bytes:
    """Parse ``#rgb`` or ``#rrggbb`` into three bytes."""
    text = colour.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(c * 2 for c in text)
    if len(text) != 6:
        raise ValueError(f"expected a colour like '#3366ff', got {colour!r}")
    try:
        return bytes.fromhex(text)
    except ValueError:
        raise ValueError(f"expected a colour like '#3366ff', got {colour!r}") from None


def _blocks(data: bytes) -> bytes:
    """Split a stream into the length-prefixed sub-blocks GIF stores it in."""
    out = bytearray()
    for start in range(0, len(data), 255):
        chunk = data[start : start + 255]
        out.append(len(chunk))
        out.extend(chunk)
    out.append(0)
    return bytes(out)


# --- LZW ----------------------------------------------------------------------


def _compress(pixels: bytes, minimum: int) -> bytes:
    """Compress palette indices with GIF's variant of LZW.

    The dictionary starts with one entry per possible index plus two control
    codes -- clear, and end of information -- and grows by one entry per code
    emitted. Codes widen as it fills and the whole dictionary is thrown away
    and restarted when it reaches 4096 entries, which is the largest code GIF
    permits.
    """
    clear = 1 << minimum
    end = clear + 1
    width = minimum + 1
    table = {bytes([i]): i for i in range(clear)}
    following = end + 1

    bits = _Bits()
    bits.write(clear, width)
    run = b""
    for index in pixels:
        candidate = run + bytes([index])
        if candidate in table:
            run = candidate
            continue
        bits.write(table[run], width)
        if following < _MAX_CODE:
            table[candidate] = following
            following += 1
            # Widen before the next code is written, so the decoder -- which is
            # always one entry behind -- reads it at the width it was written.
            if following > (1 << width) and width < 12:
                width += 1
        else:
            bits.write(clear, width)
            table = {bytes([i]): i for i in range(clear)}
            following = end + 1
            width = minimum + 1
        run = candidate[-1:]

    if run:
        bits.write(table[run], width)
    bits.write(end, width)
    return bits.done()


class _Bits:
    """A little-endian bit accumulator, which is the order GIF packs codes in."""

    __slots__ = ("_bits", "_out", "_value")

    def __init__(self) -> None:
        self._out = bytearray()
        self._value = 0
        self._bits = 0

    def write(self, code: int, width: int) -> None:
        """Append ``width`` bits of ``code``, least significant first."""
        self._value |= code << self._bits
        self._bits += width
        while self._bits >= 8:
            self._out.append(self._value & 0xFF)
            self._value >>= 8
            self._bits -= 8

    def done(self) -> bytes:
        """Return everything written, with the last partial byte padded out."""
        if self._bits > 0:
            self._out.append(self._value & 0xFF)
            self._value = 0
            self._bits = 0
        return bytes(self._out)
