"""color and layers: how a design is drawn, rather than what it is.

Geometry says where the ink goes. A :class:`Style` says which pen puts it
there -- a layer name, a color, a stroke width -- and it rides along in
:attr:`Design.meta` rather than in :class:`~geomotif.Path`, because none of it
changes the maths. A design keeps its styles through every transform, every
resample and every overlay, and drops them the moment you ask for the
coordinates alone.

Layers are the part that earns its keep. A pen plotter draws one pen at a
time, so a two-color drawing is two files or one file with two layers; the
SVG writer emits the groups Inkscape and ``vpype`` already understand, and the
DXF writer emits real DXF layers::

    from geomotif import layer, save_svg, styled
    from geomotif.motifs import Circle, Phyllotaxis

    outline = styled(Circle(radius=100).build(), layer="pen1", stroke="black")
    seeds = styled(Phyllotaxis().build(), layer="pen2", stroke="crimson")
    save_svg(layer(outline, seeds), "two-pens.svg")

Nothing is required to have a style, and a design without one writes exactly
the file it wrote before this module existed.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from types import MappingProxyType
from typing import TYPE_CHECKING

from .types import PATH_STYLE_KEY, POINT_STYLE_KEY, Design, select_styles

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "Style",
    "by_layer",
    "layer_names",
    "point_styles_of",
    "styled",
    "styles_of",
]


@dataclass(frozen=True, slots=True)
class Style:
    """How one stroke or one loose point is drawn.

    Every field is optional and ``None`` means "not stated", which is not the
    same as a default: an unstated color takes whatever the writer was told
    to use, so a style that names only a layer still draws in the document's
    own ink.

    Parameters
    ----------
    layer : str, optional
        Which layer the geometry belongs on. SVG writes these as the labeled
        groups Inkscape and ``vpype`` read; DXF writes them as real layers, so
        the name has to be one DXF permits.
    stroke : str, optional
        Line color, as any CSS color string. DXF has no notion of an
        arbitrary color, so its writer maps the seven it can name and leaves
        the rest to the layer.
    width : float, optional
        Stroke width, in the units the writer is working in. Must be > 0.
    fill : str, optional
        Fill color for closed paths. Line art rarely wants one, which is why
        it is not the default.
    """

    layer: str | None = None
    stroke: str | None = None
    width: float | None = None
    fill: str | None = None

    def __post_init__(self) -> None:
        if self.width is not None and self.width <= 0.0:
            raise ValueError(f"width must be > 0, got {self.width}")
        if self.layer is not None and not self.layer.strip():
            raise ValueError(f"layer must be a name, got {self.layer!r}")

    def __bool__(self) -> bool:
        """Whether this style states anything at all."""
        return any(getattr(self, f.name) is not None for f in fields(self))

    def merged(self, other: Style | None) -> Style:
        """Return this style with everything ``other`` states laid over it.

        Silence loses: a field ``other`` leaves at ``None`` keeps this style's
        value, which is what makes ``styled`` composable -- setting a color
        later must not quietly clear the layer set earlier.
        """
        if other is None:
            return self
        stated = {f.name: getattr(other, f.name) for f in fields(other)}
        return replace(self, **{k: v for k, v in stated.items() if v is not None})


def styled(
    design: Design,
    style: Style | None = None,
    *,
    layer: str | None = None,
    stroke: str | None = None,
    width: float | None = None,
    fill: str | None = None,
) -> Design:
    """Return ``design`` with a style laid over every stroke and loose point.

    Parameters
    ----------
    design : Design
        What to style. Returned unchanged if nothing is actually stated.
    style : Style, optional
        A whole style to apply.
    layer, stroke, width, fill
        Individual fields, applied over ``style`` where both are given. This
        is the form to reach for: ``styled(design, layer="pen1")``.

    Returns
    -------
    Design
        The same geometry, with styles merged over whatever it already
        carried -- so a second call that names a color keeps the layer the
        first one set.
    """
    over = Style(layer=layer, stroke=stroke, width=width, fill=fill)
    applied = (style or Style()).merged(over)
    if not applied:
        return design

    meta = dict(design.meta)
    meta[PATH_STYLE_KEY] = tuple(
        (existing or Style()).merged(applied) for existing in styles_of(design)
    )
    meta[POINT_STYLE_KEY] = tuple(
        (existing or Style()).merged(applied) for existing in point_styles_of(design)
    )
    return Design(design.paths, design.points, MappingProxyType(meta))


def styles_of(design: Design) -> tuple[Style | None, ...]:
    """Return one style per stroke, ``None`` where a stroke has none.

    Always exactly as long as ``design.paths``, whatever the metadata says, so
    callers can zip the two without checking.
    """
    return _aligned(design.meta, PATH_STYLE_KEY, len(design.paths))


def point_styles_of(design: Design) -> tuple[Style | None, ...]:
    """Return one style per loose point, ``None`` where a point has none."""
    return _aligned(design.meta, POINT_STYLE_KEY, len(design.points))


def layer_names(design: Design) -> tuple[str, ...]:
    """Return the layers a design uses, in the order they first appear.

    First appearance rather than alphabetical: layer order is drawing order,
    and a plotter changes pens in the order the file lists them.
    """
    seen: dict[str, None] = {}
    for style in (*styles_of(design), *point_styles_of(design)):
        if style is not None and style.layer is not None:
            seen.setdefault(style.layer, None)
    return tuple(seen)


def by_layer(design: Design) -> dict[str | None, Design]:
    """Split a design into one sub-design per layer, styles and all.

    Returns
    -------
    dict
        Keyed by layer name, in first-appearance order, with ``None`` holding
        whatever carries no layer. The key is ``None`` rather than some
        stand-in name because each writer has its own idea of what the
        unnamed layer is called -- ``"0"`` in DXF, ``1`` in ``vpype`` -- and
        picking one here would be wrong somewhere else.
    """
    path_styles = styles_of(design)
    point_styles = point_styles_of(design)

    order: dict[str | None, None] = {}
    for style in (*path_styles, *point_styles):
        order.setdefault(style.layer if style is not None else None, None)

    split: dict[str | None, Design] = {}
    for name in order:
        paths = [i for i, style in enumerate(path_styles) if _layer_of(style) == name]
        points = [i for i, style in enumerate(point_styles) if _layer_of(style) == name]
        split[name] = Design(
            tuple(design.paths[i] for i in paths),
            tuple(design.points[i] for i in points),
            select_styles(design.meta, paths=paths, points=points),
        )
    return split


def _layer_of(style: Style | None) -> str | None:
    """Return the layer a style names, treating "no style" as "no layer"."""
    return style.layer if style is not None else None


def _aligned(meta: Mapping[str, object], key: str, count: int) -> tuple[Style | None, ...]:
    """Return the styles under ``key``, padded and type-checked to ``count`` entries.

    The metadata is a plain mapping that anything may have written to, so what
    comes out is checked rather than trusted: a value that is not a style is
    read as no style at all, which degrades to an unstyled drawing instead of
    an exception halfway through a writer.
    """
    stored = meta.get(key)
    if not isinstance(stored, tuple):
        return (None,) * count
    entries = [value if isinstance(value, Style) else None for value in stored[:count]]
    entries.extend([None] * (count - len(entries)))
    return tuple(entries)
