# Python Packaging in This Repo

This guide explains how Python code is organised here, and how to import it from
your own scripts without any `sys.path` hacks.

Read the [Quick Start](#quick-start) if you just want to get running. Read the rest
when you need to add a module, a dependency, or a new custom python module.

---

## The idea in one sentence

All Python code lives in **one installable package** (`src/whopy/`), which you
install **once** in editable mode — after that, `from whopy.odoo import OdooExtractor`
works from anywhere.

No `sys.path.insert(...)`. No `Path(__file__).parents[2]`. No relative-path fragility.

---

## Repository layout

```
repo/
├── pyproject.toml            # the Python manifest: package config + dependencies
├── .venv/                    # virtual environment (gitignored)
│
├── .local/                   # scratch scripts, experiments (not part of the package)
│   └── odoo-extractor/
│       └── test.py
│
└── src/
    ├── whopy/            # <- the ONLY Python package
    │   ├── __init__.py
    │   ├── base.py           # BaseExtractor ABC — the contract every extractor implements
    │   ├── core/             # shared code: exceptions, metadata, config, logging
    │   │   ├── __init__.py
    │   │   ├── exceptions.py
    │   │   └── metadata.py
    │   ├── odoo/
    │   │   ├── __init__.py
    │   │   └── odoo.py
    │   └── sap/
    │       ├── __init__.py
    │       └── sap.py
    │
    ├── db/                   # other technology — NOT Python, no __init__.py
    └── frontend/             # other technology — NOT Python, no __init__.py
```

Key point: `src/` is a **polyglot folder**, not a Python package root. Only
`src/whopy/` is Python. `src/db/` and `src/frontend/` have their own tooling
and their own manifests (`package.json`, etc.) and must **not** contain `__init__.py`.

---

## Quick start

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
```

That's it. `-e` (editable) means the install points *at your source tree* — edit a
file, and the change is live immediately. No reinstall needed.

Verify:

```bash
python -c "import whopy; print(whopy.__file__)"
```

Now, from **any** script anywhere on your machine:

```python
from whopy.odoo import OdooExtractor

e = OdooExtractor(url="...", db="...")
print(e.extract())
```

> **The one rule:** your script must run under the venv. Either activate it in your
> shell, or point your editor at `.venv/bin/python`
> (VS Code: `Ctrl+Shift+P` → *Python: Select Interpreter*).
> Almost every "ModuleNotFoundError: No module named 'whopy'" is a wrong-interpreter problem.

---

## How imports work

### From a script (outside the package)

Always use the full dotted path from the package root:

```python
from whopy.odoo import OdooExtractor
from whopy.core.exceptions import ExtractorError
```

### Between modules inside the package

`src/whopy/odoo/odoo.py` can freely import from any sibling:

```python
# Absolute — preferred. Unambiguous, survives files being moved.
from whopy.core.exceptions import AuthenticationError
from whopy.base import BaseExtractor
```

Relative imports (`from ..core.exceptions import AuthenticationError`) resolve
identically and are fine *within* a tightly-coupled subpackage — e.g. `odoo/client.py`
doing `from .models import Partner`. Across the tree, prefer absolute.

---

## `__init__.py` — what goes in it

Every Python directory needs one. **Empty is a perfectly good default.** Its only
required job is to mark the directory as a package.

Beyond that it has one genuinely useful purpose: **flattening the public API.**

```python
# src/whopy/odoo/__init__.py
from .odoo import OdooExtractor

__all__ = ["OdooExtractor"]
```

This turns the stuttering `from whopy.odoo.odoo import OdooExtractor` into a
clean `from whopy.odoo import OdooExtractor`. It also makes the internal file
layout an implementation detail — you can later split `odoo.py` into `client.py` +
`models.py` and no caller notices.

**Guidance per directory:**

| File | Contents |
|---|---|
| `whopy/__init__.py` | Empty, or `__version__ = "0.1.0"` |
| `whopy/odoo/__init__.py` | Re-export the one public class: `OdooExtractor` |
| `whopy/sap/__init__.py` | Same pattern |
| `whopy/core/__init__.py` | **Leave empty.** See below. |

Why keep `core/__init__.py` empty? Because `core/` holds several *unrelated*
concerns (exceptions, metadata, config, logging). Re-exporting them all into one
namespace invites collisions and hides where a name came from. Import by submodule
instead — it's a few more characters and always unambiguous:

```python
from whopy.core.exceptions import ExtractorError
from whopy.core.metadata import load_schema
```

Re-exporting is best reserved for a subpackage with one obvious public thing
(like `odoo/`).

### Two things to avoid

- **No heavy work in `__init__.py`.** No DB connections, no config file reads, no
  expensive imports. It runs on *any* import of the package — `import whopy.sap`
  would pay the cost of anything sitting in `whopy/__init__.py`.
- **Watch for circular imports.** Keep `core/exceptions.py` and `base.py` as *leaf*
  modules that import nothing else from the package. Arrows point one way:
  `odoo → core`, never `core → odoo`.

---

## Multiple files in a subpackage

A package is just a directory — put as many modules in it as you like. This is normal
and costs nothing at runtime, since a module is only loaded when actually imported.

```
src/whopy/core/
├── __init__.py
├── exceptions.py     # error classes
├── metadata.py       # metadata-driven integration
├── config.py
└── logging.py
```

Modules within a subpackage may import each other — `metadata.py` will likely want
`from .exceptions import ExtractorError`. That's exactly what relative imports are for.

---

## Shared exceptions

Because every whopy module will raise errors, they live in `core/`, not inside `odoo/`.
Give them a common base so callers can catch broadly or narrowly:

```python
# src/whopy/core/exceptions.py

class ExtractorError(Exception):
    """Base for all extractor failures."""

class ConnectionFailed(ExtractorError): ...
class AuthenticationError(ExtractorError): ...
class ExtractionFailed(ExtractorError): ...
```

The payoff: a script can catch everything from any system with one clause.

```python
from whopy.core.exceptions import ExtractorError

try:
    data = e.extract()
except ExtractorError as err:      # catches Odoo, SAP, anything
    log.error("extraction failed: %s", err)
```

---

## Adding a new extractor

1. `mkdir src/whopy/<system>/` and add `__init__.py` + `<system>.py`.
2. Subclass `BaseExtractor` from `whopy/base.py` — implement `connect()` and `extract()`.
3. Re-export the class in `<system>/__init__.py`.
4. Raise the shared exceptions from `whopy.core.exceptions`.

No packaging changes. No import changes anywhere else. It just works.

---

## Dependencies

**All Python dependencies live in `pyproject.toml`.** There is no `requirements.txt`.
`pip install -e .` installs the package *and* everything it needs, in one command.

```toml
[project]
name = "whopy"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "requests>=2.31,<3",
    "jsonschema>=4.21,<5",
    "prettytable>=3.9,<4",
    "pandas>=2.2,<3",
    "pydantic>=2.8,<3",      # type-hint validation
    "paramiko>=3,<4",        # SFTP
    "unidecode>=1.3",        # normalise names
    "jinja2>=3.1.4,<4",      # metadata command validation
    "chardet>=5",
    "openpyxl>=3.1",         # xlsx
]

