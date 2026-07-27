"""Read geomotif's own SVG and DXF back, with nothing but the standard library.

A writer nobody reads is a writer nobody has tested. Both formats are
write-only as far as the library is concerned, so these parsers exist to close
the loop: whatever came out has to contain the strokes that went in, with the
same vertices in the same order and the same idea of which ones are closed.

They are deliberately strict and deliberately small -- they understand exactly
the subset geomotif emits and complain about anything else, which is the point.
Neither is a general parser and neither belongs outside the test suite; the
third-party readers this output was checked against (``svgelements``, ``ezdxf``)
are not dependencies and are not needed to run the suite.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

SVG_NS = "http://www.w3.org/2000/svg"

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
