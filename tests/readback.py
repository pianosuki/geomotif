"""Read geomotif's own SVG, DXF, GIF, PNG and JPEG back, with nothing but the standard library.

A writer nobody reads is a writer nobody has tested. Every format here is
write-only as far as the library is concerned, so these parsers exist to close
the loop: whatever came out has to contain the strokes that went in, with the
same vertices in the same order and the same idea of which ones are closed.

They are deliberately strict and deliberately small -- they understand exactly
the subset geomotif emits and complain about anything else, which is the point.
None is a general parser and none belongs outside the test suite; the
third-party readers this output was checked against (``svgelements``, ``ezdxf``,
Pillow) are not dependencies and are not needed to run the suite.

Some of them have to *decompress*: a GIF's pixels are LZW, a PNG's rows are
deflated, and a JPEG's scan is Huffman-coded into an 8x8 DCT -- and there is no
reading any of those without implementing the other half. That is exactly why
they are here -- an encoder checked only against its own assumptions is not
checked at all.
"""

from __future__ import annotations

import math
import struct
import xml.etree.ElementTree as ET
import zlib
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
    """The center of every ``<circle>``."""
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


def dxf_entity_colors(text: str) -> list[int | None]:
    """The color index of each drawn entity, or ``None`` where it inherits one."""
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
    """A decoded GIF: the screen it declares, its colors, and its frames."""

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
    assert packed & 0x80, "expected a global color table"
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
        assert data[at + 8] == 0, "expected no local color table and no interlacing"
        at += 9
        minimum = data[at]
        at += 1
        compressed, at = _subblocks(data, at)
        pixels = _lzw_decode(compressed, minimum)
        assert len(pixels) == fw * fh, f"got {len(pixels)} pixels for a {fw}x{fh} frame"
        frames.append(GifFrame(fw, fh, delay, pixels))

    return Gif(width, height, palette, frames, loop)


def _rgb(data: bytes, at: int) -> tuple[int, int, int]:
    """One color-table entry."""
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


# --- PNG -------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Png:
    """A decoded PNG, in the subset geomotif writes: 8-bit, color types 2/6/3."""

    width: int
    height: int
    color_type: int
    palette: list[tuple[int, int, int]]
    pixels: bytes


