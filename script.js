const latestReportContent = document.getElementById("latestReportContent");
const reportLoadedAt = document.getElementById("reportLoadedAt");
const reportTime = document.getElementById("reportTime");
const taskList = document.getElementById("taskList");
const taskFilter = document.getElementById("taskFilter");
const copyFollowupBtn = document.getElementById("copyFollowupBtn");

const metricPending = document.getElementById("metricPending");
const metricDone = document.getElementById("metricDone");
const metricDoing = document.getElementById("metricDoing");
const metricUrgent = document.getElementById("metricUrgent");

const STORAGE_KEY = "task_followup_state_v1";

let reportData = {
  reportTime: "",
  pendingTasks: [],
  doneTasks: []
};
let followupState = loadFollowupState();

function stripMarkdownToken(value) {
  return String(value || "")
    .replace(/`/g, "")
    .replace(/\\\|/g, "|")
    .trim();
}

function parseMarkdownTable(lines, startIndex) {
  const rows = [];
  let index = startIndex;

  while (index < lines.length && lines[index].trim().startsWith("|")) {
    const raw = lines[index].trim();
    const cells = raw
      .split("|")
      .slice(1, -1)
      .map((cell) => stripMarkdownToken(cell));

    const isSeparator = cells.length > 0 && cells.every((cell) => /^:?-{2,}:?$/.test(cell));
    if (!isSeparator) {
      rows.push(cells);
    }
    index += 1;
  }

  return rows;
}

function parsePendingTasks(lines) {
  const sectionIndex = lines.findIndex((line) => line.startsWith("## 2. 未完成任务"));
  if (sectionIndex < 0) {
    return [];
  }

  const tableStart = lines.findIndex((line, idx) => idx > sectionIndex && line.trim().startsWith("|"));
  if (tableStart < 0) {
    return [];
  }

  const rows = parseMarkdownTable(lines, tableStart);
  if (rows.length <= 1) {
    return [];
  }

  return rows.slice(1).map((cells, idx) => {
    const priority = Number.parseInt(cells[0], 10);
    const taskId = cells[1] || `task-${idx + 1}`;
    return {
      priority: Number.isFinite(priority) ? priority : idx + 1,
      taskId,
      dueTime: cells[2] || "未写明",
      urgency: cells[3] || "未写明",
      content: cells[4] || "",
      pages: cells[5] || "-",
      eta: cells[6] || "-"
    };
  });
}

function parseDoneTasks(lines) {
  const sectionIndex = lines.findIndex((line) => line.startsWith("## 5. 已完成任务"));
  if (sectionIndex < 0) {
    return [];
  }

  const tableStart = lines.findIndex((line, idx) => idx > sectionIndex && line.trim().startsWith("|"));
  if (tableStart < 0) {
    return [];
  }

  const rows = parseMarkdownTable(lines, tableStart);
  if (rows.length <= 1) {
    return [];
  }

  return rows.slice(1).map((cells) => ({
    finishedAt: cells[1] || "",
    taskId: cells[2] || "",
    content: cells[3] || ""
  }));
}

function parseReportTime(text) {
  const m = text.match(/^#\s+.*?（(.+?)）/m);
  return m ? m[1].trim() : "";
}

function parseReportMarkdown(text) {
  const lines = String(text || "").split(/\r?\n/);
  return {
    reportTime: parseReportTime(text),
    pendingTasks: parsePendingTasks(lines),
    doneTasks: parseDoneTasks(lines)
  };
}

function loadFollowupState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch (error) {
    console.warn("load followup state failed:", error);
    return {};
  }
}

function saveFollowupState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(followupState));
}

function ensureTaskState(taskId) {
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

function formatNow() {
  return new Date().toLocaleString();
}

function createMetaChip(label, value) {
  const span = document.createElement("span");
  span.className = "chip";
  span.textContent = `${label}：${value || "-"}`;
  return span;
}

function isUrgentTask(task) {
  const text = `${task.urgency} ${task.dueTime}`;
  return text.includes("已逾期") || text.includes("24小时内") || text.includes("3天内");
}

function renderMetrics() {
  const all = reportData.pendingTasks;
  let done = 0;
  let doing = 0;

  all.forEach((task) => {
    const state = ensureTaskState(task.taskId);
    if (state.status === "done") {
      done += 1;
    } else if (state.status === "doing") {
      doing += 1;
    }
  });

  const urgentCount = all.filter((task) => isUrgentTask(task)).length;
  metricPending.textContent = String(all.length);
  metricDone.textContent = String(done);
  metricDoing.textContent = String(doing);
  metricUrgent.textContent = String(urgentCount);
}

function getFilteredTasks() {
  const filter = taskFilter ? taskFilter.value : "all";
  if (filter === "all") {
    return reportData.pendingTasks;
  }
  return reportData.pendingTasks.filter((task) => ensureTaskState(task.taskId).status === filter);
}

function renderTaskList() {
  if (!taskList) {
    return;
  }

  taskList.innerHTML = "";
  const tasks = getFilteredTasks();
  if (tasks.length === 0) {
    const placeholder = document.createElement("p");
    placeholder.className = "placeholder";
    placeholder.textContent = "当前筛选下没有任务。";
    taskList.appendChild(placeholder);
    renderMetrics();
    return;
  }

  tasks.forEach((task) => {
    const state = ensureTaskState(task.taskId);
    const item = document.createElement("article");
    item.className = `task-item status-${state.status}`;

    const head = document.createElement("div");
    head.className = "task-item-head";

    const titleWrap = document.createElement("div");
    titleWrap.className = "task-title-wrap";

    const priority = document.createElement("span");
    priority.className = "priority";
    priority.textContent = `P${task.priority}`;
    titleWrap.appendChild(priority);

    const title = document.createElement("h3");
    title.className = "task-title";
    title.textContent = task.content || task.taskId;
    titleWrap.appendChild(title);

    const idTag = document.createElement("code");
    idTag.className = "task-id";
    idTag.textContent = task.taskId;
    titleWrap.appendChild(idTag);

    head.appendChild(titleWrap);

    const statusSelect = document.createElement("select");
    statusSelect.className = "select-control";
    statusSelect.innerHTML = `
      <option value="todo">待办</option>
      <option value="doing">进行中</option>
      <option value="done">已完成</option>
    `;
    statusSelect.value = state.status;
    statusSelect.addEventListener("change", () => {
      state.status = statusSelect.value;
      state.updatedAt = formatNow();
      saveFollowupState();
      renderTaskList();
    });
    head.appendChild(statusSelect);

    const meta = document.createElement("div");
    meta.className = "task-meta";
    meta.appendChild(createMetaChip("截止", task.dueTime));
    meta.appendChild(createMetaChip("紧急度", task.urgency));
    meta.appendChild(createMetaChip("页码", task.pages));
    meta.appendChild(createMetaChip("预计时长", task.eta));

    const follow = document.createElement("div");
    follow.className = "task-follow";

    const dateWrap = document.createElement("label");
    dateWrap.className = "field";
    dateWrap.textContent = "下次跟进";
    const dateInput = document.createElement("input");
    dateInput.type = "date";
    dateInput.value = state.followDate || "";
    dateInput.addEventListener("change", () => {
      state.followDate = dateInput.value;
      state.updatedAt = formatNow();
      saveFollowupState();
      renderMetrics();
    });
    dateWrap.appendChild(dateInput);
    follow.appendChild(dateWrap);

    const noteWrap = document.createElement("label");
    noteWrap.className = "field field-note";
    noteWrap.textContent = "跟进备注";
    const noteInput = document.createElement("textarea");
    noteInput.rows = 2;
    noteInput.placeholder = "例如：今晚 19:30 完成第15页，家长签字后拍照提交";
    noteInput.value = state.note || "";
    noteInput.addEventListener("change", () => {
      state.note = noteInput.value.trim();
      state.updatedAt = formatNow();
      saveFollowupState();
    });
    noteWrap.appendChild(noteInput);
    follow.appendChild(noteWrap);

    const foot = document.createElement("p");
    foot.className = "task-updated";
    foot.textContent = state.updatedAt ? `最近更新：${state.updatedAt}` : "最近更新：未记录";

    item.appendChild(head);
    item.appendChild(meta);
    item.appendChild(follow);
    item.appendChild(foot);
    taskList.appendChild(item);
  });

  renderMetrics();
}

async function copyFollowupList() {
  const lines = [];
  reportData.pendingTasks.forEach((task) => {
    const state = ensureTaskState(task.taskId);
    const statusText = state.status === "done" ? "已完成" : state.status === "doing" ? "进行中" : "待办";
    lines.push(
      `- [${statusText}] ${task.content}（ID:${task.taskId}，截止:${task.dueTime}，跟进:${state.followDate || "-"}）${state.note ? ` 备注:${state.note}` : ""}`
    );
  });

  const output = `任务跟进清单（${new Date().toLocaleString()}）\n${lines.join("\n")}`;
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
    const response = await fetch(`./homework_report.md?t=${Date.now()}`, {
      cache: "no-store"
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const text = await response.text();
    latestReportContent.textContent = text.trim() || "报告文件为空。";
    reportLoadedAt.textContent = `已加载：${formatNow()}`;

    reportData = parseReportMarkdown(text);
    reportTime.textContent = `报告时间：${reportData.reportTime || "--"}`;
    renderTaskList();
  } catch (error) {
    latestReportContent.textContent = "加载报告失败，请点击“打开报告原文”查看。";
    reportLoadedAt.textContent = "加载失败";
    reportTime.textContent = "报告时间：--";
    taskList.innerHTML = '<p class="placeholder">加载失败，请稍后刷新重试。</p>';
    console.error("load report failed:", error);
  }
}

if (taskFilter) {
  taskFilter.addEventListener("change", () => {
    renderTaskList();
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
      console.error("copy followup failed:", error);
      copyFollowupBtn.textContent = "复制失败";
      setTimeout(() => {
        copyFollowupBtn.textContent = "复制跟进清单";
      }, 1200);
    }
  });
}

loadLatestReport();

