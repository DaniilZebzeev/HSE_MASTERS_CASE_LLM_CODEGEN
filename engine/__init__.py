"""
engine — core pipeline for DSL → FastAPI code generation.

Sub-packages
------------
spec      Load & validate YAML/JSON DSL specs (Pydantic models).
planner   Break a validated spec into an ordered list of generation tasks.
llm       Thin async client around the local Ollama HTTP API.
project   Write generated source files to an output directory.
verify    Run black / ruff / pytest and return pass/fail + diagnostics.
metrics   Collect and persist generation-run statistics.
prompts   Prompt-template library used by the planner.
"""
