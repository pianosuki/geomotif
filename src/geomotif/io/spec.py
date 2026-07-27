"""A design's recipe rather than its points: the motif and its parameters.

:func:`~geomotif.io.points.save_points` writes what a design *is*; this module
writes what would produce it. The file is a few hundred bytes instead of a few
hundred kilobytes, it survives a change of point count or spacing curve, and it
is what the gallery manifest and the CLI's ``--spec`` flag are built on.

The on-disk shape is the same nested object at every depth::

    {
      "geomotif": "1.0.0",
      "motif": "polygon.star",
      "params": {"points": 7, "step": 3, "center": [0.0, 0.0]}
    }

A parameter that is itself a motif -- the composers in :mod:`geomotif.compose`
take one -- is written as that same ``{"motif": ..., "params": ...}`` object, so
a spec nests without needing a second notation. A parameter that is a value
dataclass (:class:`~geomotif.Bounds`, ``Ring``, ``IFSMap``) becomes a
``{"$type": ...}`` object naming its class.

Between them those two cases cover every builtin motif except the two whose
parameter *is* a Python function: a motif defined by code cannot be rebuilt from
data, and asking for its spec says so rather than writing a file that will not
load.
"""

from __future__ import annotations

import dataclasses
import importlib
import importlib.metadata
import json
import math
import pathlib
from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING

from ..core import registry
from ..core.motif import SupportsBuild
from ..core.types import Design

if TYPE_CHECKING:
    from os import PathLike

    from ..core.motif import Motif

__all__ = [
    "PARAMS_KEY",
    "TYPE_KEY",
    "VERSION_KEY",
    "from_spec",
    "load_spec",
    "save_spec",
    "to_spec",
]

#: Records the writing library's version. Read back for information only --
#: nothing is refused on a mismatch, because a spec is data and data that
#: loaded once should keep loading. It is here so that a future format change
#: *can* be detected rather than guessed at.
VERSION_KEY = "geomotif"

#: Where a spec's constructor arguments live. Nesting them, rather than
#: spreading them alongside ``"motif"``, is what keeps every parameter name
#: usable: a motif with a parameter called ``geomotif`` would otherwise
#: collide with the file's own keys.
PARAMS_KEY = "params"

#: Marks an object as a value dataclass rather than a plain mapping, and names
#: the class to rebuild it with.
TYPE_KEY = "$type"


def to_spec(source: SupportsBuild | Design) -> dict[str, object]:
    """Return the JSON-ready recipe for a motif, or for the design it built.

    Parameters
    ----------
    source : Motif or Design
        A motif, or any design whose :attr:`~geomotif.Design.meta` records the
        motif that produced it -- which every builtin motif's does.

    Returns
    -------
    dict
        ``{"geomotif": version, "motif": name, "params": {...}}``, holding only
        JSON types and ready for :func:`json.dumps`.

    Raises
    ------
    ValueError
        If ``source`` is a design with no motif recorded in its metadata.
    TypeError
        If a parameter cannot be written as data -- see the module docstring.

    Examples
    --------
    >>> from geomotif.motifs import Star
    >>> to_spec(Star(points=7))["motif"]
    'star'
    """
    live = _live_spec(source)
    name = live[registry.NAME_KEY]
    params = {key: value for key, value in live.items() if key != registry.NAME_KEY}
    # Imported at call time rather than at module scope: this module is part of
    # the package whose version it reads, so the two would import in a cycle.
    from .. import __version__

    return {
        VERSION_KEY: __version__,
        registry.NAME_KEY: name,
        PARAMS_KEY: _encode(params, where=str(name)),
    }


def from_spec(data: Mapping[str, object]) -> Motif:
    """Rebuild the motif a spec describes.

    The version stamp is not consulted; a spec is data, and data that loaded
    once should keep loading.

    Raises
    ------
    ValueError
        If the mapping names no motif, or names a value type this library will
        not import.
    KeyError
        If the motif name is not registered -- including when it belongs to a
        plugin that is not installed.
    """
    return _decode_spec(data, _importable_packages(), where="spec")


