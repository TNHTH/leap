function emptyAnnotations(mapId = "") {
  return { map_id: mapId, zones: [], waypoints: [], fixed_cameras: [], routes: [] };
}

const state = {
  status: null,
  currentMapId: "",
  annotations: emptyAnnotations(),
  selectedRouteId: "",
  drawingRect: null,
  teleopTimer: null,
  gamepadTimer: null,
  gamepadEnabled: false,
  gamepadConnected: false,
  gamepadIndex: null,
  gamepadZeroSent: true,
  gamepadPumpActive: false,
  testReportSummary: null,
  localLogEntries: [],
  alarmVisible: false,
  lastAlarmKey: "",
  localLogs: [],
};

const GAMEPAD_PUMP_BUTTON_INDEX = 5;
const GAMEPAD_PUMP_BUTTON_LABEL = "RB";

const dom = {};

async function apiGet(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return await response.json();
}

async function apiPost(url, payload = {}) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return await response.json();
}

function initDom() {
  [
    "missionState",
    "faultCode",
    "pumpState",
    "missionDetail",
    "batteryVoltage",
    "sensorBattery",
    "sensorPerception",
    "sensorSafety",
    "sensorWaterLevel",
    "sensorTemperature",
    "odomPose",
    "odomTwist",
    "currentMapId",
    "currentRouteId",
    "panelMode",
    "hostName",
    "hostIp",
    "hostUptime",
    "cpuLoad",
    "memoryUsage",
    "diskUsage",
    "odomSignal",
    "vehicleSignal",
    "groundSignal",
    "frontCameraState",
    "frontCameraImage",
    "frontCameraPlaceholder",
    "frontCameraHint",
    "groundCameraState",
    "groundCameraImage",
    "groundCameraPlaceholder",
    "groundCameraHint",
    "mapSelect",
    "loadMapButton",
    "mapImage",
    "mapCanvas",
    "mapEmptyState",
    "toolSelect",
    "saveAnnotationsButton",
    "routeNameInput",
    "routeModeSelect",
    "routeWaypointSelect",
    "saveRouteButton",
    "openPatrolModeButton",
    "routeSummary",
    "refreshButton",
    "stopButton",
    "startMappingButton",
    "saveMapButton",
    "enterAnnotationButton",
    "missionReadyButton",
    "startSinglePatrolButton",
    "startLoopPatrolButton",
    "stopPatrolButton",
    "triggerFireButton",
    "clearFireButton",
    "pumpOnButton",
    "pumpOffButton",
    "gamepadStatus",
    "gamepadHint",
    "gamepadToggleButton",
    "alarmOverlay",
    "alarmTitle",
    "alarmMessage",
    "alarmTimestamp",
    "alarmSource",
    "alarmDismissButton",
    "historyLevelFilter",
    "historyKeywordInput",
    "historyExportJsonButton",
    "historyExportCsvButton",
    "historyTableBody",
    "testReportSummaryMeta",
    "testReportSummaryBody",
    "logOutput",
  ].forEach((id) => {
    dom[id] = document.getElementById(id);
  });
}

function appendLog(message, level = "info") {
  const now = new Date();
  const stamp = now.toLocaleTimeString();
  const prefix = level === "error" ? "[ERROR]" : level === "warn" ? "[WARN]" : "[INFO]";
  state.localLogEntries.unshift({
    level,
    message,
    updated_at: now.toISOString(),
  });
  state.localLogEntries = state.localLogEntries.slice(0, 120);
  state.localLogs.unshift(`${prefix} [${stamp}] ${message}`);
  state.localLogs = state.localLogs.slice(0, 24);
  renderLogs();
  renderHistoryTable();
}

function renderLogs() {
  const remoteLogs = (state.status?.logs || []).map(
    (item) => `[${item.updated_at}] ${item.level}: ${item.message}`
  );
  dom.logOutput.textContent = [...state.localLogs, ...remoteLogs].join("\n") || "暂无日志";
}

function historyEntries() {
  const remoteLogs = state.status?.logs || [];
  return [...state.localLogEntries, ...remoteLogs];
}

function filteredHistoryEntries() {
  const level = dom.historyLevelFilter?.value || "all";
  const keyword = (dom.historyKeywordInput?.value || "").trim().toLowerCase();
  return historyEntries().filter((item) => {
    const itemLevel = String(item.level || "info").toLowerCase();
    const message = String(item.message || "");
    if (level !== "all" && itemLevel !== level) {
      return false;
    }
    if (keyword && !message.toLowerCase().includes(keyword)) {
      return false;
    }
    return true;
  });
}

function renderHistoryTable() {
  const rows = filteredHistoryEntries();
  if (!rows.length) {
    dom.historyTableBody.innerHTML = `
      <tr>
        <td colspan="3">没有匹配的日志记录</td>
      </tr>
    `;
    return;
  }
  dom.historyTableBody.innerHTML = rows.map((item) => `
    <tr>
      <td>${item.updated_at || "-"}</td>
      <td>${item.level || "-"}</td>
      <td>${item.message || "-"}</td>
    </tr>
  `).join("");
}

