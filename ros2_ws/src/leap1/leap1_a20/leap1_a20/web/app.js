function emptyAnnotations(mapId = "") {
  return { map_id: mapId, zones: [], waypoints: [], routes: [] };
}

const state = {
  status: null,
  currentMapId: "",
  annotations: emptyAnnotations(),
  selectedRouteId: "",
  drawingRect: null,
  teleopTimer: null,
  localLogs: [],
};

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
    "logOutput",
  ].forEach((id) => {
    dom[id] = document.getElementById(id);
  });
}

function appendLog(message, level = "info") {
  const stamp = new Date().toLocaleTimeString();
  const prefix = level === "error" ? "[ERROR]" : level === "warn" ? "[WARN]" : "[INFO]";
  state.localLogs.unshift(`${prefix} [${stamp}] ${message}`);
  state.localLogs = state.localLogs.slice(0, 24);
  renderLogs();
}

function renderLogs() {
  const remoteLogs = (state.status?.logs || []).map(
    (item) => `[${item.updated_at}] ${item.level}: ${item.message}`
  );
  dom.logOutput.textContent = [...state.localLogs, ...remoteLogs].join("\n") || "暂无日志";
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

  stateEl.textContent = !expected ? "disabled" : online ? "online" : "offline";
  hintEl.textContent = `${resolveCameraHint(expected, online, age, fallbackText)} 端口 ${port}`;

  if (expected && online) {
    imageEl.src = `http://${window.location.hostname}:${port}/stream?ts=${Date.now()}`;
    imageEl.classList.add("online");
    placeholderEl.hidden = true;
  } else {
    imageEl.classList.remove("online");
    imageEl.removeAttribute("src");
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
  const routes = state.annotations.routes || [];
  const lines = [`当前地图: ${state.currentMapId}`];

  if (!waypoints.length) {
    lines.push("还没有 waypoint。切到“航点”模式后，在地图上单击落点。");
  } else {
    lines.push(`已保存 waypoint: ${waypoints.length} 个`);
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
    if (!state.currentMapId || dom.toolSelect.value === "waypoint" || !dom.mapImage.naturalWidth) return;
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

function refreshStatusView() {
  if (!state.status) return;

  const mission = state.status.mission || {};
  const battery = state.status.battery || {};
  const odom = state.status.odom || {};
  const cameras = state.status.cameras || {};
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
  dom.refreshButton.addEventListener("click", () => runAction(refreshStatus, "状态已刷新"));
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

  dom.startMappingButton.addEventListener("click", () =>
    runAction(
      () => sendMission("enter_mapping", { detail: "网页进入建图态" }),
      "已请求进入建图态"
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
      () =>
        sendMission("start_patrol", {
          map_id: state.currentMapId,
          route_id: state.selectedRouteId,
          mode: "single_run",
          detail: "网页启动单次巡航",
        }),
      "已请求启动单次巡航"
    )
  );
  dom.startLoopPatrolButton.addEventListener("click", () =>
    runAction(
      () =>
        sendMission("start_patrol", {
          map_id: state.currentMapId,
          route_id: state.selectedRouteId,
          mode: "loop",
          detail: "网页启动循环巡航",
        }),
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
    runAction(() => apiPost("/api/pump", { enabled: true }), "已发送开泵命令")
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
  await refreshStatus();
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
