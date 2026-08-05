"""Motif registration, lookup and introspection.

Registering a motif is what makes it discoverable by name -- to the CLI, to
the gallery builder, to the conformance test suite, and to anyone who wants
to round-trip a design through a JSON spec.

Third-party packages ship their own motifs by declaring an entry point::

    [project.entry-points."geomotif.motifs"]
    my_motifs = "my_package.motifs:register_all"

The builtin catalog and any such plugins are loaded lazily, on the first
registry access rather than at import, so a motif family nobody touches costs
nothing to have installed.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import inspect
import re
from dataclasses import MISSING, dataclass, fields, is_dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, TypeVar

from .motif import Motif, SupportsBuild

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

__all__ = [
    "ENTRY_POINT_GROUP",
    "NAME_KEY",
    "MotifInfo",
    "ParamInfo",
    "create",
    "describe",
    "families",
    "get",
    "name_for",
    "names",
    "register",
    "spec",
]

ENTRY_POINT_GROUP = "geomotif.motifs"

#: The key under which :func:`spec` records a design's motif name. Reserved:
#: a motif with a parameter of this name is refused at registration, because
#: the parameter would overwrite the name and the design could no longer be
#: rebuilt from its own metadata.
NAME_KEY = "motif"

MotifT = TypeVar("MotifT", bound=Motif)

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


@dataclass(frozen=True, slots=True)
class _Entry:
    cls: type[Motif]
    family: str | None
    requires: str | None
    example: Mapping[str, object]


_REGISTRY: dict[str, _Entry] = {}
_motifs_loaded = False


@dataclass(frozen=True, slots=True)
class ParamInfo:
    """One constructor parameter of a motif, as the CLI and docs see it.

    The numeric range fields (``min``, ``max``, ``step``) come from a
    :class:`~geomotif.Range` on the field's ``metadata``; they are ``None``
    when a motif has not declared a bound, in which case a consumer falls
    back to its own heuristic rather than guessing zero.
    """

    name: str
    annotation: str
    default: object
    required: bool
    description: str | None = None
    min: float | None = None
    max: float | None = None
    step: float | None = None


@dataclass(frozen=True, slots=True)
class MotifInfo:
    """Everything known about a registered motif without instantiating it."""

    name: str
    cls: type[Motif]
    family: str | None
    requires: str | None
    summary: str
    doc: str
    params: tuple[ParamInfo, ...]
    example: Mapping[str, object]

    @property
    def available(self) -> bool:
        """Whether the optional dependency this motif needs is installed.

        A motif registered with ``requires=`` can be listed, described and
        documented on a machine that lacks its dependency -- only building
        one raises. This is what lets a listing say so instead of failing to
        import, and what the conformance suite checks before it tries.
        """
        if self.requires is None:
            return True
        try:
            return importlib.util.find_spec(self.requires) is not None
        except (ImportError, ValueError):
            # A namespace package whose parent is missing, or a name that is
            # not importable at all: either way, not installed.
            return False


def _reserves_the_name_key(cls: type) -> bool:
    """Return whether ``cls`` declares a parameter named :data:`NAME_KEY`.

    Typed as a bare ``type`` for the same reason as :func:`_params_for`: mypy
    cannot intersect an abstract motif class with the dataclass protocol, and
    written inline the check reads as unreachable.
    """
    return is_dataclass(cls) and any(field.name == NAME_KEY for field in fields(cls))


def _derive_name(cls: type) -> str:
    """Turn ``GoldenSpiral`` into ``golden-spiral``."""
    return _CAMEL_BOUNDARY.sub("-", cls.__name__).lower()


def _load_motifs() -> None:
    """Populate the registry, once, before anyone reads it.

    Motifs register as a side effect of their module being imported, so the
    builtin catalog has to be imported before a lookup can succeed --
    otherwise the registry reports only whatever the caller happened to
    import already, which is a maddening bug to chase.

    Imported here rather than at module scope because the motif modules
    import this one; by the time anything reads the registry, both are fully
    loaded and the cycle is harmless.

    Two packages, in order: the catalog, then the composers, which are
    motifs too and which build on the catalog.
    """
    global _motifs_loaded
    if _motifs_loaded:
        return
    # Set the flag before loading: a plugin that raises should surface its
    # error once, not on every subsequent registry call.
    _motifs_loaded = True
    importlib.import_module("geomotif.motifs")
    importlib.import_module("geomotif.compose")
    for entry_point in importlib.metadata.entry_points(group=ENTRY_POINT_GROUP):
        try:
            register_all = entry_point.load()
            register_all()
        except Exception as exc:
            raise RuntimeError(
                f"failed to load geomotif motif plugin {entry_point.name!r} "
                f"from {entry_point.value!r}: {exc}"
            ) from exc


def register(
    name: str | None = None,
    *,
    family: str | None = None,
    requires: str | None = None,
    example: Mapping[str, object] | None = None,
) -> Callable[[type[MotifT]], type[MotifT]]:
    """Register a motif class under ``name``, returning it unchanged.

    Parameters
    ----------
    name : str, optional
        Registry key. Derived from the class name in kebab-case when
        omitted, so ``GoldenSpiral`` becomes ``golden-spiral``.
    family : str, optional
        Grouping for ``geomotif list`` and the gallery, e.g. ``"spiral"``.
    requires : str, optional
        Name of an optional dependency the motif needs, e.g. ``"scipy"``.
        Listings report such motifs as unavailable rather than failing to
        import when the extra is missing.
    example : mapping, optional
        Constructor arguments producing a representative instance -- what
        the gallery renders and what the conformance suite exercises.
        Required for motifs with parameters that have no default, since
        those cannot be instantiated any other way.

    Examples
    --------
    ::

        @register("rose", family="polar", example={"k": 5})
        @dataclass(frozen=True, slots=True)
        class Rose(PolarMotif): ...
    """

    def decorate(cls: type[MotifT]) -> type[MotifT]:
        key = name if name is not None else _derive_name(cls)
        existing = _REGISTRY.get(key)
        if existing is not None and existing.cls is not cls:
            raise ValueError(
                f"motif name {key!r} is already registered to "
                f"{existing.cls.__module__}.{existing.cls.__qualname__}; "
                f"pass a different name to @register"
            )
        if _reserves_the_name_key(cls):
            raise ValueError(
                f"{cls.__qualname__} has a parameter called {NAME_KEY!r}, which is "
                f"the key spec() reserves for a design's own registered name. The "
                f"two would collide in Design.meta and the design could not be "
                f"rebuilt from it -- rename the parameter; the composers in "
                f"geomotif.compose call theirs 'unit'"
            )
        _REGISTRY[key] = _Entry(cls, family, requires, MappingProxyType(dict(example or {})))
        return cls

    return decorate


def names(*, family: str | None = None) -> tuple[str, ...]:
    """Return every registered motif name, sorted; optionally one family only."""
    _load_motifs()
    if family is None:
        return tuple(sorted(_REGISTRY))
    return tuple(sorted(k for k, v in _REGISTRY.items() if v.family == family))


def families() -> tuple[str, ...]:
    """Return every family name that has at least one motif, sorted."""
    _load_motifs()
    return tuple(sorted({v.family for v in _REGISTRY.values() if v.family is not None}))


def get(name: str) -> type[Motif]:
    """Return the motif class registered under ``name``.

    Raises
    ------
    KeyError
        If no such motif is registered. The message lists near misses, since
        a typo is far more likely than a genuinely missing motif.
    """
    _load_motifs()
    entry = _REGISTRY.get(name)
    if entry is None:
        close = [k for k in sorted(_REGISTRY) if name in k or k in name]
        hint = f"; did you mean {close[0]!r}?" if close else ""
        raise KeyError(f"no motif registered as {name!r}{hint}")
    return entry.cls


def create(name: str, /, **params: object) -> Motif:
    """Instantiate the motif registered under ``name`` with ``params``."""
    # Typed as a plain factory: the registry stores concrete motif classes
    # whose signatures differ from one another, so the call cannot be checked
    # statically here -- the dataclass constructor validates at runtime.
    factory: Callable[..., Motif] = get(name)
    return factory(**params)


def describe(name: str) -> MotifInfo:
    """Return a motif's documentation and parameter list without building it.

    Parameters come from :func:`dataclasses.fields`, which is why every
    builtin motif is a dataclass: one declaration drives the CLI flags, the
    docs, the gallery and spec round-tripping. They are listed motif-first --
    a motif's own parameters, then the ones it inherits -- which is the
    opposite of the order ``__init__`` needs and the right one to read.
    """
    _load_motifs()
    cls = get(name)
    entry = _REGISTRY[name]
    # 3.13+ dedents docstrings at compile time; 3.12 keeps the raw indentation,
    # so normalize explicitly to keep the committed artifacts byte-identical.
    doc = inspect.cleandoc(cls.__doc__ or "").strip()
    summary = doc.split("\n\n", 1)[0].replace("\n", " ").strip()

    return MotifInfo(
        name=name,
        cls=cls,
        family=entry.family,
        requires=entry.requires,
        summary=summary,
        doc=doc,
        params=_params_for(cls),
        example=entry.example,
    )


def name_for(cls: type) -> str | None:
    """Return the name ``cls`` is registered under, or ``None`` if it is not.

    Unlike the other lookups this one does not trigger a load: if an instance
    of the class exists, its module has already been imported, so anything
    the load would find is either present already or irrelevant.
    """
    for key, entry in _REGISTRY.items():
        if entry.cls is cls:
            return key
    return None


def spec(motif: SupportsBuild) -> Mapping[str, object]:
    """Return a reproducible description of ``motif``, for :attr:`Design.meta`.

    The result is the motif's registered name under ``"motif"`` plus every
    constructor parameter and its resolved value -- including any resolved
    random seed -- which is exactly what is needed to rebuild the design
    later via :func:`create`.

    Parameters
    ----------
    motif : Motif or any object with ``build()``
        The motif to describe. Usually a dataclass; anything else reports
        just its name, since there is nothing to introspect.

    Returns
    -------
    Mapping[str, object]
        Read-only, so it is safe to hand straight to :class:`Design`. An
        unregistered motif reports its class name, which is honest but not
        reconstructible -- register it to get a round-trippable spec.
    """
    name = name_for(type(motif)) or type(motif).__qualname__
    return MappingProxyType({NAME_KEY: name, **_field_values(motif)})


def _field_values(obj: object) -> dict[str, object]:
    """Return an instance's constructor field values, or ``{}`` if not a dataclass.

    Typed as ``object`` for the same reason as :func:`_params_for`: mypy
    cannot intersect :class:`Motif` with the dataclass protocol and would
    rule the body unreachable.
    """
    if not is_dataclass(obj) or isinstance(obj, type):
        return {}
    return {field.name: getattr(obj, field.name) for field in fields(obj) if field.init}


def _params_for(cls: type) -> tuple[ParamInfo, ...]:
    """Extract constructor parameters from a dataclass motif, if it is one.

    The motif's own parameters come first, then the ones it inherits, most
    recently declared first. :func:`dataclasses.fields` gives the opposite
    order -- base classes lead, because that is what the generated
    ``__init__`` needs -- and the opposite order is the wrong one to read:
    ``geomotif show rose`` would open with ``--resolution`` and a tiling's
    would open with ``--region``, burying the parameter the motif is actually
    about. Construction is unaffected; this is only how the list is read.

    Typed as a bare ``type`` rather than ``type[Motif]`` deliberately: mypy
    cannot intersect an abstract base with the dataclass protocol and rules
    the whole branch unreachable, so the narrowing has to happen where the
    class is not yet known to be a motif.
    """
    if not is_dataclass(cls):
        return ()
    declared = {field.name: field for field in fields(cls) if field.init}
    params: list[ParamInfo] = []
    for name in _declaration_order(cls, declared):
        field = declared[name]
        has_default = field.default is not MISSING or field.default_factory is not MISSING
        default = field.default if field.default is not MISSING else None
        params.append(
            ParamInfo(
                name=field.name,
                annotation=str(field.type),
                default=default,
                required=not has_default,
                description=field.metadata.get("help"),
                min=field.metadata.get("min"),
                max=field.metadata.get("max"),
                step=field.metadata.get("step"),
            )
        )
    return tuple(params)


def _declaration_order(cls: type, declared: Mapping[str, object]) -> list[str]:
    """Return field names most-derived first, in the order each class wrote them.

    A field redeclared by a subclass -- overriding an inherited default -- is
    listed where the subclass put it, since that is the class that meant it.
    """
    order: list[str] = []
    for klass in cls.__mro__:
        # get_annotations reads only the class's own annotations, not what it
        # inherited, which is exactly the split needed here. It also works
        # under both the string annotations of 3.12 and the deferred ones of
        # 3.14, where reaching into __dict__ would not.
        for name in inspect.get_annotations(klass):
            if name in declared and name not in order:
                order.append(name)
    # A field with no annotation on any class in the MRO cannot happen for a
    # dataclass, but leaving one out silently would be worse than a stray tail.
    order.extend(name for name in declared if name not in order)
    return order