function downloadText(filename, content, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function exportHistoryJson() {
  const rows = filteredHistoryEntries();
  downloadText("broadcast-center-history.json", JSON.stringify(rows, null, 2), "application/json");
}

function exportHistoryCsv() {
  const rows = filteredHistoryEntries();
  const lines = ["updated_at,level,message"];
  rows.forEach((item) => {
    const values = [item.updated_at || "", item.level || "", item.message || ""].map((value) =>
      `"${String(value).replaceAll('"', '""')}"`
    );
    lines.push(values.join(","));
  });
  downloadText("broadcast-center-history.csv", lines.join("\n"), "text/csv;charset=utf-8");
}

function playAlarmTone() {
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  if (!AudioCtx) return;
  const ctx = new AudioCtx();
  const oscillator = ctx.createOscillator();
  const gain = ctx.createGain();
  oscillator.type = "sawtooth";
  oscillator.frequency.setValueAtTime(880, ctx.currentTime);
  gain.gain.setValueAtTime(0.0001, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.08, ctx.currentTime + 0.02);
  gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.45);
  oscillator.connect(gain);
  gain.connect(ctx.destination);
  oscillator.start();
  oscillator.stop(ctx.currentTime + 0.48);
  oscillator.onended = () => ctx.close().catch(() => {});
}

function hideAlarmOverlay() {
  state.alarmVisible = false;
  dom.alarmOverlay.hidden = true;
}

function maybeShowAlarm(mission, perception, safety) {
  const activeFault = safety?.fault_code || mission?.fault_code || "";
  const isAlarm = Boolean(mission?.fire_active || mission?.state === "FIRE_ALERT" || activeFault);
  if (!isAlarm) {
    hideAlarmOverlay();
    return;
  }

  const source = perception?.source || mission?.state || "broadcast_center";
  const timestamp = new Date().toLocaleString();
  const key = `${mission?.state || ""}|${activeFault}|${perception?.confidence || ""}|${source}`;
  dom.alarmTitle.textContent = mission?.fire_active || mission?.state === "FIRE_ALERT" ? "火情告警" : "安全告警";
  dom.alarmMessage.textContent = mission?.detail || safety?.detail || "检测到告警，请立即确认。";
  dom.alarmTimestamp.textContent = `时间：${timestamp}`;
  dom.alarmSource.textContent = `来源：${source}`;
  dom.alarmOverlay.hidden = false;
  state.alarmVisible = true;
  if (state.lastAlarmKey !== key) {
    state.lastAlarmKey = key;
    playAlarmTone();
  }
}

function renderTestReportSummary() {
  const summary = state.testReportSummary;
  if (!summary?.available) {
    dom.testReportSummaryMeta.textContent = summary?.error
      ? `测试报告未就绪：${summary.error}`
      : "测试报告尚未加载。";
    dom.testReportSummaryBody.innerHTML = `
      <tr>
        <td colspan="5">暂无可展示的测试报告汇总数据</td>
      </tr>
    `;
    return;
  }

  dom.testReportSummaryMeta.textContent = `来源：${summary.docx_path} · 汇总条目：${summary.row_count}`;
  dom.testReportSummaryBody.innerHTML = (summary.rows || []).map((row) => `
    <tr>
      <td>${row.category || "-"}</td>
      <td>${row.item || "-"}</td>
      <td>${row.focus || "-"}</td>
      <td>${row.record || "-"}</td>
      <td>${row.source || "-"}</td>
    </tr>
  `).join("") || `
    <tr>
      <td colspan="5">测试报告存在，但没有抽取到适合展示的数据</td>
    </tr>
  `;
}

function renderSensorPanel(battery, perception, safety) {
  dom.sensorBattery.textContent = Number.isFinite(battery?.voltage)
    ? `${battery.voltage.toFixed(2)} V`
    : "未收到";
  dom.sensorPerception.textContent = perception?.active
    ? `active · ${(perception.confidence || 0).toFixed(2)}`
    : perception?.input_online
      ? "idle"
      : "离线/待接入";
  dom.sensorSafety.textContent = safety?.fault_code
    ? `${safety.fault_code}`
    : safety?.detail || "ok";
}

function formatNumber(value, digits = 2) {
  return Number.isFinite(value) ? value.toFixed(digits) : "-";
}

function formatPercent(value) {
  return Number.isFinite(value) ? `${value.toFixed(1)}%` : "-";
}

function formatGiB(bytes) {
  return Number.isFinite(bytes) ? `${(bytes / (1024 ** 3)).toFixed(1)} GiB` : "-";
}

function formatKiBToGiB(kib) {
  return Number.isFinite(kib) ? `${(kib / (1024 ** 2)).toFixed(1)} GiB` : "-";
}

function formatDuration(totalSec) {
  if (!Number.isFinite(totalSec) || totalSec < 0) return "-";
  const hours = Math.floor(totalSec / 3600);
  const minutes = Math.floor((totalSec % 3600) / 60);
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  if (minutes > 0) {
    return `${minutes}m`;
  }
  return `${Math.floor(totalSec)}s`;
}

function formatAge(seconds) {
  if (!Number.isFinite(seconds)) return "无心跳";
  if (seconds < 1) return "刚刚";
  if (seconds < 60) return `${seconds.toFixed(1)}s 前`;
  return `${(seconds / 60).toFixed(1)}m 前`;
}

function setMapEmptyState(title, detail) {
  dom.mapEmptyState.hidden = false;
  dom.mapEmptyState.innerHTML = `<div><strong>${title}</strong><p>${detail}</p></div>`;
}

function clearMapStage(title, detail) {
  state.annotations = emptyAnnotations(state.currentMapId);
  dom.mapImage.classList.remove("ready");
  dom.mapImage.removeAttribute("src");
  const ctx = dom.mapCanvas.getContext("2d");
  ctx.clearRect(0, 0, dom.mapCanvas.width, dom.mapCanvas.height);
  setMapEmptyState(title, detail);
  refreshWaypointOptions();
  refreshRouteSummary();
}

