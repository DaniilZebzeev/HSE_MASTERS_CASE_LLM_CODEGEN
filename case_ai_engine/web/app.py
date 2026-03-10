"""FastAPI-РїСЂРёР»РѕР¶РµРЅРёРµ: job-based API + СЂР°Р·РґР°С‡Р° СЃС‚Р°С‚РёРєРё."""

from __future__ import annotations

import json
import re
import threading
import uuid
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from engine.llm.ollama_client import OllamaClient
from engine.orchestrator import run_pipeline
from engine.prompts.builder import PromptBuilder

_prompt_builder = PromptBuilder()

# ---------------------------------------------------------------------------
# РљРѕРЅСЃС‚Р°РЅС‚С‹
# ---------------------------------------------------------------------------

OUTPUTS_DIR: Path = Path(__file__).parent.parent / "outputs"
STATIC_DIR: Path = Path(__file__).parent / "static"
CHAT_META_FILENAME = "_chat_meta.json"
TITLE_MAX_CHARS = 48

# ---------------------------------------------------------------------------
# РЎРѕСЃС‚РѕСЏРЅРёРµ Р·Р°РґР°С‡ (in-memory)
# ---------------------------------------------------------------------------

jobs: dict[str, dict[str, Any]] = {}

# ---------------------------------------------------------------------------
# Pydantic-РјРѕРґРµР»Рё Р·Р°РїСЂРѕСЃРѕРІ / РѕС‚РІРµС‚РѕРІ
# ---------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    """РџР°СЂР°РјРµС‚СЂС‹ Р·Р°РїСѓСЃРєР° РіРµРЅРµСЂР°С†РёРё."""

    spec_yaml: str
    model: str = "qwen3-coder:30b"
    max_iters: int = 3


class JobStatus(BaseModel):
    """РЎС‚Р°С‚СѓСЃ Р·Р°РґР°С‡Рё."""

    job_id: str
    status: str  # "pending" | "running" | "done" | "error"
    run_id: str | None = None
    title: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# РџСЂРёР»РѕР¶РµРЅРёРµ
# ---------------------------------------------------------------------------

app = FastAPI(title="CASE AI Engine", version="0.1.0")

# РЈРґР°Р»СЏРµРј markdown-РѕР±С‘СЂС‚РєСѓ ```yaml ... ``` РїРµСЂРµРґ YAML-РїР°СЂСЃРёРЅРіРѕРј.
_CODE_FENCE_RE = re.compile(
    r"^\s*```(?:yaml|yml|json)?\s*\n(?P<body>[\s\S]*?)\n```\s*$",
    flags=re.IGNORECASE,
)


def _strip_code_fence(text: str) -> str:
    """Р’РµСЂРЅСѓС‚СЊ С‚РµРєСЃС‚ Р±РµР· markdown code fences, РµСЃР»Рё РѕРЅРё РµСЃС‚СЊ."""
    candidate = text.strip()
    match = _CODE_FENCE_RE.match(candidate)
    if not match:
        return candidate
    return match.group("body").strip()


def _parse_spec_dict(text: str) -> dict[str, Any] | None:
    """Р Р°СЃРїР°СЂСЃРёС‚СЊ YAML/JSON-СЃРїРµС†РёС„РёРєР°С†РёСЋ Рё РІРµСЂРЅСѓС‚СЊ СЃР»РѕРІР°СЂСЊ РёР»Рё None."""
    candidate = _strip_code_fence(text)
    try:
        parsed = yaml.safe_load(candidate)
    except yaml.YAMLError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _normalize_title(text: str, max_len: int = TITLE_MAX_CHARS) -> str:
    """Normalize and truncate title text."""
    collapsed = re.sub(r"\s+", " ", text.strip())
    if not collapsed:
        return "New chat"
    return collapsed[: max_len - 3].rstrip() + "..." if len(collapsed) > max_len else collapsed


def _title_from_spec(spec_dict: dict[str, Any]) -> str | None:
    """Build title from parsed specification when possible."""
    service = spec_dict.get("service")
    if not isinstance(service, dict):
        return None
    name = service.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    return _normalize_title(name.replace("_", " ").replace("-", " "))


def _derive_chat_title(user_text: str, spec_dict: dict[str, Any] | None) -> str:
    """Build chat title from context with language-aware priority."""
    plain = _strip_code_fence(user_text)
    text_title: str | None = None
    for line in plain.splitlines():
        cleaned = re.sub(r"^[#>\-\*\d\.\)\s]+", "", line).strip()
        if cleaned:
            text_title = _normalize_title(cleaned)
            break

    spec_title = _title_from_spec(spec_dict) if spec_dict else None
    has_cyrillic = re.search(r"[А-Яа-яЁё]", plain) is not None
    has_latin = re.search(r"[A-Za-z]", plain) is not None

    if has_cyrillic:
        return text_title or spec_title or "New chat"
    if has_latin:
        return spec_title or text_title or "New chat"
    return spec_title or text_title or "New chat"

