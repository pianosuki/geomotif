# Security policy

## Supported versions

The latest release on the 1.x line receives security fixes.

## Reporting a vulnerability

Please report privately rather than opening a public issue: use
[GitHub's private vulnerability reporting](https://github.com/pianosuki/geomotif/security/advisories/new),
or email pianosuki@protonmail.com.

Include what you did, what happened, and what you expected. A minimal
reproduction is worth more than anything else you can send.

You should get an acknowledgement within a week. If a fix is warranted it will
be released on the 1.x line with an advisory crediting you, unless you would
rather not be named.

## What is in scope

The core library has no runtime dependencies, reads no network and executes no
code it was not given, so the attack surface is small and specific. Two places
are worth pointing at:

**Loading a spec file.** `load_spec` reads JSON that names a motif and,
sometimes, a value type. It deliberately will **not** import a module the file
names: `$type` resolution is restricted to `geomotif` itself plus packages that
already declare a `geomotif.motifs` entry point on the machine doing the
loading, and the resolved object has to be a dataclass class. A spec that could
make a process import or call something outside that set is a vulnerability,
and worth reporting.

**Building an untrusted motif.** A parameter that drives a recursion depth, a
tile count or a sample count can be given a value that makes a build allocate
without bound. If you accept spec files or motif parameters from users, bound
those parameters yourself — that is your input validation, not the library's.
A build that consumes disproportionate resources for *small* parameters is a
bug worth reporting.

## What is out of scope

- Rendering an exported SVG or DXF in some other program. geomotif writes
  coordinates and nothing executable; what a viewer does with a file is that
  viewer's concern.
- Denial of service from parameters you chose yourself. Asking for a fractal at
  depth 40 does what you asked.
- The optional `plot` and `scipy` extras' own dependencies. Report those to
  matplotlib and scipy.