function syncMapOptions() {
  const maps = state.status?.maps || [];
  dom.mapSelect.innerHTML = "";
  if (!maps.length) {
    const option = document.createElement("option");
    option.textContent = "暂无地图";
    option.value = "";
    dom.mapSelect.appendChild(option);
    dom.mapSelect.disabled = true;
    dom.loadMapButton.disabled = true;
    state.currentMapId = "";
    return;
  }

  dom.mapSelect.disabled = false;
  dom.loadMapButton.disabled = false;
  maps.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.map_id;
    option.textContent = `${item.map_id} · 航点 ${item.waypoint_count} · 路线 ${item.route_count}`;
    dom.mapSelect.appendChild(option);
  });
  if (!state.currentMapId) {
    state.currentMapId = maps[0].map_id;
  }
  dom.mapSelect.value = state.currentMapId;
}

function resolveCameraHint(expected, online, age, fallbackText) {
  if (!expected) {
    return "当前模式未启用这路视频流。";
  }
  if (!online) {
    return fallbackText || "相机未连上，或设备文件还没就绪。";
  }
  return `视频流在线，最近心跳 ${formatAge(age)}。`;
}

function renderCameraCard(prefix, camera, expected, age, fallbackPort, fallbackText) {
  const stateEl = prefix === "front" ? dom.frontCameraState : dom.groundCameraState;
  const imageEl = prefix === "front" ? dom.frontCameraImage : dom.groundCameraImage;
  const placeholderEl = prefix === "front" ? dom.frontCameraPlaceholder : dom.groundCameraPlaceholder;
  const hintEl = prefix === "front" ? dom.frontCameraHint : dom.groundCameraHint;

  const online = Boolean(camera?.online);
  const port = camera?.mjpeg_port || fallbackPort;
  const allowLocalFallback = prefix === "ground";
  const streamUrl = camera?.stream_url || (
    allowLocalFallback ? `http://${window.location.hostname}:${port}/stream` : ""
  );

  stateEl.textContent = !expected ? "disabled" : online ? "online" : "offline";
  if (expected && online && !streamUrl) {
    hintEl.textContent = `已收到相机心跳，但后端没有提供可用 stream_url。端口 ${port}`;
  } else {
    hintEl.textContent = `${resolveCameraHint(expected, online, age, fallbackText)} 端口 ${port}`;
  }

  if (expected && online && streamUrl) {
    if (imageEl.dataset.streamUrl !== streamUrl) {
      imageEl.src = streamUrl;
      imageEl.dataset.streamUrl = streamUrl;
    }
    imageEl.classList.add("online");
    placeholderEl.hidden = true;
  } else {
    imageEl.classList.remove("online");
    imageEl.removeAttribute("src");
    delete imageEl.dataset.streamUrl;
    placeholderEl.hidden = false;
  }
}

function refreshWaypointOptions() {
  dom.routeWaypointSelect.innerHTML = "";
  (state.annotations.waypoints || []).forEach((waypoint) => {
    const option = document.createElement("option");
    option.value = waypoint.id;
    option.textContent = waypoint.name;
    dom.routeWaypointSelect.appendChild(option);
  });
}

function refreshRouteSummary() {
  if (!state.currentMapId) {
    dom.routeSummary.textContent = "当前没有地图。先进入建图态并保存地图，再配置 waypoint 和路线。";
    return;
  }

  const waypoints = state.annotations.waypoints || [];
  const fixedCameras = state.annotations.fixed_cameras || [];
  const routes = state.annotations.routes || [];
  const lines = [`当前地图: ${state.currentMapId}`];

  if (!waypoints.length) {
    lines.push("还没有 waypoint。切到“航点”模式后，在地图上单击落点。");
  } else {
    lines.push(`已保存 waypoint: ${waypoints.length} 个`);
  }
  if (fixedCameras.length) {
    lines.push(`固定摄像头位置: ${fixedCameras.map((item) => item.camera_id || item.name || item.id).join(", ")}`);
  } else {
    lines.push("还没有固定摄像头位置。切到“固定摄像头位置”后，在地图上单击放置。");
  }

  if (!routes.length) {
    lines.push("还没有路线。选中 waypoint 后点击“保存路线”。");
  } else {
    lines.push(
      ...routes.map((route) => `${route.name} [${route.mode}] -> ${route.waypoint_ids.join(", ")}`)
    );
  }

  dom.routeSummary.textContent = lines.join("\n");
}

function resizeCanvas() {
  const rect = dom.mapImage.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) {
    return;
  }
  dom.mapCanvas.width = rect.width;
  dom.mapCanvas.height = rect.height;
}

function imageToCanvas(point) {
  return {
    x: (point.x / dom.mapImage.naturalWidth) * dom.mapCanvas.width,
    y: (point.y / dom.mapImage.naturalHeight) * dom.mapCanvas.height,
  };
}

function canvasToImage(clientX, clientY) {
  const rect = dom.mapCanvas.getBoundingClientRect();
  return {
    x: ((clientX - rect.left) / rect.width) * dom.mapImage.naturalWidth,
    y: ((clientY - rect.top) / rect.height) * dom.mapImage.naturalHeight,
  };
}