def save_spec(
    source: SupportsBuild | Design,
    path: str | PathLike[str],
    *,
    indent: int | None = 2,
) -> pathlib.Path:
    """Write a motif's recipe to a JSON file and return the path written.

    Parameters
    ----------
    source : Motif or Design
        What to describe; see :func:`to_spec`.
    path : str or path-like
        Destination file.
    indent : int, optional
        Passed through to :func:`json.dumps`. Indented by default: a spec is a
        few hundred bytes and is meant to be opened and edited by hand.

    Returns
    -------
    pathlib.Path
        The file that was written.
    """
    target = pathlib.Path(path)
    target.write_text(json.dumps(to_spec(source), indent=indent) + "\n")
    return target


def load_spec(path: str | PathLike[str]) -> Motif:
    """Read a spec file and return the motif it describes.

    Returns
    -------
    Motif
        Ready to :meth:`~geomotif.Motif.build` or
        :meth:`~geomotif.Motif.generate`.
    """
    data = json.loads(pathlib.Path(path).read_text())
    if not isinstance(data, dict):
        raise ValueError(
            f"{path} is not a spec file: expected a JSON object, got {type(data).__name__}"
        )
    return from_spec(data)


def _live_spec(source: SupportsBuild | Design) -> Mapping[str, object]:
    """Return the in-memory spec mapping for a motif or for a design."""
    if not isinstance(source, Design):
        return registry.spec(source)
    if registry.NAME_KEY not in source.meta:
        raise ValueError(
            "this design does not record which motif produced it, so it has no spec. "
            "Every builtin motif sets Design.meta from registry.spec(self); overlaying "
            "two designs merges their metadata and loses that, so a composer that wants "
            "a spec should set meta on its own result"
        )
    return source.meta


def _encode(value: object, *, where: str) -> object:
    """Convert a live parameter value into JSON types, recursively.

    ``where`` is a dotted trail down to the value being converted, so a refusal
    names the offending parameter rather than only its type.
    """
    match value:
        case None | bool() | int() | str():
            return value
        case float():
            if not math.isfinite(value):
                # json.dumps happily writes Infinity and NaN, which no other
                # JSON parser accepts. Refusing beats a file only Python reads.
                raise ValueError(f"cannot write {where} to a spec: {value} is not a JSON number")
            return value
        case SupportsBuild():
            return _encode_motif(value, where=where)
        case tuple() | list():
            return [_encode(item, where=f"{where}[{index}]") for index, item in enumerate(value)]
        case Mapping():
            return {str(k): _encode(v, where=f"{where}.{k}") for k, v in value.items()}
        case _ if dataclasses.is_dataclass(value) and not isinstance(value, type):
            fields = {f.name: getattr(value, f.name) for f in dataclasses.fields(value) if f.init}
            encoded = {k: _encode(v, where=f"{where}.{k}") for k, v in fields.items()}
            return {TYPE_KEY: _dotted_name(type(value)), **encoded}
        case _:
            raise TypeError(
                f"cannot write {where} to a spec: a {type(value).__name__} is not data. "
                f"A motif parameterized by a Python function is defined by code, and can "
                f"only be rebuilt in Python -- pass the motif itself rather than a spec"
            )


def _encode_motif(motif: SupportsBuild, *, where: str) -> dict[str, object]:
    """Encode a nested motif parameter with the same shape as a whole spec."""
    name = registry.name_for(type(motif))
    if name is None:
        raise TypeError(
            f"cannot write {where} to a spec: {type(motif).__qualname__} is not "
            f"registered, so nothing could look it up again -- add @register to it"
        )
    params = {k: v for k, v in registry.spec(motif).items() if k != registry.NAME_KEY}
    return {
        registry.NAME_KEY: name,
        PARAMS_KEY: {k: _encode(v, where=f"{where}.{k}") for k, v in params.items()},
    }


def _dotted_name(cls: type) -> str:
    """Return the import path a value type is written under."""
    return f"{cls.__module__}.{cls.__qualname__}"


