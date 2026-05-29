let modules = [];
let selected = null;
let currentTaskId = null;
let pollTimer = null;

const moduleList = document.querySelector("#moduleList");
const moduleTitle = document.querySelector("#moduleTitle");
const moduleDesc = document.querySelector("#moduleDesc");
const fields = document.querySelector("#fields");
const taskForm = document.querySelector("#taskForm");
const refreshBtn = document.querySelector("#refreshBtn");
const statusValue = document.querySelector("#statusValue");
const taskIdValue = document.querySelector("#taskIdValue");
const resultPathValue = document.querySelector("#resultPathValue");
const resultJson = document.querySelector("#resultJson");
const logOutput = document.querySelector("#logOutput");
const taskMeta = document.querySelector("#taskMeta");
const executorState = document.querySelector("#executorState");
const historyList = document.querySelector("#historyList");
const historyRefreshBtn = document.querySelector("#historyRefreshBtn");
const outputPreview = document.querySelector("#outputPreview");
const previewMeta = document.querySelector("#previewMeta");
const csvFieldNames = new Set(["data", "predictions"]);

async function loadModules() {
  modules = await fetch("/api/modules").then(r => r.json());
  selected = modules[0];
  renderModules();
  renderForm();
  loadHistory();
}

function renderModules() {
  moduleList.innerHTML = "";
  modules.forEach(module => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `module-button ${module.task === selected.task ? "active" : ""}`;
    button.innerHTML = `${module.title}<span>${module.domain} / ${module.task}</span>`;
    button.addEventListener("click", () => {
      selected = module;
      renderModules();
      renderForm();
    });
    moduleList.appendChild(button);
  });
}

function renderForm() {
  moduleTitle.textContent = selected.title;
  moduleDesc.textContent = selected.description;
  fields.innerHTML = "";
  selected.fields.forEach(field => {
    const label = document.createElement("label");
    label.textContent = field.label;
    const input = document.createElement("input");
    input.name = field.name;
    input.type = field.type === "number" ? "number" : "text";
    input.value = field.defaultValue;
    if (field.type === "number") input.step = "any";
    label.appendChild(input);
    if (isCsvField(field)) {
      label.appendChild(createCsvUploader(field, input));
    }
    fields.appendChild(label);
  });
}

function isCsvField(field) {
  return field.type !== "number" && (csvFieldNames.has(field.name) || field.label.toUpperCase().includes("CSV"));
}

function createCsvUploader(field, targetInput) {
  const wrapper = document.createElement("div");
  wrapper.className = "upload-row";

  const fileInput = document.createElement("input");
  fileInput.type = "file";
  fileInput.accept = ".csv,text/csv";
  fileInput.id = `upload_${field.name}`;

  const button = document.createElement("button");
  button.type = "button";
  button.textContent = "上传 CSV";

  const status = document.createElement("span");
  status.textContent = "选择本地 CSV 后自动填入路径";

  button.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", async () => {
    const file = fileInput.files?.[0];
    if (!file) return;
    status.textContent = "上传中...";
    button.disabled = true;
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("task", selected.task);
      form.append("fieldName", field.name);
      const response = await fetch("/api/uploads/csv", {
        method: "POST",
        body: form
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "上传失败");
      targetInput.value = payload.path;
      status.textContent = `${payload.originalName} / ${payload.rows} 行 / ${payload.columns.length} 列`;
      outputPreview.innerHTML = renderCsvTable(payload.preview.join("\n"));
      previewMeta.textContent = `已上传 ${payload.path}`;
      renderCsvValidation(payload, field, targetInput, wrapper);
    } catch (error) {
      status.textContent = String(error.message || error);
    } finally {
      button.disabled = false;
      fileInput.value = "";
    }
  });

  wrapper.append(button, status, fileInput);
  return wrapper;
}

function renderCsvValidation(payload, field, targetInput, wrapper) {
  wrapper.querySelector(".mapping-panel")?.remove();
  const validation = payload.validation;
  if (!validation || !validation.required?.length) return;

  const panel = document.createElement("div");
  panel.className = `mapping-panel ${validation.usable ? "ok" : "warn"}`;

  if (validation.usable) {
    panel.innerHTML = `
      <strong>字段校验通过</strong>
      <span>${escapeHtml(validation.message)}</span>
    `;
    wrapper.appendChild(panel);
    return;
  }

  const options = payload.columns.map(column => `<option value="${escapeHtml(column)}">${escapeHtml(column)}</option>`).join("");
  panel.innerHTML = `
    <strong>需要字段映射</strong>
    <span>${escapeHtml(validation.message)}</span>
    <div class="mapping-grid">
      ${validation.missing.map(required => {
        const suggested = validation.suggestedMappings?.[required] || "";
        return `
          <label>
            <span>${escapeHtml(required)}</span>
            <select data-required="${escapeHtml(required)}">
              <option value="">选择 CSV 列</option>
              ${payload.columns.map(column => `
                <option value="${escapeHtml(column)}" ${column === suggested ? "selected" : ""}>${escapeHtml(column)}</option>
              `).join("")}
            </select>
          </label>
        `;
      }).join("")}
    </div>
    <button type="button" class="mapping-apply">应用映射</button>
  `;

  const applyButton = panel.querySelector(".mapping-apply");
  applyButton.addEventListener("click", async () => {
    const mappings = {};
    panel.querySelectorAll("select[data-required]").forEach(select => {
      if (select.value) mappings[select.dataset.required] = select.value;
    });
    if (Object.keys(mappings).length === 0) {
      panel.querySelector("span").textContent = "请至少选择一个 CSV 列。";
      return;
    }

    applyButton.disabled = true;
    applyButton.textContent = "处理中...";
    try {
      const response = await fetch("/api/uploads/csv/map", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          path: payload.path,
          task: selected.task,
          fieldName: field.name,
          mappings
        })
      });
      const mapped = await response.json();
      if (!response.ok) throw new Error(mapped.error || "映射失败");
      targetInput.value = mapped.path;
      outputPreview.innerHTML = renderCsvTable(mapped.preview.join("\n"));
      previewMeta.textContent = `已映射 ${mapped.path}`;
      renderCsvValidation(mapped, field, targetInput, wrapper);
    } catch (error) {
      panel.querySelector("span").textContent = String(error.message || error);
    } finally {
      applyButton.disabled = false;
      applyButton.textContent = "应用映射";
    }
  });

  wrapper.appendChild(panel);
}