def png(data: bytes) -> Png:
    """Decode a PNG of the shape geomotif writes, defilter and inflate included."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"not a PNG: {data[:8]!r}"
    width: int | None = None
    height: int | None = None
    color_type: int | None = None
    palette: list[tuple[int, int, int]] = []
    idat = bytearray()
    at = 8
    while at < len(data):
        size = int.from_bytes(data[at : at + 4], "big")
        kind = data[at + 4 : at + 8]
        body = data[at + 8 : at + 8 + size]
        at += 12 + size
        if kind == b"IHDR":
            width, height, bit_depth, color_type, _, _, _ = struct.unpack(">IIBBBBB", body)
            assert bit_depth == 8, f"bit depth {bit_depth}"
        elif kind == b"PLTE":
            assert len(body) % 3 == 0, "a palette is a run of RGB triples"
            palette = [(body[i], body[i + 1], body[i + 2]) for i in range(0, len(body), 3)]
        elif kind == b"IDAT":
            idat.extend(body)
        elif kind == b"IEND":
            break
        else:
            raise AssertionError(f"unexpected chunk {kind!r}")
    if width is None or height is None or color_type is None:
        raise AssertionError("missing IHDR")
    bpp = {2: 3, 6: 4, 3: 1}[color_type]
    return Png(width, height, color_type, palette, _defilter(zlib.decompress(bytes(idat)), width, height, bpp))


def _defilter(raw: bytes, width: int, height: int, bpp: int) -> bytes:
    """Undo the per-scanline filter, which the writer always sets to none."""
    stride = width * bpp
    out = bytearray()
    previous = bytearray(stride)
    at = 0
    for _ in range(height):
        filter_type = raw[at]
        at += 1
        line = bytearray(raw[at : at + stride])
        at += stride
        for index in range(stride):
            left = line[index - bpp] if index >= bpp else 0
            up = previous[index]
            corner = previous[index - bpp] if index >= bpp else 0
            if filter_type == 0:
                pass
            elif filter_type == 1:
                line[index] = (line[index] + left) & 0xFF
            elif filter_type == 2:
                line[index] = (line[index] + up) & 0xFF
            elif filter_type == 3:
                line[index] = (line[index] + (left + up) // 2) & 0xFF
            elif filter_type == 4:
                predictor = left + up - corner
                pa, pb, pc = abs(predictor - left), abs(predictor - up), abs(predictor - corner)
                nearer = left if (pa <= pb and pa <= pc) else (up if pb <= pc else corner)
                line[index] = (line[index] + nearer) & 0xFF
            else:
                raise AssertionError(f"unexpected filter type {filter_type}")
        out.extend(line)
        previous = line
    return bytes(out)


# --- JPEG -------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Jpeg:
    """A decoded baseline JPEG, in the 4:2:0 subset geomotif writes."""

    width: int
    height: int
    pixels: bytes  # RGB, one triple per pixel, row-major


#: The path a block's 64 coefficients are read in, DC first (Annex A).
_ZIGZAG = (
    0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18, 11, 4, 5,
    12, 19, 26, 33, 40, 48, 41, 34, 27, 20, 13, 6, 7, 14, 21, 28,
    35, 42, 49, 56, 57, 50, 43, 36, 29, 22, 15, 23, 30, 37, 44, 51,
    58, 59, 52, 45, 38, 31, 39, 46, 53, 60, 61, 54, 47, 55, 62, 63,
)

#: Cosines for the IDCT, indexed ``_COS[h][f] = cos((2h+1) f pi / 16)``.
_COS = [[math.cos((2 * row + 1) * freq * math.pi / 16) for freq in range(8)] for row in range(8)]


def jpeg(data: bytes) -> Jpeg:
    """Decode a baseline JPEG of the shape geomotif writes, Huffman and IDCT included."""
    assert data[:2] == b"\xff\xd8", f"not a JPEG: {data[:2]!r}"
    width: int | None = None
    height: int | None = None
    quant: dict[int, list[int]] = {}
    huff: dict[tuple[int, int], tuple[tuple[int, ...], tuple[int, ...]]] = {}
    scan: tuple[tuple[int, int, int], ...] = ()
    at = 2
    scan_at = 0
    while at < len(data):
        assert data[at] == 0xFF, f"marker expected at {at}"
        marker = data[at + 1]
        at += 2
        if marker == 0xDA:  # start of scan: the entropy data follows this segment
            length = int.from_bytes(data[at : at + 2], "big")
            payload = data[at + 2 : at + length]
            scan_at = at + length
            components = payload[0]
            scan = tuple(
                (payload[1 + c * 2], payload[2 + c * 2] >> 4, payload[2 + c * 2] & 0xF)
                for c in range(components)
            )
            break
        if marker in (0xFF, 0xD8):
            continue
        length = int.from_bytes(data[at : at + 2], "big")
        payload = data[at + 2 : at + length]
        at += length
        if marker == 0xDB:
            _parse_quant(payload, quant)
        elif marker == 0xC0:
            height = int.from_bytes(payload[1:3], "big")
            width = int.from_bytes(payload[3:5], "big")
        elif marker == 0xC4:
            _parse_huff(payload, huff)

    assert width is not None, "missing SOF0"
    assert height is not None, "missing SOF0"
    assert scan, "missing SOS"

    reader = _ScanReader(_scan_data(data, scan_at))
    return _rebuild(reader, width, height, quant, huff, scan)


def _parse_quant(payload: bytes, quant: dict[int, list[int]]) -> None:
    """Read the quantization tables (precision 0, so one byte per entry)."""
    i = 0
    while i < len(payload):
        tid = payload[i]
        assert tid & 0xF0 == 0, "only 8-bit precision is understood"
        quant[tid & 0x0F] = list(payload[i + 1 : i + 65])
        i += 65


def _parse_huff(
    payload: bytes, huff: dict[tuple[int, int], tuple[tuple[int, ...], tuple[int, ...]]]
) -> None:
    """Read the Huffman tables: 16 length counts, then that many symbols."""
    i = 0
    while i < len(payload):
        cls = payload[i] >> 4
        tid = payload[i] & 0x0F
        counts = tuple(payload[i + 1 : i + 17])
        i += 17
        total = sum(counts)
        values = tuple(payload[i : i + total])
        i += total
        huff[(cls, tid)] = (counts, values)


def _scan_data(data: bytes, at: int) -> bytes:
    """The entropy-coded scan: undo byte-stuffing, stop at EOI."""
    out = bytearray()
    while at < len(data):
        b = data[at]
        at += 1
        if b == 0xFF:
            n = data[at]
            at += 1
            if n == 0x00:
                out.append(0xFF)  # a stuffed 0xFF
            elif n == 0xFF:
                continue  # fill byte
            elif n == 0xD9:
                break  # EOI
            else:
                break  # another marker: nothing more to read
        else:
            out.append(b)
    return bytes(out)


class _ScanReader:
    """Huffman bits of a JPEG scan, read most-significant-bit first."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._bit = 0

    def read(self, n: int) -> int:
        value = 0
        for _ in range(n):
            value = (value << 1) | ((self._data[self._bit // 8] >> (7 - self._bit % 8)) & 1)
            self._bit += 1
        return value


def _decode_huff(counts: tuple[int, ...], values: tuple[int, ...]) -> dict[tuple[int, int], int]:
    """Map ``(length, code)`` to a symbol, from counts-per-length plus symbols.

    The reference DC tables declare one more code slot than they fill, so the
    walk hands out codes only while symbols remain, matching the writer.
    """
    table: dict[tuple[int, int], int] = {}
    code, k = 0, 0
    for length in range(1, 17):
        for _ in range(counts[length - 1]):
            if k >= len(values):
                break
            table[(length, code)] = values[k]
            k += 1
            code += 1
        code <<= 1
    return table


def _read_symbol(reader: _ScanReader, table: dict[tuple[int, int], int]) -> int:
    code = 0
    for length in range(1, 17):
        code = (code << 1) | reader.read(1)
        if (length, code) in table:
            return table[(length, code)]
    raise AssertionError("no Huffman symbol matched")


def _read_coefficient(reader: _ScanReader, size: int) -> int:
    """The signed value a run of ``size`` bits stands for (DC and AC alike)."""
    if size == 0:
        return 0
    value = reader.read(size)
    if value < 1 << (size - 1):
        return value - (1 << size) + 1
    return value


def _rebuild(
    reader: _ScanReader,
    width: int,
    height: int,
    quant: dict[int, list[int]],
    huff: dict[tuple[int, int], tuple[tuple[int, ...], tuple[int, ...]]],
    scan: tuple[tuple[int, int, int], ...],
) -> Jpeg:
    """Block-decode the scan into planes, then up-sample and convert to RGB."""
    dc_table = {tid: _decode_huff(*source) for (cls, tid), source in huff.items() if cls == 0}
    ac_table = {tid: _decode_huff(*source) for (cls, tid), source in huff.items() if cls == 1}

    # Scan components are Y, Cb, Cr in that order, each (id, dc-id, ac-id).
    _, y_dc, y_ac = scan[0]
    _, cb_dc, cb_ac = scan[1]
    _, cr_dc, cr_ac = scan[2]

    mcu_w = (width + 15) // 16
    mcu_h = (height + 15) // 16
    y_w, y_h = mcu_w * 16, mcu_h * 16
    c_w, c_h = mcu_w * 8, mcu_h * 8
    y_plane = bytearray(y_w * y_h)
    cb_plane = bytearray(c_w * c_h)
    cr_plane = bytearray(c_w * c_h)
    quant_y = quant[0]
    quant_c = quant[1]
    prev_dc = [0, 0, 0]

    for my in range(mcu_h):
        for mx in range(mcu_w):
            for by, bx in ((my * 2, mx * 2), (my * 2, mx * 2 + 1), (my * 2 + 1, mx * 2), (my * 2 + 1, mx * 2 + 1)):
                samples = _block(reader, prev_dc, 0, quant_y, dc_table[y_dc], ac_table[y_ac])
                _place(y_plane, y_w, by, bx, samples)
            cbv = _block(reader, prev_dc, 1, quant_c, dc_table[cb_dc], ac_table[cb_ac])
            _place(cb_plane, c_w, my, mx, cbv)
            crv = _block(reader, prev_dc, 2, quant_c, dc_table[cr_dc], ac_table[cr_ac])
            _place(cr_plane, c_w, my, mx, crv)

    return Jpeg(width, height, _to_rgb(y_plane, cb_plane, cr_plane, y_w, c_w, width, height))


def _block(
    reader: _ScanReader,
    prev: list[int],
    comp: int,
    quant: list[int],
    dc_table: dict[tuple[int, int], int],
    ac_table: dict[tuple[int, int], int],
) -> list[list[int]]:
    """One 8x8 block, returned as a natural-order grid of samples (0..255)."""
    diff = _read_coefficient(reader, _read_symbol(reader, dc_table))
    prev[comp] += diff
    zz = [0] * 64
    zz[0] = prev[comp]
    i = 1
    while i < 64:
        rs = _read_symbol(reader, ac_table)
        if rs == 0x00:  # EOB: rest of the block is zero
            break
        if rs == 0xF0:  # ZRL: sixteen more zeros
            i += 16
            continue
        run, size = rs >> 4, rs & 0x0F
        i += run
        if size and i < 64:
            zz[i] = _read_coefficient(reader, size)
        i += 1
    coef = [[0] * 8 for _ in range(8)]
    for v in range(8):
        for u in range(8):
            coef[v][u] = zz[_ZIGZAG[v * 8 + u]] * quant[v * 8 + u]
    return _idct(coef)


def _idct(coef: list[list[int]]) -> list[list[int]]:
    """Inverse DCT of a natural-order coefficient block, clamped and re-centered."""
    samples = [[0] * 8 for _ in range(8)]
    for y in range(8):
        for x in range(8):
            total = 0.0
            for v in range(8):
                cv = math.sqrt(0.5) if v == 0 else 1.0
                cosine_v = _COS[y][v]
                for u in range(8):
                    cu = math.sqrt(0.5) if u == 0 else 1.0
                    total += cu * cv * coef[v][u] * _COS[x][u] * cosine_v
            value = round(total * 0.25) + 128
            samples[y][x] = max(0, min(255, value))
    return samples


def _place(plane: bytearray, width: int, by: int, bx: int, samples: list[list[int]]) -> None:
    for y in range(8):
        row = (by * 8 + y) * width + bx * 8
        plane[row : row + 8] = bytes(samples[y])


def _to_rgb(y_plane, cb_plane, cr_plane, y_w, c_w, width, height) -> bytes:
    """Up-sample chroma to full size, then convert YCbCr to RGB."""
    out = bytearray(width * height * 3)
    for py in range(height):
        cy = py // 2
        for px in range(width):
            cx = px // 2
            yv = y_plane[py * y_w + px]
            cbv = cb_plane[cy * c_w + cx] - 128
            crv = cr_plane[cy * c_w + cx] - 128
            r = yv + 1.402 * crv
            g = yv - 0.344136 * cbv - 0.714136 * crv
            b = yv + 1.772 * cbv
            at = (py * width + px) * 3
            out[at] = max(0, min(255, round(r)))
            out[at + 1] = max(0, min(255, round(g)))
            out[at + 2] = max(0, min(255, round(b)))
    return bytes(out)
