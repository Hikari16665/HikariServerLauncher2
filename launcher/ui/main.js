const invoke = window.__TAURI__.core.invoke;
const modeButtons = [...document.querySelectorAll(".mode")];
const launchButton = document.querySelector("#launch");
const autostartButton = document.querySelector("#autostart");
const message = document.querySelector("#message");
const installDir = document.querySelector("#install-dir");
const backendState = document.querySelector("#backend-state");
const keyNotice = document.querySelector("#key-notice");
const adminKey = document.querySelector("#admin-key");
const copyKeyButton = document.querySelector("#copy-key");
let selectedMode = "full";
let autostartEnabled = false;
let refreshing = false;

function showMessage(text, kind = "") {
  message.textContent = text;
  message.className = kind;
}

function renderAutostart(value) {
  autostartEnabled = value;
  autostartButton.classList.toggle("on", value);
  autostartButton.setAttribute("aria-checked", String(value));
}

function showAdminKey(value) {
  if (!value) return;
  adminKey.textContent = value;
  keyNotice.hidden = false;
}

copyKeyButton.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(adminKey.textContent);
    copyKeyButton.textContent = "已复制";
    setTimeout(() => { copyKeyButton.textContent = "复制"; }, 1600);
  } catch {
    showMessage("无法复制密钥，请手动选择复制", "error");
  }
});

async function refreshStatus() {
  if (refreshing) return;
  refreshing = true;
  try {
    const status = await invoke("get_status");
    installDir.textContent = status.install_dir || "未找到 HSL2 发布目录";
    backendState.textContent = status.backend_running ? "后端运行中" : "后端未运行";
    if (status.port_conflict) backendState.textContent = `${status.backend_port} 端口被其他程序占用`;
    backendState.classList.toggle("online", status.backend_running);
    backendState.classList.toggle("error", status.port_conflict);
    renderAutostart(status.autostart_enabled);
    showAdminKey(status.admin_key);
    modeButtons.find(button => button.dataset.mode === "frontend").disabled = !status.frontend_available;
    modeButtons.filter(button => button.dataset.mode !== "frontend").forEach(button => {
      button.disabled = !status.backend_available;
    });
    autostartButton.disabled = !status.backend_available;
    if (!status.backend_available && selectedMode !== "frontend" && status.frontend_available) {
      selectedMode = "frontend";
      modeButtons.forEach(item => item.classList.toggle("selected", item.dataset.mode === "frontend"));
    }
    launchButton.disabled = !modeButtons.some(button => button.dataset.mode === selectedMode && !button.disabled);
    if (status.install_error || !status.backend_available) {
      showMessage(status.install_error || "未找到后端程序，请重新安装 HSL2", "error");
    }
  } catch (error) {
    showMessage(String(error), "error");
  } finally {
    refreshing = false;
  }
}

modeButtons.forEach(button => button.addEventListener("click", () => {
  if (button.disabled) return;
  selectedMode = button.dataset.mode;
  modeButtons.forEach(item => item.classList.toggle("selected", item === button));
  showMessage(`将启动：${button.querySelector("strong").textContent}`);
}));

autostartButton.addEventListener("click", async () => {
  autostartButton.disabled = true;
  try {
    const enabled = await invoke("set_backend_autostart", { enabled: !autostartEnabled });
    renderAutostart(enabled);
    showMessage(enabled ? "已开启后端开机自启" : "已关闭后端开机自启", "success");
  } catch (error) {
    showMessage(String(error), "error");
  } finally {
    await refreshStatus();
  }
});

launchButton.addEventListener("click", async () => {
  launchButton.disabled = true;
  launchButton.textContent = selectedMode === "full" ? "等待后端…" : "正在启动…";
  showMessage(selectedMode === "full" ? "正在启动后端，随后打开前端" : selectedMode === "frontend" ? "正在打开前端" : "正在启动后端");
  try {
    const result = await invoke("launch_mode", { mode: selectedMode });
    showMessage(result.message, "success");
    showAdminKey(result.admin_key);
  } catch (error) {
    showMessage(String(error), "error");
  } finally {
    launchButton.textContent = "立即启动";
    await refreshStatus();
  }
});

refreshStatus();
setInterval(() => {
  if (!document.hidden && !launchButton.disabled) refreshStatus();
}, 2500);