def _run_meta_path(run_dir: Path) -> Path:
    return run_dir / CHAT_META_FILENAME


def _write_run_meta(run_dir: Path, title: str) -> None:
    """Persist chat metadata for a generated run."""
    data = {"title": _normalize_title(title)}
    _run_meta_path(run_dir).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _read_run_title(run_dir: Path) -> str | None:
    """Read chat title for run if metadata exists."""
    meta_path = _run_meta_path(run_dir)
    if not meta_path.is_file():
        return None
    try:
        raw = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    title = raw.get("title")
    if not isinstance(title, str):
        return None
    return _normalize_title(title)


# ---------------------------------------------------------------------------
# API-СЌРЅРґРїРѕРёРЅС‚С‹
# ---------------------------------------------------------------------------


@app.post("/api/jobs/generate", response_model=JobStatus, status_code=202)
def create_job(req: GenerateRequest) -> JobStatus:
    """Р—Р°РїСѓСЃС‚РёС‚СЊ Р·Р°РґР°С‡Сѓ РіРµРЅРµСЂР°С†РёРё РєРѕРґР° РІ С„РѕРЅРѕРІРѕРј РїРѕС‚РѕРєРµ."""
    job_id = uuid.uuid4().hex[:12]

    # Р’СЂРµРјРµРЅРЅС‹Р№ С„Р°Р№Р» РґР»СЏ СЃРїРµС†РёС„РёРєР°С†РёРё (Р·Р°РїРѕР»РЅСЏРµС‚СЃСЏ РІ РІРѕСЂРєРµСЂРµ)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    spec_file = OUTPUTS_DIR / f"_spec_{job_id}.yaml"
    input_spec_dict = _parse_spec_dict(req.spec_yaml)
    initial_title = _derive_chat_title(req.spec_yaml, input_spec_dict)

    jobs[job_id] = {
        "status": "pending",
        "run_id": None,
        "title": initial_title,
        "error": None,
        "spec_yaml": None,
    }

    def _worker() -> None:
        jobs[job_id]["status"] = "running"
        try:
            # Р•СЃР»Рё РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ РІРІС‘Р» РЅРµ YAML-СЃР»РѕРІР°СЂСЊ вЂ” РєРѕРЅРІРµСЂС‚РёСЂСѓРµРј С‡РµСЂРµР· LLM.
            spec_text = _strip_code_fence(req.spec_yaml)
            spec_dict = _parse_spec_dict(spec_text)
            if spec_dict is None:
                with OllamaClient(model=req.model) as client:
                    prompt = _prompt_builder.render_nl_to_spec(spec_text)
                    spec_text = _strip_code_fence(client.generate(prompt))
                spec_dict = _parse_spec_dict(spec_text)
                if spec_dict is None:
                    raise ValueError(
                        "РќРµ СѓРґР°Р»РѕСЃСЊ РїСЂРµРѕР±СЂР°Р·РѕРІР°С‚СЊ Р·Р°РїСЂРѕСЃ РІ YAML-СЃРїРµС†РёС„РёРєР°С†РёСЋ. "
                        "РћРїРёС€РёС‚Рµ С‚СЂРµР±РѕРІР°РЅРёСЏ Рє API РѕР±С‹С‡РЅС‹Рј С‚РµРєСЃС‚РѕРј Р±РµР· markdown-Р±Р»РѕРєРѕРІ."
                    )
                jobs[job_id]["spec_yaml"] = spec_text
            jobs[job_id]["title"] = _derive_chat_title(req.spec_yaml, spec_dict)

            # РџРёС€РµРј РЅРѕСЂРјР°Р»РёР·РѕРІР°РЅРЅС‹Р№ YAML РґР»СЏ СЃР»РµРґСѓСЋС‰РµРіРѕ С€Р°РіР° РїР°Р№РїР»Р°Р№РЅР°.
            spec_file.write_text(
                yaml.safe_dump(spec_dict, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )

            run_id = run_pipeline(
                spec_path=spec_file,
                model=req.model,
                output_dir=OUTPUTS_DIR,
                max_iters=req.max_iters,
            )
            _write_run_meta(
                OUTPUTS_DIR / run_id,
                str(jobs[job_id].get("title") or initial_title),
            )
            jobs[job_id]["status"] = "done"
            jobs[job_id]["run_id"] = run_id
        except Exception as exc:  # noqa: BLE001
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"] = str(exc)
        finally:
            spec_file.unlink(missing_ok=True)

    threading.Thread(target=_worker, daemon=True).start()

    return JobStatus(job_id=job_id, status="pending", title=initial_title)


@app.get("/api/jobs/{job_id}", response_model=JobStatus)
def get_job(job_id: str) -> JobStatus:
    """РџРѕР»СѓС‡РёС‚СЊ СЃС‚Р°С‚СѓСЃ Р·Р°РґР°С‡Рё."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Р—Р°РґР°С‡Р° РЅРµ РЅР°Р№РґРµРЅР°")
    j = jobs[job_id]
    return JobStatus(
        job_id=job_id,
        status=j["status"],
        run_id=j.get("run_id"),
        title=j.get("title"),
        error=j.get("error"),
    )


@app.get("/api/runs")
def list_runs() -> JSONResponse:
    """РЎРїРёСЃРѕРє РІСЃРµС… run_id (РїРѕРґРєР°С‚Р°Р»РѕРіРѕРІ outputs)."""
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    run_dirs = sorted((d for d in OUTPUTS_DIR.iterdir() if d.is_dir()), reverse=True)
    runs = [d.name for d in run_dirs]
    titles: dict[str, str] = {}
    for run_dir in run_dirs:
        title = _read_run_title(run_dir)
        if title:
            titles[run_dir.name] = title
    return JSONResponse({"runs": runs, "titles": titles})


@app.get("/api/runs/{run_id}/files")
def list_files(run_id: str) -> JSONResponse:
    """РЎРїРёСЃРѕРє С„Р°Р№Р»РѕРІ РІРЅСѓС‚СЂРё run_id."""
    run_dir = _resolve_run_dir(run_id)
    files = sorted(
        str(p.relative_to(run_dir)).replace("\\", "/")
        for p in run_dir.rglob("*")
        if p.is_file()
    )
    return JSONResponse({"files": files})


@app.get("/api/runs/{run_id}/file")
def get_file(run_id: str, path: str) -> JSONResponse:
    """РЎРѕРґРµСЂР¶РёРјРѕРµ РѕРґРЅРѕРіРѕ С„Р°Р№Р»Р° РІРЅСѓС‚СЂРё run_id."""
    run_dir = _resolve_run_dir(run_id)
    file_path = _safe_path(run_dir, path)
    content = file_path.read_text(encoding="utf-8", errors="replace")
    return JSONResponse({"path": path, "content": content})


@app.get("/api/runs/{run_id}/download")
def download_run(run_id: str) -> StreamingResponse:
    """РЎРєР°С‡Р°С‚СЊ РІСЃРµ С„Р°Р№Р»С‹ run_id РєР°Рє ZIP-Р°СЂС…РёРІ."""
    run_dir = _resolve_run_dir(run_id)
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in run_dir.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(run_dir))
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{run_id}.zip"'},
    )


# ---------------------------------------------------------------------------
# Р’СЃРїРѕРјРѕРіР°С‚РµР»СЊРЅС‹Рµ С„СѓРЅРєС†РёРё
# ---------------------------------------------------------------------------


def _resolve_run_dir(run_id: str) -> Path:
    """Р’РµСЂРЅСѓС‚СЊ Path Рє run_dir РёР»Рё РїРѕРґРЅСЏС‚СЊ 404."""
    # РќРµ РґРѕРїСѓСЃРєР°РµРј path-traversal РІ run_id
    if "/" in run_id or "\\" in run_id or ".." in run_id:
        raise HTTPException(status_code=400, detail="РќРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ run_id")
    run_dir = OUTPUTS_DIR / run_id
    if not run_dir.is_dir():
        raise HTTPException(status_code=404, detail="Run РЅРµ РЅР°Р№РґРµРЅ")
    return run_dir


def _safe_path(run_dir: Path, rel: str) -> Path:
    """Р Р°Р·СЂРµС€РёС‚СЊ РѕС‚РЅРѕСЃРёС‚РµР»СЊРЅС‹Р№ РїСѓС‚СЊ РІРЅСѓС‚СЂРё run_dir (Р·Р°С‰РёС‚Р° РѕС‚ path-traversal)."""
    candidate = (run_dir / rel).resolve()
    try:
        candidate.relative_to(run_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="РќРµРґРѕРїСѓСЃС‚РёРјС‹Р№ РїСѓС‚СЊ")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="Р¤Р°Р№Р» РЅРµ РЅР°Р№РґРµРЅ")
    return candidate


# ---------------------------------------------------------------------------
# Р Р°Р·РґР°С‡Р° СЃС‚Р°С‚РёРєРё (РјРѕРЅС‚РёСЂСѓРµС‚СЃСЏ РїРѕСЃР»РµРґРЅРµР№)
# ---------------------------------------------------------------------------

app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