def _importable_packages() -> frozenset[str]:
    """Top-level packages a spec file may name a value type from.

    A spec is data, and data must not get to choose which module this process
    imports. The allowance is this library plus any package that has already
    opted in by declaring a motif entry point -- which is exactly the set whose
    value types could legitimately appear in a spec in the first place.
    """
    plugins = {
        entry_point.value.partition(".")[0]
        for entry_point in importlib.metadata.entry_points(group=registry.ENTRY_POINT_GROUP)
    }
    return frozenset({__name__.partition(".")[0], *plugins})


def _meta_from_spec(data: Mapping[str, object]) -> Mapping[str, object]:
    """Return a spec object as the flat mapping :attr:`Design.meta` holds.

    The parameters are decoded but the motif is deliberately *not* built, so a
    design saved by a plugin still loads on a machine without that plugin --
    you simply cannot rebuild it there.
    """
    allowed = _importable_packages()
    name, params = _name_and_params(data, where="meta")
    decoded = {key: _decode(v, allowed, where=f"{name}.{key}") for key, v in params.items()}
    return MappingProxyType({registry.NAME_KEY: name, **decoded})


def _decode_spec(data: Mapping[str, object], allowed: frozenset[str], *, where: str) -> Motif:
    """Rebuild one motif from a ``{"motif": ..., "params": ...}`` mapping."""
    name, params = _name_and_params(data, where=where)
    return registry.create(
        name, **{k: _decode(v, allowed, where=f"{name}.{k}") for k, v in params.items()}
    )


def _name_and_params(data: Mapping[str, object], *, where: str) -> tuple[str, Mapping[str, object]]:
    """Pull the motif name and its parameter mapping out of a spec object."""
    name = data.get(registry.NAME_KEY)
    if not isinstance(name, str):
        raise ValueError(
            f"{where} is not a motif: expected a {registry.NAME_KEY!r} key naming a "
            f"registered motif, got {name!r}"
        )
    params = data.get(PARAMS_KEY, {})
    if not isinstance(params, Mapping):
        raise ValueError(f"{where}: {PARAMS_KEY!r} must be an object, got {type(params).__name__}")
    return name, params


def _decode(value: object, allowed: frozenset[str], *, where: str) -> object:
    """Convert JSON types back into the values a motif constructor expects."""
    match value:
        case list():
            # JSON has one sequence type; every motif parameter holding a
            # sequence is annotated as a tuple, and several of them are hashed.
            return tuple(
                _decode(item, allowed, where=f"{where}[{index}]")
                for index, item in enumerate(value)
            )
        case Mapping() if TYPE_KEY in value:
            cls = _resolve_value_type(str(value[TYPE_KEY]), allowed, where=where)
            return cls(
                **{
                    key: _decode(item, allowed, where=f"{where}.{key}")
                    for key, item in value.items()
                    if key != TYPE_KEY
                }
            )
        case Mapping() if registry.NAME_KEY in value:
            return _decode_spec(value, allowed, where=where)
        case Mapping():
            return {
                str(key): _decode(item, allowed, where=f"{where}.{key}")
                for key, item in value.items()
            }
        case _:
            return value


def _resolve_value_type(dotted: str, allowed: frozenset[str], *, where: str) -> type:
    """Import and return the value dataclass a ``$type`` names."""
    module_name, _, attribute = dotted.rpartition(".")
    if module_name.partition(".")[0] not in allowed:
        raise ValueError(
            f"{where}: refusing to import {dotted!r}. A spec may only name value types "
            f"from {sorted(allowed)} -- the packages that provide motifs here"
        )
    try:
        found = getattr(importlib.import_module(module_name), attribute)
    except (ImportError, AttributeError) as exc:
        raise ValueError(f"{where}: no value type {dotted!r} to rebuild it with ({exc})") from exc
    if not (isinstance(found, type) and dataclasses.is_dataclass(found)):
        raise ValueError(f"{where}: {dotted!r} is not a value type, it is a {type(found).__name__}")
    return found
