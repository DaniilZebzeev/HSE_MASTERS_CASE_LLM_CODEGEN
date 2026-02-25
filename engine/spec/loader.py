"""Load and validate a YAML or JSON DSL spec file into an ApiSpec object."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from engine.spec.schema import ApiSpec


def load_spec(path: str | Path) -> ApiSpec:
    """Parse *path* (YAML or JSON) and return a validated :class:`ApiSpec`.

    Parameters
    ----------
    path:
        Filesystem path to the DSL file.  The file extension is used to
        choose the parser; ``.json`` → JSON, anything else → YAML.

    Returns
    -------
    ApiSpec
        Fully validated specification object.

    Raises
    ------
    ValueError
        If the file cannot be parsed or fails Pydantic validation.
    FileNotFoundError
        If the file does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Spec file not found: {path}")

    raw = path.read_text(encoding="utf-8")
    try:
        if path.suffix.lower() == ".json":
            data = json.loads(raw)
        else:
            data = yaml.safe_load(raw)
    except Exception as exc:
        raise ValueError(f"Failed to parse {path}: {exc}") from exc

    return ApiSpec.model_validate(data)
