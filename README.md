# HSE_MASTERS_CASE_LLM_CODEGEN

Master's thesis (HSE): DSL-driven CASE module for generating Python/FastAPI projects using a local LLM (Ollama) with automated verification and repair-loop.

---

## Быстрый старт

### 1. Требования

- Python 3.11+
- [Ollama](https://ollama.ai/) — локальный инференс LLM

### 2. Установка зависимостей

```bash
cd case_ai_engine
pip install httpx pydantic pyyaml jinja2 typer rich fastapi "uvicorn[standard]" aiofiles
pip install black ruff pytest          # инструменты разработки
```

### 3. Запуск Ollama

```bash
ollama pull codellama:7b-instruct      # один раз скачать модель
ollama serve                           # держать в отдельном терминале
```

---

## CLI: генерация по спецификации

```bash
cd case_ai_engine
python cli.py generate --spec examples/spec_min.yaml --model codellama:7b-instruct
```

Опции:

| Флаг | По умолчанию | Описание |
|---|---|---|
| `--spec` | — | Путь к YAML-спецификации |
| `--model` | `codellama:7b-instruct` | Имя модели Ollama |
| `--output` | `outputs` | Каталог для результатов |
| `--max-iters` | `3` | Макс. итераций repair-loop |
| `--verbose` | `False` | Подробный лог |

Результат появляется в `outputs/<run_id>/`.

---

## Web UI: ChatGPT-подобный интерфейс

### Запуск сервера

```bash
cd case_ai_engine
uvicorn web.app:app --reload --port 8000
```

Открыть в браузере: [http://localhost:8000](http://localhost:8000)

### Интерфейс

- **Левая панель** — история запусков (сохраняется в localStorage)
- **Центр** — чат: вставьте YAML-спецификацию, нажмите «Генерировать»
- **Правая панель** — просмотр сгенерированных файлов, скачивание ZIP

### API-эндпоинты

| Метод | Путь | Описание |
|---|---|---|
| `POST` | `/api/jobs/generate` | Запустить генерацию (возвращает `job_id`) |
| `GET` | `/api/jobs/{job_id}` | Статус задачи (`pending/running/done/error`) |
| `GET` | `/api/runs` | Список всех run_id |
| `GET` | `/api/runs/{run_id}/files` | Список файлов внутри run |
| `GET` | `/api/runs/{run_id}/file?path=…` | Содержимое файла |
| `GET` | `/api/runs/{run_id}/download` | Скачать ZIP-архив |

---

## Пример спецификации

```yaml
service:
  name: my_api
  stack: python-fastapi

entities:
  - name: Item
    fields:
      - name: id
        type: int
        required: true
      - name: title
        type: str
        required: true

endpoints:
  - name: health
    method: GET
    path: /health
    responses:
      - status_code: 200

generation:
  tests: true
```

---

## Проверки и тесты

```bash
cd case_ai_engine
python -m black --check .
python -m ruff check .
python -m pytest -q
```

---

## Структура проекта

```
case_ai_engine/
  cli.py                    # CLI-интерфейс (Typer)
  web/
    app.py                  # FastAPI web-приложение
    static/                 # HTML/CSS/JS фронтенд
  engine/
    orchestrator.py         # Главный конвейер
    planner.py              # Планировщик файлов
    prompts/                # Jinja2-шаблоны промптов
    llm/ollama_client.py    # HTTP-клиент Ollama
    spec/                   # DSL-модели и валидация
    project/                # Запись файлов, применение diff
    verify/                 # black/ruff/pytest верификация
    metrics/                # Метрики и отчёты
  examples/spec_min.yaml    # Минимальный пример
  outputs/                  # Результаты генерации
```
