const STORAGE_KEY = "task_followup_state_v2";

const taskList = document.getElementById("taskList");
const taskFilter = document.getElementById("taskFilter");
const copyFollowupBtn = document.getElementById("copyFollowupBtn");
const resetBtn = document.getElementById("resetBtn");

const progressText = document.getElementById("progressText");
const progressPercent = document.getElementById("progressPercent");
const progressBar = document.getElementById("progressBar");
const priorityList = document.getElementById("priorityList");

const latestReportContent = document.getElementById("latestReportContent");
const reportLoadedAt = document.getElementById("reportLoadedAt");
const reportTimeLine = document.getElementById("reportTimeLine");

let reportData = {
  reportTime: "",
  pendingTasks: []
};
let followupState = loadState();

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch (error) {
    console.warn("state parse failed:", error);
    return {};
  }
}

function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(followupState));
}

function stripToken(value) {
  return String(value || "")
    .replace(/`/g, "")
    .replace(/\\\|/g, "|")
    .trim();
}

function parseMarkdownTable(lines, startIndex) {
  const rows = [];
  let index = startIndex;

  while (index < lines.length && lines[index].trim().startsWith("|")) {
    const line = lines[index].trim();
    const cells = line
      .split("|")
      .slice(1, -1)
      .map((cell) => stripToken(cell));

    const isDivider = cells.length > 0 && cells.every((cell) => /^:?-{2,}:?$/.test(cell));
    if (!isDivider) {
      rows.push(cells);
    }
    index += 1;
  }

  return rows;
}

function parseReportTime(text) {
  const m = text.match(/^#\s+.*?（(.+?)）/m);
  return m ? m[1].trim() : "";
}

function parsePendingTasks(lines) {
  const idx = lines.findIndex((line) => line.startsWith("## 2. 未完成任务"));
  if (idx < 0) {
    return [];
  }

  const tableStart = lines.findIndex((line, i) => i > idx && line.trim().startsWith("|"));
  if (tableStart < 0) {
    return [];
  }

  const rows = parseMarkdownTable(lines, tableStart);
  if (rows.length <= 1) {
    return [];
  }

  return rows.slice(1).map((cells, i) => {
    const priority = Number.parseInt(cells[0], 10);
    return {
      priority: Number.isFinite(priority) ? priority : i + 1,
      taskId: cells[1] || `task-${i + 1}`,
      dueTime: cells[2] || "未写明",
      urgency: cells[3] || "未写明",
      content: cells[4] || "",
      pages: cells[5] || "-",
      eta: cells[6] || "-"
    };
  });
}

function parseReport(text) {
  const lines = String(text || "").split(/\r?\n/);
  return {
    reportTime: parseReportTime(text),
    pendingTasks: parsePendingTasks(lines)
  };
}

function ensureState(taskId) {
  if (!followupState[taskId]) {
    followupState[taskId] = {
      status: "todo",
      followDate: "",
      note: "",
      updatedAt: ""
    };
  }
  return followupState[taskId];
}

function nowText() {
  return new Date().toLocaleString();
}

function urgencyLevel(task) {
  const text = `${task.urgency} ${task.dueTime}`;
  if (text.includes("已逾期") || text.includes("24小时内")) {
    return "high";
  }
  return "mid";
}

function selectedTasks() {
  const filter = taskFilter ? taskFilter.value : "all";
  if (filter === "all") {
    return reportData.pendingTasks;
  }
  return reportData.pendingTasks.filter((task) => ensureState(task.taskId).status === filter);
}

function updateProgress() {
  const total = reportData.pendingTasks.length;
  const done = reportData.pendingTasks.filter((task) => ensureState(task.taskId).status === "done").length;
  const percent = total > 0 ? Math.round((done / total) * 100) : 0;

  progressText.textContent = `${done} / ${total}`;
  progressPercent.textContent = `${percent}%`;
  progressBar.style.width = `${percent}%`;
}

function renderPriority() {
  if (!priorityList) {
    return;
  }
  priorityList.innerHTML = "";

  const sorted = [...reportData.pendingTasks].sort((a, b) => {
    const ah = urgencyLevel(a) === "high" ? 0 : 1;
    const bh = urgencyLevel(b) === "high" ? 0 : 1;
    if (ah !== bh) {
      return ah - bh;
    }
    return a.priority - b.priority;
  });

  const top = sorted.slice(0, 3);
  if (top.length === 0) {
    const li = document.createElement("li");
    li.textContent = "当前无待办任务。";
    priorityList.appendChild(li);
    return;
  }

  top.forEach((task, idx) => {
    const li = document.createElement("li");
    li.innerHTML = `<strong>第${idx + 1}优先：</strong>${task.content}（截止：${task.dueTime}）`;
    priorityList.appendChild(li);
  });
}

function buildTaskCard(task, index) {
  const state = ensureState(task.taskId);
  const dueClass = urgencyLevel(task) === "high" ? "due-high" : "due-mid";

  const card = document.createElement("article");
  card.className = "task-card";
  card.style.setProperty("--delay", String(index));

  const top = document.createElement("div");
  top.className = "task-top";

  const label = document.createElement("label");
  label.className = "checkline";

  const checkbox = document.createElement("input");
  checkbox.className = "task-check";
  checkbox.type = "checkbox";
  checkbox.checked = state.status === "done";
  checkbox.addEventListener("change", () => {
    state.status = checkbox.checked ? "done" : "todo";
    state.updatedAt = nowText();
    saveState();
    renderAll();
  });

  const title = document.createElement("span");
  title.className = "task-title";
  title.textContent = task.content;

  label.appendChild(checkbox);
  label.appendChild(title);
  top.appendChild(label);

  const due = document.createElement("span");
  due.className = `due ${dueClass}`;
  due.textContent = `截止：${task.dueTime}（${task.urgency}）`;
  top.appendChild(due);

  const desc = document.createElement("p");
  desc.className = "task-desc";
  desc.textContent = `任务ID：${task.taskId}；页码/提示：${task.pages}；预计时长：${task.eta}`;

  const h3 = document.createElement("h3");
  h3.textContent = "跟进设置";

  const formRow = document.createElement("div");
  formRow.className = "task-form-row";

  const statusLabel = document.createElement("label");
  statusLabel.className = "field-inline";
  statusLabel.textContent = "状态";
  const select = document.createElement("select");
  select.className = "select-control";
  select.innerHTML = `
    <option value="todo">待办</option>
    <option value="doing">进行中</option>
    <option value="done">已完成</option>
  `;
  select.value = state.status;
  select.addEventListener("change", () => {
    state.status = select.value;
    state.updatedAt = nowText();
    saveState();
    renderAll();
  });
  statusLabel.appendChild(select);

  const dateLabel = document.createElement("label");
  dateLabel.className = "field-inline";
  dateLabel.textContent = "下次跟进";
  const dateInput = document.createElement("input");
  dateInput.type = "date";
  dateInput.value = state.followDate || "";
  dateInput.addEventListener("change", () => {
    state.followDate = dateInput.value;
    state.updatedAt = nowText();
    saveState();
  });
  dateLabel.appendChild(dateInput);

  formRow.appendChild(statusLabel);
  formRow.appendChild(dateLabel);

  const noteLabel = document.createElement("label");
  noteLabel.className = "field-block";
  noteLabel.textContent = "跟进备注";
  const note = document.createElement("textarea");
  note.className = "note-input";
  note.rows = 2;
  note.placeholder = "例如：今晚完成并家长签字后提交";
  note.value = state.note || "";
  note.addEventListener("change", () => {
    state.note = note.value.trim();
    state.updatedAt = nowText();
    saveState();
  });
  noteLabel.appendChild(note);

  const updated = document.createElement("p");
  updated.className = "task-updated";
  updated.textContent = `最近更新：${state.updatedAt || "未记录"}`;

  card.appendChild(top);
  card.appendChild(desc);
  card.appendChild(h3);
  card.appendChild(formRow);
  card.appendChild(noteLabel);
  card.appendChild(updated);
  return card;
}

function renderTasks() {
  if (!taskList) {
    return;
  }
  taskList.innerHTML = "";

  const tasks = selectedTasks();
  if (tasks.length === 0) {
    const p = document.createElement("p");
    p.className = "placeholder";
    p.textContent = "当前筛选下没有任务。";
    taskList.appendChild(p);
    return;
  }

  tasks.forEach((task, idx) => {
    taskList.appendChild(buildTaskCard(task, idx));
  });
}

function renderAll() {
  renderTasks();
  updateProgress();
  renderPriority();
}

async function copyFollowupList() {
  const lines = reportData.pendingTasks.map((task) => {
    const state = ensureState(task.taskId);
    const statusMap = {
      todo: "待办",
      doing: "进行中",
      done: "已完成"
    };
    const status = statusMap[state.status] || "待办";
    const note = state.note ? `；备注：${state.note}` : "";
    return `- [${status}] ${task.content}（ID:${task.taskId}；截止:${task.dueTime}；跟进:${state.followDate || "-"}${note}）`;
  });

  const output = `任务跟进清单（${nowText()}）\n${lines.join("\n")}`;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    await navigator.clipboard.writeText(output);
    return;
  }

  const input = document.createElement("textarea");
  input.value = output;
  document.body.appendChild(input);
  input.select();
  document.execCommand("copy");
  document.body.removeChild(input);
}

async function loadLatestReport() {
  try {
    const response = await fetch(`./homework_report.md?t=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const text = await response.text();
    latestReportContent.textContent = text.trim() || "报告文件为空。";
    reportLoadedAt.textContent = `已加载：${nowText()}`;
    reportData = parseReport(text);
    reportTimeLine.textContent = `报告时间：${reportData.reportTime || "--"}`;
    renderAll();
  } catch (error) {
    latestReportContent.textContent = "加载报告失败，请点击“打开报告原文”查看。";
    reportLoadedAt.textContent = "加载失败";
    reportTimeLine.textContent = "报告时间：--";
    console.error(error);
  }
}

if (taskFilter) {
  taskFilter.addEventListener("change", () => {
    renderTasks();
  });
}

if (copyFollowupBtn) {
  copyFollowupBtn.addEventListener("click", async () => {
    try {
      await copyFollowupList();
      copyFollowupBtn.textContent = "已复制";
      setTimeout(() => {
        copyFollowupBtn.textContent = "复制跟进清单";
      }, 1200);
    } catch (error) {
      console.error(error);
    }
  });
}

if (resetBtn) {
  resetBtn.addEventListener("click", () => {
    const ok = window.confirm("确认重置所有任务状态与备注吗？");
    if (!ok) {
      return;
    }
    followupState = {};
    saveState();
    renderAll();
  });
}

loadLatestReport();

