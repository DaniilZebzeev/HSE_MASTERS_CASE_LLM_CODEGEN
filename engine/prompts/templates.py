"""Prompt templates for the FastAPI code-generation pipeline."""

from __future__ import annotations

from engine.spec.schema import ApiSpec

# ---------------------------------------------------------------------------
# System prompt shared by all generation tasks
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert Python developer specialising in FastAPI.
Your task is to generate clean, production-quality Python source files.
Follow these rules:
- Use Pydantic v2 models (from pydantic import BaseModel).
- Use Python 3.11+ type hints (e.g. str | None, list[str]).
- Do NOT include markdown code fences (``` … ```) in your output.
- Output ONLY valid Python source code, nothing else.
- Keep imports sorted (isort compatible).
- Line length ≤ 88 characters (black compatible).
"""

# ---------------------------------------------------------------------------
# Individual file prompts
# ---------------------------------------------------------------------------


def models_prompt(spec: ApiSpec) -> str:
    """Return a prompt that asks the LLM to generate ``models.py``."""
    model_descriptions = "\n".join(
        f"  - {m.name}: "
        + ", ".join(
            f"{f.name}: {f.type}"
            + (" (optional)" if f.optional else "")
            + (f" = {f.default!r}" if f.default is not None else "")
            for f in m.fields
        )
        for m in spec.models
    )
    return f"""\
Generate a file called `models.py` for the FastAPI project "{spec.name}".

Data models to define (use Pydantic BaseModel):
{model_descriptions}

Return only the complete Python source for `models.py`.
"""


def router_prompt(spec: ApiSpec) -> str:
    """Return a prompt that asks the LLM to generate ``routers/api.py``."""
    endpoint_descriptions = "\n".join(
        f"  - {ep.method} {ep.path}"
        + (f" — {ep.summary}" if ep.summary else "")
        + (f" [request body: {ep.request_body}]" if ep.request_body else "")
        + (f" [response: {ep.response_model}]" if ep.response_model else "")
        for ep in spec.endpoints
    )
    model_names = ", ".join(m.name for m in spec.models)
    return f"""\
Generate a FastAPI router file (`routers/api.py`) for the project "{spec.name}".

Import models from `..models` (relative import).
Available models: {model_names}

Endpoints to implement:
{endpoint_descriptions}

Use `APIRouter` from FastAPI.  Include a realistic stub implementation for
each endpoint (e.g. return an empty list, create a new object, etc.).
Return only the complete Python source for `routers/api.py`.
"""


def main_prompt(spec: ApiSpec) -> str:
    """Return a prompt that asks the LLM to generate ``main.py``."""
    return f"""\
Generate `main.py` for the FastAPI project "{spec.name}" (version {spec.version}).

Requirements:
- Create a FastAPI app with title "{spec.name}" and version "{spec.version}".
- Description: "{spec.description}".
- Include the router from `routers.api` (use `app.include_router`).
- Add a simple `/health` GET endpoint that returns {{"status": "ok"}}.
- At the bottom add: `if __name__ == "__main__": uvicorn.run(app, host="0.0.0.0", port=8000)`

Return only the complete Python source for `main.py`.
"""


def tests_prompt(spec: ApiSpec) -> str:
    """Return a prompt that asks the LLM to generate ``tests/test_api.py``."""
    endpoint_paths = "\n".join(f"  - {ep.method} {ep.path}" for ep in spec.endpoints)
    return f"""\
Generate `tests/test_api.py` for the FastAPI project "{spec.name}".

Use `pytest` and `httpx.AsyncClient` with `transport=ASGITransport(app=app)`.
Import `app` from `main`.

Write one test per endpoint:
{endpoint_paths}
Also test GET /health → 200.

Return only the complete Python source for `tests/test_api.py`.
"""


def repair_prompt(file_name: str, source: str, diagnostics: str) -> str:
    """Return a prompt asking the LLM to repair *source* given *diagnostics*.

    The LLM is asked to respond with a unified diff (``diff -u`` format) so
    that the repair-loop can apply it deterministically.
    """
    return f"""\
The file `{file_name}` has the following linting / test errors:

{diagnostics}

Current source of `{file_name}`:
```python
{source}
```

Reply with a unified diff (diff -u format, no surrounding explanation) that
fixes all reported errors.  The diff must apply cleanly with `patch -p0`.
Do NOT output the full file — output only the diff.
"""
