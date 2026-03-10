"use strict";

const POLL_MS = 2000;
const LS_HISTORY_KEY = "case_runs_history";
const LS_TITLES_KEY = "case_runs_titles";
const LS_THEME_KEY = "case_theme";
const TITLE_MAX_CHARS = 48;
const THEME_DARK = "dark";
const THEME_LIGHT = "light";

// DOM references
const runsList = document.getElementById("runs-list");
const messages = document.getElementById("messages");
const inputForm = document.getElementById("input-form");
const specInput = document.getElementById("spec-input");
const modelInput = document.getElementById("model-input");
const itersInput = document.getElementById("iters-input");
const sendBtn = document.getElementById("send-btn");
const newBtn = document.getElementById("new-btn");
const themeBtn = document.getElementById("theme-btn");
const fileList = document.getElementById("file-list");
const fileCode = document.getElementById("file-code");
const viewerTitle = document.getElementById("viewer-title");
const downloadBtn = document.getElementById("download-btn");

let runTitles = {};

function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem(LS_HISTORY_KEY) || "[]");
  } catch {
    return [];
  }
}

function isRussianUi() {
  const lang = String(document.documentElement.lang || navigator.language || "").toLowerCase();
  return lang.startsWith("ru");
}

function detectInitialTheme() {
  try {
    const saved = localStorage.getItem(LS_THEME_KEY);
    if (saved === THEME_DARK || saved === THEME_LIGHT) return saved;
  } catch {
    // Ignore localStorage issues and fallback to media query.
  }

  return window.matchMedia("(prefers-color-scheme: dark)").matches ? THEME_DARK : THEME_LIGHT;
}

function updateThemeButton(theme) {
  if (!themeBtn) return;
  const ru = isRussianUi();
  const isDark = theme === THEME_DARK;
  const switchTo = isDark ? THEME_LIGHT : THEME_DARK;

  themeBtn.textContent = isDark ? "☀" : "☾";
  themeBtn.title = ru
    ? switchTo === THEME_LIGHT
      ? "Переключить на светлую тему"
      : "Переключить на тёмную тему"
    : switchTo === THEME_LIGHT
      ? "Switch to light theme"
      : "Switch to dark theme";
  themeBtn.setAttribute("aria-label", themeBtn.title);
}

function applyTheme(theme, persist = true) {
  const normalized = theme === THEME_DARK ? THEME_DARK : THEME_LIGHT;
  document.documentElement.setAttribute("data-theme", normalized);
  updateThemeButton(normalized);
  if (!persist) return;
  try {
    localStorage.setItem(LS_THEME_KEY, normalized);
  } catch {
    // Ignore localStorage issues.
  }
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") === THEME_DARK
    ? THEME_DARK
    : THEME_LIGHT;
  applyTheme(current === THEME_DARK ? THEME_LIGHT : THEME_DARK);
}

function saveHistory(history) {
  localStorage.setItem(LS_HISTORY_KEY, JSON.stringify(history));
}

function addToHistory(runId) {
  const history = loadHistory().filter((item) => item !== runId);
  history.unshift(runId);
  saveHistory(history.slice(0, 50));
}

function loadTitles() {
  try {
    return JSON.parse(localStorage.getItem(LS_TITLES_KEY) || "{}");
  } catch {
    return {};
  }
}

function saveTitles(titles) {
  localStorage.setItem(LS_TITLES_KEY, JSON.stringify(titles));
}

function saveTitle(runId, title) {
  if (!runId || !title) return;
  const titles = loadTitles();
  titles[runId] = normalizeTitle(title);
  saveTitles(titles);
  runTitles = { ...runTitles, ...titles };
}

function normalizeTitle(text) {
  const collapsed = String(text || "").replace(/\s+/g, " ").trim();
  if (!collapsed) return "New chat";
  if (collapsed.length <= TITLE_MAX_CHARS) return collapsed;
  return `${collapsed.slice(0, TITLE_MAX_CHARS - 1).trim()}…`;
}

function titleFor(runId) {
  return runTitles[runId] || runId;
}