[project.optional-dependencies]
dev = ["pytest>=8", "ruff", "mypy"]

[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
include = ["whopy*"]     # never wander into src/db or src/frontend
```

Install dev tooling with `pip install -e ".[dev]"`.

### Ranges, not hard pins

Note `>=2.31,<3` rather than `==2.31.0`. `whopy` is a **library** — something
other code imports. Hard `==` pins cause resolution conflicts the moment a consumer
needs a slightly different version. Reproducibility for *deployments* comes from a
**lockfile** (`pip freeze > requirements.lock`, or `uv lock`), not from the manifest.

---

## Promoting a script to a command

When a `.local/` script graduates from a scratch test into a real entry point, declare
it rather than shipping a loose file:

```toml
[project.scripts]
extract-odoo = "whopy.odoo.cli:main"
```

After `pip install -e .`, you simply type `extract-odoo` in the shell.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'whopy'`**
The venv isn't active, or your editor is pointing at the system Python.
Check with `which python` — it should be inside `.venv/`.

**Changes to my code aren't taking effect**
You installed without `-e`. Reinstall: `pip install -e .`

**`ImportError: cannot import name X (most likely due to a circular import)`**
Two modules import each other. Make `core/` and `base.py` leaf modules that import
nothing from the rest of the package.

**setuptools complains about multiple top-level packages**
A stray `.py` file appeared under `src/db/` or `src/frontend/`. The
`include = ["whopy*"]` line should prevent this — confirm it's present.

---

## Why not just use `sys.path`?

You'll see this pattern in a lot of scripts:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
```

It works, and it's fine for a five-minute throwaway. But it doesn't scale: every new
script, test, and cron job needs its own copy of the incantation; the `parents[2]`
breaks the moment a file moves; and `pytest` will import things differently from
your shell. The editable install solves all of it once, at the repo level.