function renderMapOverlay() {
  const ctx = dom.mapCanvas.getContext("2d");
  ctx.clearRect(0, 0, dom.mapCanvas.width, dom.mapCanvas.height);
  if (!state.currentMapId || !dom.mapImage.naturalWidth) {
    return;
  }

  const colorMap = {
    keepout_zone: "#cf4236",
    patrol_zone: "#1f7a53",
    static_obstacle: "#3a5f84",
    fire_risk_zone: "#ff6b35",
    equipment: "#8c5e3c",
    water_source: "#2e9cca",
  };

  (state.annotations.zones || []).forEach((zone) => {
    if (!zone.points || zone.points.length < 3) return;
    ctx.beginPath();
    zone.points.forEach((point, index) => {
      const mapped = imageToCanvas(point);
      if (index === 0) ctx.moveTo(mapped.x, mapped.y);
      else ctx.lineTo(mapped.x, mapped.y);
    });
    ctx.closePath();
    ctx.fillStyle = `${colorMap[zone.kind] || "#ff6b35"}55`;
    ctx.strokeStyle = colorMap[zone.kind] || "#ff6b35";
    ctx.lineWidth = 2;
    ctx.fill();
    ctx.stroke();
  });

  (state.annotations.waypoints || []).forEach((waypoint) => {
    const mapped = imageToCanvas(waypoint.pixel);
    ctx.beginPath();
    ctx.fillStyle = "#10212f";
    ctx.arc(mapped.x, mapped.y, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#ffffff";
    ctx.font = "12px 'IBM Plex Sans Condensed', sans-serif";
    ctx.fillText(waypoint.name, mapped.x + 8, mapped.y - 8);
  });

  (state.annotations.fixed_cameras || []).forEach((camera) => {
    const mapped = imageToCanvas(camera.pixel);
    ctx.beginPath();
    ctx.fillStyle = "#0f6e7a";
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 2;
    ctx.arc(mapped.x, mapped.y, 8, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "#10212f";
    ctx.font = "12px 'IBM Plex Sans Condensed', sans-serif";
    ctx.fillText(`CAM ${camera.camera_id || camera.name || ""}`, mapped.x + 10, mapped.y - 10);
  });

  const route = (state.annotations.routes || []).find((item) => item.id === state.selectedRouteId);
  if (route) {
    ctx.beginPath();
    ctx.strokeStyle = "#10212f";
    ctx.lineWidth = 3;
    route.waypoint_ids.forEach((waypointId, index) => {
      const waypoint = (state.annotations.waypoints || []).find((item) => item.id === waypointId);
      if (!waypoint) return;
      const mapped = imageToCanvas(waypoint.pixel);
      if (index === 0) ctx.moveTo(mapped.x, mapped.y);
      else ctx.lineTo(mapped.x, mapped.y);
    });
    ctx.stroke();
  }

  if (state.drawingRect) {
    const { x, y, width, height } = state.drawingRect;
    ctx.setLineDash([8, 4]);
    ctx.strokeStyle = "#ff6b35";
    ctx.strokeRect(x, y, width, height);
    ctx.setLineDash([]);
  }
}

function buildRectangleZone(start, end, kind) {
  const left = Math.min(start.x, end.x);
  const right = Math.max(start.x, end.x);
  const top = Math.min(start.y, end.y);
  const bottom = Math.max(start.y, end.y);
  return {
    id: `zone_${Date.now()}`,
    kind,
    points: [
      { x: left, y: top },
      { x: right, y: top },
      { x: right, y: bottom },
      { x: left, y: bottom },
    ],
  };
}

function installMapInteractions() {
  dom.mapCanvas.addEventListener("pointerdown", (event) => {
    if (
      !state.currentMapId
      || dom.toolSelect.value === "waypoint"
      || dom.toolSelect.value === "fixed_camera"
      || !dom.mapImage.naturalWidth
    ) return;
    const rect = dom.mapCanvas.getBoundingClientRect();
    const originX = event.clientX - rect.left;
    const originY = event.clientY - rect.top;
    state.drawingRect = { originX, originY, x: originX, y: originY, width: 0, height: 0 };
    renderMapOverlay();
  });

  dom.mapCanvas.addEventListener("pointermove", (event) => {
    if (!state.drawingRect) return;
    const rect = dom.mapCanvas.getBoundingClientRect();
    const currentX = event.clientX - rect.left;
    const currentY = event.clientY - rect.top;
    state.drawingRect.x = Math.min(state.drawingRect.originX, currentX);
    state.drawingRect.y = Math.min(state.drawingRect.originY, currentY);
    state.drawingRect.width = Math.abs(currentX - state.drawingRect.originX);
    state.drawingRect.height = Math.abs(currentY - state.drawingRect.originY);
    renderMapOverlay();
  });

  dom.mapCanvas.addEventListener("pointerup", (event) => {
    if (!state.currentMapId || !dom.mapImage.naturalWidth) return;
    if (dom.toolSelect.value === "waypoint") {
      const pixel = canvasToImage(event.clientX, event.clientY);
      const name = window.prompt("航点名称", `wp_${(state.annotations.waypoints || []).length + 1}`);
      if (!name) return;
      state.annotations.waypoints.push({
        id: `wp_${Date.now()}`,
        name,
        pixel,
        yaw: 0.0,
      });
      refreshWaypointOptions();
      refreshRouteSummary();
      renderMapOverlay();
      return;
    }

    if (dom.toolSelect.value === "fixed_camera") {
      const pixel = canvasToImage(event.clientX, event.clientY);
      const cameraId = window.prompt("固定摄像头 ID", "ground_camera");
      if (!cameraId) return;
      const fixedCameras = state.annotations.fixed_cameras || [];
      const existingIndex = fixedCameras.findIndex((item) => item.camera_id === cameraId || item.id === cameraId);
      const item = {
        id: cameraId,
        camera_id: cameraId,
        name: cameraId,
        pixel,
        yaw: 0.0,
        route_id: `camera:${cameraId}`,
      };
      if (existingIndex >= 0) {
        fixedCameras[existingIndex] = item;
      } else {
        fixedCameras.push(item);
      }
      state.annotations.fixed_cameras = fixedCameras;
      refreshRouteSummary();
      renderMapOverlay();
      return;
    }

    if (!state.drawingRect) return;
    const stageRect = dom.mapCanvas.getBoundingClientRect();
    const start = canvasToImage(stageRect.left + state.drawingRect.x, stageRect.top + state.drawingRect.y);
    const end = canvasToImage(
      stageRect.left + state.drawingRect.x + state.drawingRect.width,
      stageRect.top + state.drawingRect.y + state.drawingRect.height
    );
    state.annotations.zones.push(buildRectangleZone(start, end, dom.toolSelect.value));
    state.drawingRect = null;
    renderMapOverlay();
  });
}

async function loadMap(mapId) {
  if (!mapId) {
    state.currentMapId = "";
    clearMapStage("当前还没有可用地图", "先进入建图态，保存地图，再回到这里做标注。");
    return;
  }

  try {
    state.currentMapId = mapId;
    state.annotations = await apiGet(`/api/maps/${mapId}/annotations`);
    state.annotations.map_id = mapId;
    state.selectedRouteId = state.annotations.routes?.[0]?.id || "";
    refreshWaypointOptions();
    refreshRouteSummary();
    dom.mapImage.classList.remove("ready");
    dom.mapEmptyState.hidden = true;
    dom.mapImage.onload = () => {
      dom.mapImage.classList.add("ready");
      resizeCanvas();
      renderMapOverlay();
    };
    dom.mapImage.onerror = () => {
      dom.mapImage.classList.remove("ready");
      setMapEmptyState("地图底图读取失败", "标注文件在，但底图资源不存在或尚未生成。");
    };
    dom.mapImage.src = `/api/maps/${mapId}/map?ts=${Date.now()}`;
  } catch (error) {
    clearMapStage("地图加载失败", error.message);
    appendLog(`地图加载失败: ${error.message}`, "error");
  }
}

async function runAction(action, successMessage = "") {
  try {
    const result = await action();
    if (successMessage) {
      appendLog(successMessage);
    }
    return result;
  } catch (error) {
    appendLog(error.message, "error");
    throw error;
  }
}

async function sendMission(command, extra = {}) {
  return apiPost("/api/mission", { command, ...extra });
}

function bindTeleopButton(button) {
  const vx = Number(button.dataset.vx || 0);
  const vz = Number(button.dataset.vz || 0);

  const start = async () => {
    clearInterval(state.teleopTimer);
    await apiPost("/api/cmd_vel", { vx, vz });
    state.teleopTimer = setInterval(() => {
      apiPost("/api/cmd_vel", { vx, vz }).catch((error) => appendLog(error.message, "error"));
    }, 120);
  };

  const stop = async () => {
    clearInterval(state.teleopTimer);
    await apiPost("/api/stop");
  };

  button.addEventListener("pointerdown", () => runAction(start, `Teleop 输出: vx=${vx}, vz=${vz}`));
  button.addEventListener("pointerup", () => runAction(stop));
  button.addEventListener("pointerleave", () => runAction(stop));
}

function scaleGamepadAxis(value, deadzone = 0.15) {
  if (!Number.isFinite(value)) return 0;
  if (Math.abs(value) < deadzone) return 0;
  const normalized = (Math.abs(value) - deadzone) / (1 - deadzone);
  return Math.sign(value) * normalized;
}

function getActiveGamepad() {
  if (!navigator.getGamepads) return null;
  const pads = navigator.getGamepads();
  if (state.gamepadIndex !== null && pads[state.gamepadIndex]) {
    return pads[state.gamepadIndex];
  }
  for (const pad of pads) {
    if (pad) {
      state.gamepadIndex = pad.index;
      return pad;
    }
  }
  return null;
}

function refreshGamepadStatus() {
  const supported = Boolean(navigator.getGamepads);
  const pad = getActiveGamepad();
  state.gamepadConnected = Boolean(pad);

  if (!supported) {
    dom.gamepadStatus.textContent = "浏览器不支持";
    dom.gamepadHint.textContent = "当前浏览器没有 Gamepad API，仍可使用页面按钮或独立手柄脚本。";
    dom.gamepadToggleButton.disabled = true;
    dom.gamepadToggleButton.textContent = "不可用";
    return;
  }

  dom.gamepadToggleButton.textContent = state.gamepadEnabled ? "关闭手柄控制" : "启用手柄控制";
  dom.gamepadToggleButton.disabled = !pad;

  if (!pad) {
    dom.gamepadStatus.textContent = "未连接";
    dom.gamepadHint.textContent = "插入手柄并保持当前页面激活，然后点击“启用手柄控制”。";
    return;
  }

  dom.gamepadStatus.textContent = `${state.gamepadEnabled ? "接管中" : "已连接"} · ${pad.id}`;
  dom.gamepadHint.textContent = `默认使用左摇杆控制前后/转向，按住 ${GAMEPAD_PUMP_BUTTON_LABEL} 持续抽水，松开即停。`;
}

async function stopGamepadTeleop(sendStop = true) {
  clearInterval(state.gamepadTimer);
  state.gamepadTimer = null;
  state.gamepadEnabled = false;
  if (state.gamepadPumpActive) {
    await apiPost("/api/pump", { enabled: false });
    state.gamepadPumpActive = false;
  }
  refreshGamepadStatus();
  if (sendStop) {
    await apiPost("/api/stop");
  }
  state.gamepadZeroSent = true;
}

async function syncGamepadPump(pressed) {
  const active = Boolean(pressed);
  if (active === state.gamepadPumpActive) {
    return;
  }

  if (active) {
    await apiPost("/api/pump", { enabled: true, authorized_test: true });
    appendLog(`手柄按钮 ${GAMEPAD_PUMP_BUTTON_LABEL} 按下，开始持续抽水`);
  } else {
    await apiPost("/api/pump", { enabled: false });
    appendLog(`手柄按钮 ${GAMEPAD_PUMP_BUTTON_LABEL} 松开，停止抽水`);
  }
  state.gamepadPumpActive = active;
}

async function gamepadTick() {
  const pad = getActiveGamepad();
  refreshGamepadStatus();
  if (!state.gamepadEnabled || !pad) {
    if (state.gamepadPumpActive) {
      await syncGamepadPump(false);
    }
    if (!state.gamepadZeroSent) {
      await apiPost("/api/stop");
      state.gamepadZeroSent = true;
    }
    return;
  }

  const pumpPressed = Boolean(pad.buttons?.[GAMEPAD_PUMP_BUTTON_INDEX]?.pressed);
  await syncGamepadPump(pumpPressed);

  const vx = Number((-scaleGamepadAxis(pad.axes?.[1]) * 0.25).toFixed(3));
  const vz = Number((-scaleGamepadAxis(pad.axes?.[0]) * 0.8).toFixed(3));

  if (Math.abs(vx) < 0.01 && Math.abs(vz) < 0.01) {
    if (!state.gamepadZeroSent) {
      await apiPost("/api/stop");
      state.gamepadZeroSent = true;
    }
    return;
  }

  state.gamepadZeroSent = false;
  await apiPost("/api/cmd_vel", { vx, vz });
}

function installGamepadTeleop() {
  refreshGamepadStatus();

  window.addEventListener("gamepadconnected", (event) => {
    state.gamepadIndex = event.gamepad.index;
    refreshGamepadStatus();
    appendLog(`手柄已连接: ${event.gamepad.id}`);
  });

  window.addEventListener("gamepaddisconnected", async (event) => {
    if (state.gamepadIndex === event.gamepad.index) {
      state.gamepadIndex = null;
    }
    if (state.gamepadEnabled) {
      await stopGamepadTeleop(true);
    } else {
      refreshGamepadStatus();
    }
    appendLog(`手柄已断开: ${event.gamepad.id}`, "warn");
  });

  dom.gamepadToggleButton.addEventListener("click", () =>
    runAction(async () => {
      if (state.gamepadEnabled) {
        await stopGamepadTeleop(true);
        appendLog("已关闭手柄控制");
        return;
      }
      const pad = getActiveGamepad();
      if (!pad) {
        throw new Error("没有检测到可用手柄，请先连接手柄。");
      }
      state.gamepadEnabled = true;
      state.gamepadZeroSent = true;
      refreshGamepadStatus();
      clearInterval(state.gamepadTimer);
      state.gamepadTimer = setInterval(() => {
        gamepadTick().catch((error) => appendLog(error.message, "error"));
      }, 120);
      appendLog(`已启用手柄控制: ${pad.id}`);
    })
  );
}

function refreshStatusView() {
  if (!state.status) return;

  const mission = state.status.mission || {};
  const battery = state.status.battery || {};
  const odom = state.status.odom || {};
  const cameras = state.status.cameras || {};
  const perception = state.status.perception || {};
  const safety = state.status.safety || {};
  const system = state.status.system || {};
  const signals = system.signals || {};

  dom.missionState.textContent = mission.state || "BOOT";
  dom.faultCode.textContent = mission.fault_code || "-";
  dom.pumpState.textContent = state.status.pump_state ? "ON" : "OFF";
  dom.missionDetail.textContent = mission.detail || "等待状态机上线";
  dom.batteryVoltage.textContent = Number.isFinite(battery.voltage)
    ? `${battery.voltage.toFixed(2)} V${Number.isFinite(battery.percentage) ? ` · ${(battery.percentage * 100).toFixed(0)}%` : ""}`
    : "未收到电池数据";
  dom.odomPose.textContent = odom.x !== undefined ? `${odom.x.toFixed(2)}, ${odom.y.toFixed(2)}` : "未收到里程计";
  dom.odomTwist.textContent =
    odom.linear_x !== undefined ? `${odom.linear_x.toFixed(2)} m/s · ${odom.angular_z.toFixed(2)} rad/s` : "未收到速度数据";
  dom.currentMapId.textContent = mission.map_id || state.currentMapId || "-";
  dom.currentRouteId.textContent = mission.route_id || state.selectedRouteId || "-";

  dom.panelMode.textContent = system.panel_mode || "full_stack";
  const statusOnly = (system.panel_mode || "full_stack") === "status_only";
  const routePanel = document.querySelector(".route-panel");
  const mapPanel = document.querySelector(".map-panel");
  if (routePanel) {
    routePanel.hidden = statusOnly;
  }
  if (mapPanel) {
    mapPanel.hidden = statusOnly;
  }
  dom.hostName.textContent = system.hostname || "-";
  dom.hostIp.textContent = (system.ipv4 || []).join(" / ") || "未解析到 IP";
  dom.hostUptime.textContent = formatDuration(system.uptime_sec);
  dom.cpuLoad.textContent = Array.isArray(system.loadavg)
    ? `${system.loadavg.join(" / ")} · ${system.cpu_count || 0} 核`
    : "-";
  dom.memoryUsage.textContent = system.memory
    ? `${formatPercent(system.memory.used_percent)} · ${formatKiBToGiB(system.memory.available_kib)} 可用 / ${formatKiBToGiB(system.memory.total_kib)}`
    : "-";
  dom.diskUsage.textContent = system.disk
    ? `${formatPercent(system.disk.used_percent)} · ${formatGiB(system.disk.free_bytes)} 可用 / ${formatGiB(system.disk.total_bytes)}`
    : "-";
  renderSensorPanel(battery, perception, safety);
  maybeShowAlarm(mission, perception, safety);

  dom.odomSignal.textContent = signals.odom_online
    ? `在线 · ${formatAge(signals.odom_age_sec)}`
    : signals.odom_age_sec == null
      ? "未收到里程计"
      : `离线 · ${formatAge(signals.odom_age_sec)}`;
  dom.vehicleSignal.textContent = !signals.vehicle_camera_expected
    ? "当前模式未启用"
    : signals.vehicle_camera_online
      ? `在线 · ${formatAge(signals.vehicle_camera_age_sec)}`
      : signals.vehicle_camera_age_sec == null
        ? "未收到相机心跳"
        : `离线 · ${formatAge(signals.vehicle_camera_age_sec)}`;
  dom.groundSignal.textContent = !signals.ground_camera_expected
    ? "当前模式未启用"
    : signals.ground_camera_online
      ? `在线 · ${formatAge(signals.ground_camera_age_sec)}`
      : signals.ground_camera_age_sec == null
        ? "未收到相机心跳"
        : `离线 · ${formatAge(signals.ground_camera_age_sec)}`;

  renderCameraCard(
    "front",
    cameras.vehicle_camera || cameras.front_camera,
    Boolean(signals.vehicle_camera_expected),
    signals.vehicle_camera_age_sec,
    8091,
    "车载相机未就绪，检查 /dev/video0 或启用视频模式。"
  );
  renderCameraCard(
    "ground",
    cameras.ground_camera,
    Boolean(signals.ground_camera_expected),
    signals.ground_camera_age_sec,
    8092,
    "固定摄像头未就绪，当前通常保持占位。"
  );

  syncMapOptions();
  refreshRouteSummary();
  renderLogs();
  renderHistoryTable();
  updateActionAvailability();
}

async function refreshStatus() {
  state.status = await apiGet("/api/status");
  refreshStatusView();

  if (state.currentMapId && state.currentMapId !== state.annotations.map_id) {
    await loadMap(state.currentMapId);
  }

  if (!state.currentMapId) {
    clearMapStage("当前还没有可用地图", "先进入建图态并保存地图，然后这里会自动出现底图与标注能力。");
  }
}

async function refreshTestReportSummary() {
  state.testReportSummary = await apiGet("/api/test-report-summary");
  renderTestReportSummary();
}

function updateActionAvailability() {
  const hasMap = Boolean(state.currentMapId);
  const hasWaypoints = Boolean(state.annotations.waypoints?.length);
  dom.enterAnnotationButton.disabled = !hasMap;
  dom.saveAnnotationsButton.disabled = !hasMap;
  dom.missionReadyButton.disabled = !hasMap;
  dom.saveRouteButton.disabled = !hasWaypoints;
  dom.startSinglePatrolButton.disabled = !hasWaypoints;
  dom.startLoopPatrolButton.disabled = !hasWaypoints;
}

function saveRoute() {
  if (!state.currentMapId) {
    appendLog("当前没有地图，无法保存路线。", "warn");
    return;
  }

  const waypointIds = Array.from(dom.routeWaypointSelect.selectedOptions).map((option) => option.value);
  if (!waypointIds.length) {
    appendLog("请至少选择一个 waypoint。", "warn");
    return;
  }

  const route = {
    id: `route_${Date.now()}`,
    name: dom.routeNameInput.value.trim() || `route_${Date.now()}`,
    mode: dom.routeModeSelect.value,
    waypoint_ids: waypointIds,
  };
  state.annotations.routes.push(route);
  state.selectedRouteId = route.id;
  refreshRouteSummary();
  renderMapOverlay();
  appendLog(`路线已加入本地编辑区: ${route.name}`);
}

async function saveAnnotations() {
  if (!state.currentMapId) {
    appendLog("请先加载地图。", "warn");
    return;
  }
  const result = await apiPost("/api/maps/annotations", {
    map_id: state.currentMapId,
    annotations: state.annotations,
  });
  appendLog(`标注已保存，keepout 已生成: ${result.keepout.keepout_yaml}`);
  await refreshStatus();
}

function installActions() {
  dom.refreshButton.addEventListener("click", () => runAction(async () => {
    await refreshStatus();
    await refreshTestReportSummary();
  }, "状态已刷新"));
  dom.mapSelect.addEventListener("change", () => loadMap(dom.mapSelect.value));
  dom.loadMapButton.addEventListener("click", () => runAction(() => loadMap(dom.mapSelect.value), "地图已载入"));
  dom.saveAnnotationsButton.addEventListener("click", () => runAction(saveAnnotations));
  dom.saveRouteButton.addEventListener("click", saveRoute);
  dom.routeWaypointSelect.addEventListener("change", () => {
    const selected = Array.from(dom.routeWaypointSelect.selectedOptions).map((item) => item.value);
    const route = state.annotations.routes.find((item) => item.id === state.selectedRouteId);
    if (route) {
      route.waypoint_ids = selected;
    }
    refreshRouteSummary();
    renderMapOverlay();
  });
  dom.historyLevelFilter.addEventListener("change", renderHistoryTable);
  dom.historyKeywordInput.addEventListener("input", renderHistoryTable);
  dom.historyExportJsonButton.addEventListener("click", exportHistoryJson);
  dom.historyExportCsvButton.addEventListener("click", exportHistoryCsv);
  dom.alarmDismissButton.addEventListener("click", hideAlarmOverlay);
  dom.openPatrolModeButton.addEventListener("click", () =>
    runAction(
      async () => {
        const runtimeResult = await apiPost("/api/runtime/patrol/ensure_remote", {});
        appendLog(`树莓派巡航模式确认完成: ${runtimeResult.stdout || "ok"}`);
      },
      "已打开巡航/避障模式"
    )
  );

  dom.startMappingButton.addEventListener("click", () =>
    runAction(
      async () => {
        const runtimeResult = await apiPost("/api/runtime/mapping/start", {});
        appendLog(
          runtimeResult.already_running
            ? "建图工作台已在运行，复用当前 RViz/SLAM 进程。"
            : `建图工作台已启动 pid=${runtimeResult.pid}`
        );
        return await sendMission("enter_mapping", { detail: "网页进入建图态" });
      },
      "已请求进入建图态，并拉起 RViz 建图工作台"
    )
  );
  dom.enterAnnotationButton.addEventListener("click", () =>
    runAction(
      () => sendMission("start_annotation", { map_id: state.currentMapId, detail: "网页进入标注态" }),
      "已请求进入标注态"
    )
  );
  dom.missionReadyButton.addEventListener("click", () =>
    runAction(
      () =>
        sendMission("mission_ready", {
          map_id: state.currentMapId,
          route_id: state.selectedRouteId,
          detail: "网页标注完成，任务就绪",
        }),
      "已请求进入任务就绪态"
    )
  );
  dom.startSinglePatrolButton.addEventListener("click", () =>
    runAction(
      async () => {
        const runtimeResult = await apiPost("/api/runtime/patrol/ensure_remote", {});
        appendLog(`树莓派巡航模式确认完成: ${runtimeResult.stdout || "ok"}`);
        return await sendMission("start_patrol", {
          map_id: state.currentMapId,
          route_id: state.selectedRouteId,
          mode: "single_run",
          detail: "网页启动单次巡航",
        });
      },
      "已请求启动单次巡航"
    )
  );
  dom.startLoopPatrolButton.addEventListener("click", () =>
    runAction(
      async () => {
        const runtimeResult = await apiPost("/api/runtime/patrol/ensure_remote", {});
        appendLog(`树莓派巡航模式确认完成: ${runtimeResult.stdout || "ok"}`);
        return await sendMission("start_patrol", {
          map_id: state.currentMapId,
          route_id: state.selectedRouteId,
          mode: "loop",
          detail: "网页启动循环巡航",
        });
      },
      "已请求启动循环巡航"
    )
  );
  dom.stopPatrolButton.addEventListener("click", () =>
    runAction(
      () => sendMission("stop_patrol", { detail: "网页要求停止巡航" }),
      "已请求停止巡航"
    )
  );

  dom.triggerFireButton.addEventListener("click", () =>
    runAction(
      () =>
        apiPost("/api/fire", {
          active: true,
          source: "web_panel",
          camera_id: "manual",
          level: "warning",
          description: "网页手动触发火情",
        }),
      "火情占位已触发"
    )
  );
  dom.clearFireButton.addEventListener("click", () =>
    runAction(
      () =>
        apiPost("/api/fire", {
          active: false,
          source: "web_panel",
          camera_id: "manual",
          level: "info",
          description: "网页手动清除火情",
        }),
      "火情占位已清除"
    )
  );

  dom.saveMapButton.addEventListener("click", () =>
    runAction(async () => {
      const mapId = window.prompt("保存地图 ID", state.currentMapId || `map_${Date.now()}`);
      if (!mapId) return;
      const result = await apiPost("/api/maps/save", { map_id: mapId });
      appendLog(`地图已保存: ${result.map_id}`);
      await refreshStatus();
      await loadMap(result.map_id);
    })
  );

  dom.pumpOnButton.addEventListener("click", () =>
    runAction(
      () => apiPost("/api/pump", { enabled: true, authorized_test: true }),
      "已发送授权开泵命令"
    )
  );
  dom.pumpOffButton.addEventListener("click", () =>
    runAction(() => apiPost("/api/pump", { enabled: false }), "已发送停泵命令")
  );
  dom.stopButton.addEventListener("click", () =>
    runAction(() => apiPost("/api/stop"), "已发送急停命令")
  );

  document.querySelectorAll(".teleop-btn[data-vx]").forEach(bindTeleopButton);
}

async function boot() {
  initDom();
  installMapInteractions();
  installActions();
  installGamepadTeleop();
  await refreshStatus();
  await refreshTestReportSummary();
  updateActionAvailability();
  window.addEventListener("resize", () => {
    resizeCanvas();
    renderMapOverlay();
  });
  setInterval(() => {
    refreshStatus().catch((error) => appendLog(error.message, "error"));
    updateActionAvailability();
  }, 1200);
}

window.addEventListener("DOMContentLoaded", boot);
