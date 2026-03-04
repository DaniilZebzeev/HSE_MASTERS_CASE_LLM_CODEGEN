/* ===== CASE AI Engine — клиентская логика ===== */
"use strict";

const POLL_MS = 2000;
const LS_KEY = "case_runs_history";

// ───────────────────────────────────────────────
// DOM-ссылки
// ───────────────────────────────────────────────
const runsList    = document.getElementById("runs-list");
const messages    = document.getElementById("messages");
const inputForm   = document.getElementById("input-form");
const specInput   = document.getElementById("spec-input");
const modelInput  = document.getElementById("model-input");
const itersInput  = document.getElementById("iters-input");
const sendBtn     = document.getElementById("send-btn");
const newBtn      = document.getElementById("new-btn");
const fileList    = document.getElementById("file-list");
const fileCode    = document.getElementById("file-code");
const viewerTitle = document.getElementById("viewer-title");
const downloadBtn = document.getElementById("download-btn");

// ───────────────────────────────────────────────
// История (localStorage)
// ───────────────────────────────────────────────
function loadHistory() {
  try { return JSON.parse(localStorage.getItem(LS_KEY) || "[]"); }
  catch { return []; }
}

function saveHistory(history) {
  localStorage.setItem(LS_KEY, JSON.stringify(history));
}

function addToHistory(runId) {
  const h = loadHistory().filter(r => r !== runId);
  h.unshift(runId);
  saveHistory(h.slice(0, 50));
}

// ───────────────────────────────────────────────
// Список запусков (боковая панель)
// ───────────────────────────────────────────────
async function refreshSidebar() {
  let serverRuns = [];
  try {
    const res = await fetch("/api/runs");
    serverRuns = (await res.json()).runs || [];
  } catch { /* сервер недоступен — показываем только локальную историю */ }

  // Объединяем: серверные + исторические (могут не совпадать при перезапуске)
  const hist = loadHistory();
  const all = [...new Set([...serverRuns, ...hist])];

  runsList.innerHTML = "";
  all.forEach(runId => {
    const li = document.createElement("li");
    li.textContent = runId;
    li.dataset.runId = runId;
    li.title = runId;
    li.addEventListener("click", () => openRun(runId, li));
    runsList.appendChild(li);
  });
}

// ───────────────────────────────────────────────
// Просмотр файлов
// ───────────────────────────────────────────────
async function openRun(runId, liEl) {
  // Подсветка активного элемента
  runsList.querySelectorAll("li").forEach(l => l.classList.remove("active"));
  if (liEl) liEl.classList.add("active");

  viewerTitle.textContent = runId;
  downloadBtn.style.display = "inline-block";
  downloadBtn.onclick = () => { window.location = `/api/runs/${runId}/download`; };

  fileList.innerHTML = "";
  fileCode.textContent = "";

  try {
    const res = await fetch(`/api/runs/${runId}/files`);
    if (!res.ok) { fileCode.textContent = "Файлы не найдены."; return; }
    const { files } = await res.json();

    files.forEach(fp => {
      const li = document.createElement("li");
      li.textContent = fp;
      li.title = fp;
      li.addEventListener("click", () => openFile(runId, fp, li));
      fileList.appendChild(li);
    });

    // Автоматически открываем первый файл
    if (files.length > 0) {
      openFile(runId, files[0], fileList.firstChild);
    }
  } catch {
    fileCode.textContent = "Ошибка загрузки файлов.";
  }
}

async function openFile(runId, filePath, liEl) {
  fileList.querySelectorAll("li").forEach(l => l.classList.remove("active"));
  if (liEl) liEl.classList.add("active");

  fileCode.textContent = "Загрузка…";
  try {
    const res = await fetch(
      `/api/runs/${runId}/file?path=${encodeURIComponent(filePath)}`
    );
    if (!res.ok) { fileCode.textContent = "Файл не найден."; return; }
    const { content } = await res.json();
    fileCode.textContent = content;
  } catch {
    fileCode.textContent = "Ошибка загрузки файла.";
  }
}

// ───────────────────────────────────────────────
// Чат: добавление сообщений
// ───────────────────────────────────────────────
function addMessage(role, html) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  const tag = document.createElement("div");
  tag.className = "tag";
  tag.textContent = role === "user" ? "Вы" : "Ассистент";
  div.appendChild(tag);
  const body = document.createElement("div");
  body.innerHTML = html;
  div.appendChild(body);
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
  return body;
}

// ───────────────────────────────────────────────
// Опрос статуса задачи
// ───────────────────────────────────────────────
async function pollJob(jobId, statusEl, runId_holder) {
  return new Promise((resolve, reject) => {
    const timer = setInterval(async () => {
      try {
        const res = await fetch(`/api/jobs/${jobId}`);
        const data = await res.json();

        if (data.status === "done") {
          clearInterval(timer);
          runId_holder.runId = data.run_id;
          resolve(data.run_id);
        } else if (data.status === "error") {
          clearInterval(timer);
          reject(new Error(data.error || "Неизвестная ошибка"));
        } else {
          statusEl.innerHTML =
            `Статус: <strong>${data.status}</strong>…<span class="spinner"></span>`;
        }
      } catch (e) {
        clearInterval(timer);
        reject(e);
      }
    }, POLL_MS);
  });
}

// ───────────────────────────────────────────────
// Отправка формы
// ───────────────────────────────────────────────
inputForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  const specYaml = specInput.value.trim();
  if (!specYaml) return;

  const model = modelInput.value.trim() || "codellama:7b-instruct";
  const maxIters = parseInt(itersInput.value, 10) || 3;

  // Сообщение пользователя
  addMessage("user", `<pre style="white-space:pre-wrap">${escapeHtml(specYaml)}</pre>`);

  sendBtn.disabled = true;

  // Сообщение ассистента (обновляется по мере выполнения)
  const statusBody = addMessage(
    "assistant",
    `Запускаю генерацию…<span class="spinner"></span>`
  );

  try {
    const res = await fetch("/api/jobs/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ spec_yaml: specYaml, model, max_iters: maxIters }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    const { job_id } = await res.json();
    statusBody.innerHTML =
      `Задача <code>${job_id}</code> запущена…<span class="spinner"></span>`;

    const holder = { runId: null };
    const runId = await pollJob(job_id, statusBody, holder);

    addToHistory(runId);
    await refreshSidebar();

    statusBody.innerHTML =
      `<span class="status-pass">✅ Готово!</span> run_id: <code>${runId}</code>`;

    // Открываем файлы в правой панели
    const runLi = runsList.querySelector(`[data-run-id="${runId}"]`);
    await openRun(runId, runLi);

  } catch (err) {
    statusBody.innerHTML =
      `<span class="status-fail">❌ Ошибка:</span> ${escapeHtml(err.message)}`;
  } finally {
    sendBtn.disabled = false;
  }
});

// ───────────────────────────────────────────────
// Кнопка «Новый запуск»
// ───────────────────────────────────────────────
newBtn.addEventListener("click", () => {
  specInput.value = "";
  specInput.focus();
  messages.innerHTML = "";
  fileList.innerHTML = "";
  fileCode.textContent = "";
  viewerTitle.textContent = "Файлы проекта";
  downloadBtn.style.display = "none";
  runsList.querySelectorAll("li").forEach(l => l.classList.remove("active"));
});

// ───────────────────────────────────────────────
// Вспомогательные функции
// ───────────────────────────────────────────────
function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ───────────────────────────────────────────────
// Инициализация
// ───────────────────────────────────────────────
(async () => {
  await refreshSidebar();
})();
