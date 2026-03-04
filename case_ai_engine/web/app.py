"""FastAPI-приложение: job-based API + раздача статики."""

from __future__ import annotations

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
# Константы
# ---------------------------------------------------------------------------

OUTPUTS_DIR: Path = Path(__file__).parent.parent / "outputs"
STATIC_DIR: Path = Path(__file__).parent / "static"

# ---------------------------------------------------------------------------
# Состояние задач (in-memory)
# ---------------------------------------------------------------------------

jobs: dict[str, dict[str, Any]] = {}

# ---------------------------------------------------------------------------
# Pydantic-модели запросов / ответов
# ---------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    """Параметры запуска генерации."""

    spec_yaml: str
    model: str = "codellama:7b-instruct"
    max_iters: int = 3


class JobStatus(BaseModel):
    """Статус задачи."""

    job_id: str
    status: str  # "pending" | "running" | "done" | "error"
    run_id: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Приложение
# ---------------------------------------------------------------------------

app = FastAPI(title="CASE AI Engine", version="0.1.0")


# ---------------------------------------------------------------------------
# API-эндпоинты
# ---------------------------------------------------------------------------


@app.post("/api/jobs/generate", response_model=JobStatus, status_code=202)
def create_job(req: GenerateRequest) -> JobStatus:
    """Запустить задачу генерации кода в фоновом потоке."""
    job_id = uuid.uuid4().hex[:12]

    # Временный файл для спецификации (заполняется в воркере)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    spec_file = OUTPUTS_DIR / f"_spec_{job_id}.yaml"

    jobs[job_id] = {
        "status": "pending",
        "run_id": None,
        "error": None,
        "spec_yaml": None,
    }

    def _worker() -> None:
        jobs[job_id]["status"] = "running"
        try:
            # Если пользователь ввёл не YAML-словарь — конвертируем через LLM
            spec_text = req.spec_yaml
            try:
                parsed = yaml.safe_load(spec_text)
                is_dict = isinstance(parsed, dict)
            except yaml.YAMLError:
                is_dict = False

            if not is_dict:
                with OllamaClient(model=req.model) as client:
                    prompt = _prompt_builder.render_nl_to_spec(spec_text)
                    spec_text = client.generate(prompt)
                jobs[job_id]["spec_yaml"] = spec_text

            spec_file.write_text(spec_text, encoding="utf-8")

            run_id = run_pipeline(
                spec_path=spec_file,
                model=req.model,
                output_dir=OUTPUTS_DIR,
                max_iters=req.max_iters,
            )
            jobs[job_id]["status"] = "done"
            jobs[job_id]["run_id"] = run_id
        except Exception as exc:  # noqa: BLE001
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"] = str(exc)
        finally:
            spec_file.unlink(missing_ok=True)

    threading.Thread(target=_worker, daemon=True).start()

    return JobStatus(job_id=job_id, status="pending")


@app.get("/api/jobs/{job_id}", response_model=JobStatus)
def get_job(job_id: str) -> JobStatus:
    """Получить статус задачи."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    j = jobs[job_id]
    return JobStatus(
        job_id=job_id,
        status=j["status"],
        run_id=j.get("run_id"),
        error=j.get("error"),
    )


@app.get("/api/runs")
def list_runs() -> JSONResponse:
    """Список всех run_id (подкаталогов outputs)."""
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    runs = sorted(
        (d.name for d in OUTPUTS_DIR.iterdir() if d.is_dir()),
        reverse=True,
    )
    return JSONResponse({"runs": runs})


@app.get("/api/runs/{run_id}/files")
def list_files(run_id: str) -> JSONResponse:
    """Список файлов внутри run_id."""
    run_dir = _resolve_run_dir(run_id)
    files = sorted(
        str(p.relative_to(run_dir)).replace("\\", "/")
        for p in run_dir.rglob("*")
        if p.is_file()
    )
    return JSONResponse({"files": files})


@app.get("/api/runs/{run_id}/file")
def get_file(run_id: str, path: str) -> JSONResponse:
    """Содержимое одного файла внутри run_id."""
    run_dir = _resolve_run_dir(run_id)
    file_path = _safe_path(run_dir, path)
    content = file_path.read_text(encoding="utf-8", errors="replace")
    return JSONResponse({"path": path, "content": content})


@app.get("/api/runs/{run_id}/download")
def download_run(run_id: str) -> StreamingResponse:
    """Скачать все файлы run_id как ZIP-архив."""
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
# Вспомогательные функции
# ---------------------------------------------------------------------------


def _resolve_run_dir(run_id: str) -> Path:
    """Вернуть Path к run_dir или поднять 404."""
    # Не допускаем path-traversal в run_id
    if "/" in run_id or "\\" in run_id or ".." in run_id:
        raise HTTPException(status_code=400, detail="Некорректный run_id")
    run_dir = OUTPUTS_DIR / run_id
    if not run_dir.is_dir():
        raise HTTPException(status_code=404, detail="Run не найден")
    return run_dir


def _safe_path(run_dir: Path, rel: str) -> Path:
    """Разрешить относительный путь внутри run_dir (защита от path-traversal)."""
    candidate = (run_dir / rel).resolve()
    try:
        candidate.relative_to(run_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Недопустимый путь")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="Файл не найден")
    return candidate


# ---------------------------------------------------------------------------
# Раздача статики (монтируется последней)
# ---------------------------------------------------------------------------

app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
