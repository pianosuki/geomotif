"""Read geomotif's own SVG, DXF and GIF back, with nothing but the standard library.

A writer nobody reads is a writer nobody has tested. Every format here is
write-only as far as the library is concerned, so these parsers exist to close
the loop: whatever came out has to contain the strokes that went in, with the
same vertices in the same order and the same idea of which ones are closed.

They are deliberately strict and deliberately small -- they understand exactly
the subset geomotif emits and complain about anything else, which is the point.
None is a general parser and none belongs outside the test suite; the
third-party readers this output was checked against (``svgelements``, ``ezdxf``,
Pillow) are not dependencies and are not needed to run the suite.

The GIF reader is the odd one, in that it has to *decompress*: a GIF's pixels
are LZW and there is no reading them without implementing the other half of
it. That is exactly why it is here -- an encoder checked only against its own
assumptions is not checked at all.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass

SVG_NS = "http://www.w3.org/2000/svg"
INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"

type Point = tuple[float, float]
#: A stroke as read back: its vertices, and whether it closed.
type Stroke = tuple[list[Point], bool]


# --- SVG -------------------------------------------------------------------


def svg_root(text: str) -> ET.Element:
    """Parse the document and return its root, checking it really is an SVG."""
    root = ET.fromstring(text)
    assert root.tag == f"{{{SVG_NS}}}svg", f"root element is {root.tag}"
    return root


def svg_find(text: str, tag: str) -> list[ET.Element]:
    """Every element with the given local name, in document order."""
    return list(svg_root(text).iter(f"{{{SVG_NS}}}{tag}"))


def svg_number(element: ET.Element, name: str) -> float:
    """A numeric attribute, insisting it is actually there."""
    value = element.get(name)
    assert value is not None, f"element has no {name!r} attribute"
    return float(value)


def svg_strokes(text: str) -> list[Stroke]:
    """Every subpath of every ``<path>``, as vertices plus a closed flag."""
    return [sub for element in svg_find(text, "path") for sub in _subpaths(element.get("d", ""))]


def svg_dots(text: str) -> list[Point]:
    """The centre of every ``<circle>``."""
    return [(float(c.get("cx", "0")), float(c.get("cy", "0"))) for c in svg_find(text, "circle")]


def svg_layers(text: str) -> list[str]:
    """The label of every group marked as a layer, in document order."""
    return [
        group.get(f"{{{INKSCAPE_NS}}}label", "")
        for group in svg_find(text, "g")
        if group.get(f"{{{INKSCAPE_NS}}}groupmode") == "layer"
    ]


def _subpaths(d: str) -> list[Stroke]:
    """Parse the ``M x y L x y ... Z`` subset of path data geomotif writes."""
    tokens = d.split()
    found: list[Stroke] = []
    current: list[Point] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "M":
            if current:
                found.append((current, False))
            current = []
            index += 1
        elif token == "L":
            index += 1
        elif token == "Z":
            found.append((current, True))
            current = []
            index += 1
        else:
            assert index + 1 < len(tokens), f"dangling coordinate {token!r} in {d!r}"
            current.append((float(tokens[index]), float(tokens[index + 1])))
            index += 2
    if current:
        found.append((current, False))
    return found


# --- DXF -------------------------------------------------------------------


def dxf_pairs(text: str) -> list[tuple[int, str]]:
    """The whole file as ``(group code, value)`` pairs.

    That is the entirety of DXF's syntax: a code on one line, its value on the
    next. An odd number of lines means something was written without a value,
    which is worth failing on rather than parsing around.
    """
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    assert len(lines) % 2 == 0, "a group code was written without a value"
    return [(int(code), value) for code, value in zip(lines[::2], lines[1::2], strict=True)]


def dxf_records(text: str) -> list[tuple[str, dict[int, str]]]:
    """Split the stream into ``(entity name, codes)`` records; code 0 starts one."""
    records: list[tuple[str, dict[int, str]]] = []
    for code, value in dxf_pairs(text):
        if code == 0:
            records.append((value, {}))
        elif records:
            records[-1][1][code] = value
    return records


def dxf_section(text: str, name: str) -> list[tuple[str, dict[int, str]]]:
    """The records inside one named SECTION."""
    records = dxf_records(text)
    starts = [
        index
        for index, (kind, codes) in enumerate(records)
        if kind == "SECTION" and codes.get(2) == name
    ]
    assert len(starts) == 1, f"expected exactly one {name} section, found {len(starts)}"
    start = starts[0]
    end = next(i for i in range(start + 1, len(records)) if records[i][0] == "ENDSEC")
    return records[start + 1 : end]


def dxf_polylines(text: str) -> list[Stroke]:
    """Every POLYLINE in the entities section, with its VERTEX run."""
    found: list[Stroke] = []
    current: list[Point] | None = None
    for kind, codes in dxf_section(text, "ENTITIES"):
        match kind:
            case "POLYLINE":
                current = []
                found.append((current, int(codes.get(70, "0")) & 1 == 1))
            case "VERTEX":
                assert current is not None, "a VERTEX arrived outside a POLYLINE"
                current.append((float(codes[10]), float(codes[20])))
            case "SEQEND":
                current = None
            case _:
                pass
    return found


def dxf_points(text: str) -> list[Point]:
    """Every POINT entity."""
    return [
        (float(codes[10]), float(codes[20]))
        for kind, codes in dxf_section(text, "ENTITIES")
        if kind == "POINT"
    ]


def dxf_layer_table(text: str) -> list[str]:
    """Every layer the file declares, in the order the table lists them."""
    return [
        codes[2] for kind, codes in dxf_section(text, "TABLES") if kind == "LAYER" and 2 in codes
    ]


def dxf_entity_layers(text: str) -> list[tuple[str, str]]:
    """Each drawn entity as ``(kind, layer)``; the VERTEX run is left out."""
    return [
        (kind, codes.get(8, ""))
        for kind, codes in dxf_section(text, "ENTITIES")
        if kind in {"POLYLINE", "POINT"}
    ]


def dxf_entity_colours(text: str) -> list[int | None]:
    """The colour index of each drawn entity, or ``None`` where it inherits one."""
    return [
        int(codes[62]) if 62 in codes else None
        for kind, codes in dxf_section(text, "ENTITIES")
        if kind in {"POLYLINE", "POINT"}
    ]


def dxf_header(text: str) -> dict[str, list[str]]:
    """The header variables, each with the values that followed its name.

    Header variables are not records the way entities are: code 9 names one
    and whatever codes follow belong to it, so the raw pairs have to be walked
    rather than grouped.
    """
    variables: dict[str, list[str]] = {}
    name: str | None = None
    for code, value in dxf_pairs(text):
        if code == 9:
            name = value
            variables[name] = []
        elif code == 0:
            name = None
        elif name is not None:
            variables[name].append(value)
    return variables


# --- GIF -------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GifFrame:
    """One decoded frame: its size, its delay, and one palette index per pixel."""

    width: int
    height: int
    delay: int
    pixels: bytes


@dataclass(frozen=True, slots=True)
class Gif:
    """A decoded GIF: the screen it declares, its colours, and its frames."""

    width: int
    height: int
    palette: list[tuple[int, int, int]]
    frames: list[GifFrame]
    loop: int | None


def gif(data: bytes) -> Gif:
    """Decode a GIF89a of the shape geomotif writes, LZW and all."""
    assert data[:6] == b"GIF89a", f"not a GIF89a: {data[:6]!r}"
    width, height = _u16(data, 6), _u16(data, 8)
    packed = data[10]
    assert packed & 0x80, "expected a global colour table"
    size = 2 << (packed & 0x07)
    at = 13
    palette = [_rgb(data, at + 3 * i) for i in range(size)]
    at += 3 * size

    frames: list[GifFrame] = []
    loop: int | None = None
    delay = 0
    while at < len(data):
        block = data[at]
        at += 1
        if block == 0x3B:  # trailer
            break
        if block == 0x21:  # extension
            label = data[at]
            at += 1
            chunks, at = _subblocks(data, at)
            if label == 0xF9:
                delay = _u16(chunks, 1)
            elif label == 0xFF and chunks.startswith(b"NETSCAPE2.0"):
                # The eleven-byte name, then a sub-block whose first byte is
                # its own id and whose next two are the repeat count.
                loop = _u16(chunks, 12)
            continue
        assert block == 0x2C, f"unexpected block 0x{block:02x} at {at - 1}"
        left, top = _u16(data, at), _u16(data, at + 2)
        fw, fh = _u16(data, at + 4), _u16(data, at + 6)
        assert (left, top) == (0, 0), "frames are written full-canvas"
        assert data[at + 8] == 0, "expected no local colour table and no interlacing"
        at += 9
        minimum = data[at]
        at += 1
        compressed, at = _subblocks(data, at)
        pixels = _lzw_decode(compressed, minimum)
        assert len(pixels) == fw * fh, f"got {len(pixels)} pixels for a {fw}x{fh} frame"
        frames.append(GifFrame(fw, fh, delay, pixels))

    return Gif(width, height, palette, frames, loop)


def _rgb(data: bytes, at: int) -> tuple[int, int, int]:
    """One colour-table entry."""
    return (data[at], data[at + 1], data[at + 2])


def _u16(data: bytes, at: int) -> int:
    """Read one of GIF's little-endian shorts."""
    return int.from_bytes(data[at : at + 2], "little")