function collectParams() {
  const data = new FormData(taskForm);
  const params = {};
  selected.fields.forEach(field => {
    const value = data.get(field.name);
    params[field.name] = field.type === "number" ? Number(value) : value;
  });
  return params;
}

async function submitTask(event) {
  event.preventDefault();
  executorState.textContent = "RUNNING";
  const response = await fetch("/api/tasks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      task: selected.task,
      params: collectParams()
    })
  });

  const payload = await response.json();
  if (!response.ok) {
    resultJson.textContent = JSON.stringify(payload, null, 2);
    executorState.textContent = "ERROR";
    return;
  }

  currentTaskId = payload.taskId;
  taskIdValue.textContent = currentTaskId;
  taskMeta.textContent = `${selected.task} 已提交`;
  statusValue.textContent = "RUNNING";
  resultPathValue.textContent = "-";
  resultJson.textContent = JSON.stringify(payload, null, 2);
  startPolling();
}

function startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  refreshTask();
  pollTimer = setInterval(refreshTask, 1800);
}

async function refreshTask() {
  if (!currentTaskId) return;
  const task = await fetch(`/api/tasks/${currentTaskId}`).then(r => r.json());
  statusValue.textContent = (task.status || "running").toUpperCase();
  resultPathValue.textContent = task.resultPath || task.result_path || "-";
  resultJson.textContent = JSON.stringify(task, null, 2);
  executorState.textContent = task.status === "failed" ? "ERROR" : task.status === "success" ? "READY" : "RUNNING";

  const logs = await fetch(`/api/tasks/${currentTaskId}/logs`).then(r => r.json());
  logOutput.textContent = [
    logs.hostStdout,
    logs.stdout,
    logs.hostStderr,
    logs.stderr
  ].filter(Boolean).join("\n");

  if (task.status === "success" || task.status === "failed") {
    clearInterval(pollTimer);
    pollTimer = null;
    loadHistory();
    loadOutput(currentTaskId);
  }
}

async function loadHistory() {
  const tasks = await fetch("/api/tasks").then(r => r.json());
  historyList.innerHTML = "";
  if (!tasks.length) {
    historyList.innerHTML = `<p class="empty">暂无任务</p>`;
    return;
  }
  tasks.forEach(task => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `history-item ${task.status}`;
    button.innerHTML = `
      <strong>${task.task || "unknown"}</strong>
      <span>${task.taskId}</span>
      <em>${(task.status || "running").toUpperCase()} · ${task.updatedAt || ""}</em>
    `;
    button.addEventListener("click", () => selectHistoryTask(task.taskId));
    historyList.appendChild(button);
  });
}

async function selectHistoryTask(taskId) {
  currentTaskId = taskId;
  taskIdValue.textContent = taskId;
  await refreshTask();
  await loadOutput(taskId);
}

async function loadOutput(taskId) {
  try {
    const response = await fetch(`/api/tasks/${taskId}/output`);
    const contentType = response.headers.get("content-type") || "";
    if (contentType.startsWith("image/")) {
      const blob = await response.blob();
      const imageUrl = URL.createObjectURL(blob);
      outputPreview.innerHTML = `<img class="preview-image" src="${imageUrl}" alt="任务输出图片">`;
      previewMeta.textContent = "图片输出";
      return;
    }

    const payload = await response.json();
    if (!response.ok) {
      outputPreview.innerHTML = `
        <div class="empty-state">
          <strong>暂无可预览文件</strong>
          <span>${escapeHtml(payload.message || "这个任务可能生成的是模型目录，详细信息请看左侧结果 JSON 和运行日志。")}</span>
        </div>
      `;
      previewMeta.textContent = "无单独预览文件";
      return;
    }
    previewMeta.textContent = payload.path || "输出文件";
    if (payload.kind === "json") {
      outputPreview.innerHTML = `<pre class="console embedded">${escapeHtml(JSON.stringify(JSON.parse(payload.content), null, 2))}</pre>`;
    } else if (payload.kind === "csv") {
      outputPreview.innerHTML = renderCsvTable(payload.content);
    } else {
      outputPreview.innerHTML = `<pre class="console embedded">${escapeHtml(payload.content)}</pre>`;
    }
  } catch (error) {
    outputPreview.innerHTML = `<pre class="console embedded">${escapeHtml(String(error))}</pre>`;
    previewMeta.textContent = "读取输出失败";
  }
}

function renderCsvTable(text) {
  const rows = text.trim().split(/\r?\n/).slice(0, 40).map(line => line.split(","));
  if (!rows.length) return `<p class="empty">CSV 为空</p>`;
  const [header, ...body] = rows;
  return `
    <div class="table-wrap">
      <table>
        <thead><tr>${header.map(cell => `<th>${escapeHtml(cell)}</th>`).join("")}</tr></thead>
        <tbody>
          ${body.map(row => `<tr>${row.map(cell => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

taskForm.addEventListener("submit", submitTask);
refreshBtn.addEventListener("click", refreshTask);
historyRefreshBtn.addEventListener("click", loadHistory);
loadModules();