function inferTitleFromInput(input) {
  const trimmed = String(input || "").trim();
  if (!trimmed) return "New chat";

  const fenced = trimmed.match(/^\s*```(?:yaml|yml|json)?\s*\n([\s\S]*?)\n```\s*$/i);
  const plain = fenced ? fenced[1] : trimmed;

  for (const line of plain.split("\n")) {
    const cleaned = line.replace(/^[#>*\-\d.)\s]+/, "").trim();
    if (cleaned) return normalizeTitle(cleaned);
  }
  return "New chat";
}

async function refreshSidebar() {
  let serverRuns = [];
  let serverTitles = {};
  try {
    const res = await fetch("/api/runs");
    const data = await res.json();
    serverRuns = data.runs || [];
    serverTitles = data.titles || {};
  } catch {
    // Show local history even if server is unavailable.
  }

  const history = loadHistory();
  const allRuns = [...new Set([...serverRuns, ...history])];
  runTitles = { ...loadTitles(), ...serverTitles };
  saveTitles(runTitles);

  runsList.innerHTML = "";
  allRuns.forEach((runId) => {
    const title = titleFor(runId);
    const li = document.createElement("li");
    li.textContent = title;
    li.dataset.runId = runId;
    li.title = `${title} (${runId})`;
    li.addEventListener("click", () => openRun(runId, li));
    runsList.appendChild(li);
  });
}

async function openRun(runId, liEl) {
  runsList.querySelectorAll("li").forEach((li) => li.classList.remove("active"));
  if (liEl) liEl.classList.add("active");

  viewerTitle.textContent = titleFor(runId);
  downloadBtn.style.display = "inline-block";
  downloadBtn.onclick = () => {
    window.location = `/api/runs/${runId}/download`;
  };

  fileList.innerHTML = "";
  fileCode.textContent = "";

  try {
    const res = await fetch(`/api/runs/${runId}/files`);
    if (!res.ok) {
      fileCode.textContent = "Файлы не найдены.";
      return;
    }
    const { files } = await res.json();
    files.forEach((filePath) => {
      const li = document.createElement("li");
      li.textContent = filePath;
      li.title = filePath;
      li.addEventListener("click", () => openFile(runId, filePath, li));
      fileList.appendChild(li);
    });
    if (files.length > 0) {
      openFile(runId, files[0], fileList.firstChild);
    }
  } catch {
    fileCode.textContent = "Ошибка загрузки файлов.";
  }
}

async function openFile(runId, filePath, liEl) {
  fileList.querySelectorAll("li").forEach((li) => li.classList.remove("active"));
  if (liEl) liEl.classList.add("active");

  fileCode.textContent = "Загрузка…";
  try {
    const res = await fetch(`/api/runs/${runId}/file?path=${encodeURIComponent(filePath)}`);
    if (!res.ok) {
      fileCode.textContent = "Файл не найден.";
      return;
    }
    const { content } = await res.json();
    fileCode.textContent = content;
  } catch {
    fileCode.textContent = "Ошибка загрузки файла.";
  }
}

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

async function pollJob(jobId, statusEl) {
  return new Promise((resolve, reject) => {
    const timer = setInterval(async () => {
      try {
        const res = await fetch(`/api/jobs/${jobId}`);
        const data = await res.json();
        if (data.status === "done") {
          clearInterval(timer);
          resolve(data);
        } else if (data.status === "error") {
          clearInterval(timer);
          reject(new Error(data.error || "Неизвестная ошибка"));
        } else {
          statusEl.innerHTML = `Статус: <strong>${data.status}</strong>…<span class="spinner"></span>`;
        }
      } catch (err) {
        clearInterval(timer);
        reject(err);
      }
    }, POLL_MS);
  });
}

inputForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const specYaml = specInput.value.trim();
  if (!specYaml) return;

  const model = modelInput.value.trim() || "qwen3-coder:30b";
  const maxIters = parseInt(itersInput.value, 10) || 3;
  const localTitle = inferTitleFromInput(specYaml);

  addMessage("user", `<pre style="white-space:pre-wrap">${escapeHtml(specYaml)}</pre>`);
  sendBtn.disabled = true;

  const statusBody = addMessage(
    "assistant",
    "Запускаю генерацию…<span class=\"spinner\"></span>",
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

    const started = await res.json();
    const jobId = started.job_id;
    statusBody.innerHTML = `Задача <code>${jobId}</code> запущена…<span class="spinner"></span>`;

    const done = await pollJob(jobId, statusBody);
    const runId = done.run_id;
    if (!runId) throw new Error("Сервер не вернул run_id");

    const finalTitle = normalizeTitle(done.title || started.title || localTitle);
    saveTitle(runId, finalTitle);
    addToHistory(runId);
    await refreshSidebar();

    statusBody.innerHTML = `<span class="status-pass">✅ Готово!</span> ${escapeHtml(finalTitle)}`;
    const runLi = runsList.querySelector(`[data-run-id="${runId}"]`);
    await openRun(runId, runLi);
  } catch (err) {
    statusBody.innerHTML = `<span class="status-fail">❌ Ошибка:</span> ${escapeHtml(err.message)}`;
  } finally {
    sendBtn.disabled = false;
  }
});

newBtn.addEventListener("click", () => {
  specInput.value = "";
  specInput.focus();
  messages.innerHTML = "";
  fileList.innerHTML = "";
  fileCode.textContent = "";
  viewerTitle.textContent = "Файлы проекта";
  downloadBtn.style.display = "none";
  runsList.querySelectorAll("li").forEach((li) => li.classList.remove("active"));
});

if (themeBtn) {
  themeBtn.addEventListener("click", toggleTheme);
}

function escapeHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

(async () => {
  applyTheme(detectInitialTheme(), false);
  await refreshSidebar();
})();