def _subblocks(data: bytes, at: int) -> tuple[bytes, int]:
    """Read a run of length-prefixed sub-blocks, up to the zero that ends it."""
    out = bytearray()
    while data[at]:
        size = data[at]
        out.extend(data[at + 1 : at + 1 + size])
        at += 1 + size
    return bytes(out), at + 1


def _lzw_decode(data: bytes, minimum: int) -> bytes:
    """The other half of the writer's compressor, and the reason it is trusted."""
    clear, end = 1 << minimum, (1 << minimum) + 1
    width = minimum + 1
    table = [bytes([i]) for i in range(clear)] + [b"", b""]
    out = bytearray()
    previous: bytes | None = None
    bit = 0
    available = len(data) * 8
    while bit + width <= available:
        # Codes are packed least significant bit first, across byte boundaries.
        chunk = int.from_bytes(data[bit // 8 : bit // 8 + 3].ljust(3, b"\x00"), "little")
        code = (chunk >> (bit % 8)) & ((1 << width) - 1)
        bit += width
        if code == clear:
            table = [bytes([i]) for i in range(clear)] + [b"", b""]
            width = minimum + 1
            previous = None
            continue
        if code == end:
            break
        if code < len(table):
            entry = table[code]
        else:
            assert previous is not None, f"code {code} arrived before anything to extend"
            assert code == len(table), f"undefined code {code}"
            entry = previous + previous[:1]
        out.extend(entry)
        if previous is not None:
            table.append(previous + entry[:1])
            if len(table) == (1 << width) and width < 12:
                width += 1
        previous = entry
    return bytes(out)
