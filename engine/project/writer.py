"""Write generated source files to an output directory.

The writer also creates boilerplate files (``__init__.py``, ``requirements.txt``,
``pyproject.toml``) that are not LLM-generated but are needed for the
generated project to be importable and testable.
"""

from __future__ import annotations

from pathlib import Path

from engine.spec.schema import ApiSpec

# ---------------------------------------------------------------------------
# Boilerplate templates (not LLM-generated)
# ---------------------------------------------------------------------------

_REQUIREMENTS_TMPL = """\
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
pydantic>=2.6.0
httpx>=0.27.0
pytest>=8.1.0
pytest-asyncio>=0.23.5
"""

_PYPROJECT_TMPL = """\
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "{name}"
version = "{version}"
description = "{description}"
requires-python = ">=3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "-v --tb=short"

[tool.black]
line-length = 88

[tool.ruff]
line-length = 88
"""

_INIT_PY = ""  # empty __init__.py


def write_project(
    spec: ApiSpec,
    generated_files: dict[str, str],
    output_dir: str | Path,
) -> Path:
    """Write all generated files plus boilerplate to *output_dir*.

    Parameters
    ----------
    spec:
        Validated DSL specification (used for boilerplate templating).
    generated_files:
        Mapping of *relative path* → *source code* produced by the LLM.
    output_dir:
        Root directory for the generated project.  Created if absent.

    Returns
    -------
    Path
        Absolute path to the generated project root.
    """
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)

    # --- LLM-generated files ------------------------------------------------
    for rel_path, source in generated_files.items():
        dest = root / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(source, encoding="utf-8")

    # --- Boilerplate ---------------------------------------------------------
    _ensure_file(root / "requirements.txt", _REQUIREMENTS_TMPL)
    _ensure_file(
        root / "pyproject.toml",
        _PYPROJECT_TMPL.format(
            name=spec.name,
            version=spec.version,
            description=spec.description,
        ),
    )
    # __init__.py files for importability
    for pkg_dir in [root, root / "routers", root / "tests"]:
        if pkg_dir.is_dir():
            _ensure_file(pkg_dir / "__init__.py", _INIT_PY)

    return root


def _ensure_file(path: Path, content: str) -> None:
    """Write *content* to *path* only if the file does not already exist."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
