const state = {
  status: null,
  currentMapId: "",
  annotations: { map_id: "", zones: [], waypoints: [], routes: [] },
  selectedRouteId: "",
  drawingRect: null,
  teleopTimer: null,
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
    "frontCameraState",
    "frontCameraImage",
    "groundCameraState",
    "groundCameraImage",
    "mapSelect",
    "loadMapButton",
    "mapImage",
    "mapCanvas",
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

function appendLog(text) {
  const stamp = new Date().toLocaleTimeString();
  dom.logOutput.textContent = `[${stamp}] ${text}\n${dom.logOutput.textContent}`.slice(0, 5000);
}

function resolveCameraUrl(camera, fallbackPort) {
  const port = camera?.mjpeg_port || fallbackPort;
  return `http://${window.location.hostname}:${port}/stream`;
}

function syncMapOptions() {
  const maps = state.status?.maps || [];
  dom.mapSelect.innerHTML = "";
  maps.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.map_id;
    option.textContent = `${item.map_id} · zones ${item.zone_count} · routes ${item.route_count}`;
    dom.mapSelect.appendChild(option);
  });
  if (!state.currentMapId && maps.length > 0) {
    state.currentMapId = maps[0].map_id;
  }
  if (state.currentMapId) {
    dom.mapSelect.value = state.currentMapId;
  }
}

function refreshStatusView() {
  if (!state.status) {
    return;
  }
  const mission = state.status.mission || {};
  const battery = state.status.battery || {};
  const odom = state.status.odom || {};
  const cameras = state.status.cameras || {};

  dom.missionState.textContent = mission.state || "BOOT";
  dom.faultCode.textContent = mission.fault_code || "-";
  dom.pumpState.textContent = state.status.pump_state ? "ON" : "OFF";
  dom.missionDetail.textContent = mission.detail || "-";
  dom.batteryVoltage.textContent = battery.voltage ? `${battery.voltage.toFixed(2)} V` : "-";
  dom.odomPose.textContent = odom.x !== undefined ? `${odom.x.toFixed(2)}, ${odom.y.toFixed(2)}` : "-";
  dom.odomTwist.textContent =
    odom.linear_x !== undefined ? `${odom.linear_x.toFixed(2)} / ${odom.angular_z.toFixed(2)}` : "-";
  dom.currentMapId.textContent = mission.map_id || "-";
  dom.currentRouteId.textContent = mission.route_id || state.selectedRouteId || "-";

  const frontCamera = cameras.vehicle_camera || cameras.front_camera;
  const groundCamera = cameras.ground_camera;
  dom.frontCameraState.textContent = frontCamera?.online ? "online" : "offline";
  dom.groundCameraState.textContent = groundCamera?.online ? "online" : "offline";
  dom.frontCameraImage.src = resolveCameraUrl(frontCamera, 8091);
  dom.groundCameraImage.src = resolveCameraUrl(groundCamera, 8092);

  const logs = (state.status.logs || []).map((item) => `[${item.updated_at}] ${item.level}: ${item.message}`);
  dom.logOutput.textContent = logs.join("\n") || "暂无日志";
  syncMapOptions();
  refreshRouteSummary();
}

async function refreshStatus() {
  state.status = await apiGet("/api/status");
  refreshStatusView();
}

async function loadMap(mapId) {
  if (!mapId) return;
  state.currentMapId = mapId;
  state.annotations = await apiGet(`/api/maps/${mapId}/annotations`);
  state.annotations.map_id = mapId;
  state.selectedRouteId = state.annotations.routes?.[0]?.id || "";
  refreshWaypointOptions();
  dom.mapImage.onload = () => {
    resizeCanvas();
    renderMapOverlay();
  };
  dom.mapImage.src = `/api/maps/${mapId}/map?ts=${Date.now()}`;
}

function resizeCanvas() {
  const rect = dom.mapImage.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) return;
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
  const routes = state.annotations.routes || [];
  if (!routes.length) {
    dom.routeSummary.textContent = "当前地图尚未保存 route。";
    return;
  }
  dom.routeSummary.textContent = routes
    .map((route) => `${route.name} [${route.mode}] -> ${route.waypoint_ids.join(", ")}`)
    .join("\n");
}

function renderMapOverlay() {
  const ctx = dom.mapCanvas.getContext("2d");
  ctx.clearRect(0, 0, dom.mapCanvas.width, dom.mapCanvas.height);

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
    if (!state.currentMapId || dom.toolSelect.value === "waypoint") return;
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
    if (!state.currentMapId) return;
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
      renderMapOverlay();
      return;
    }

    if (!state.drawingRect) return;
    const start = canvasToImage(
      dom.mapCanvas.getBoundingClientRect().left + state.drawingRect.x,
      dom.mapCanvas.getBoundingClientRect().top + state.drawingRect.y
    );
    const end = canvasToImage(
      dom.mapCanvas.getBoundingClientRect().left + state.drawingRect.x + state.drawingRect.width,
      dom.mapCanvas.getBoundingClientRect().top + state.drawingRect.y + state.drawingRect.height
    );
    state.annotations.zones.push(buildRectangleZone(start, end, dom.toolSelect.value));
    state.drawingRect = null;
    renderMapOverlay();
  });
}

async function saveAnnotations() {
  if (!state.currentMapId) {
    appendLog("请先加载地图。");
    return;
  }
  const result = await apiPost("/api/maps/annotations", {
    map_id: state.currentMapId,
    annotations: state.annotations,
  });
  appendLog(`标注已保存，keepout 生成于 ${result.keepout.keepout_yaml}`);
  await refreshStatus();
}

function saveRoute() {
  const waypointIds = Array.from(dom.routeWaypointSelect.selectedOptions).map((option) => option.value);
  if (!waypointIds.length) {
    appendLog("请至少选择一个 waypoint。");
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
}

async function sendMission(command, extra = {}) {
  await apiPost("/api/mission", { command, ...extra });
  appendLog(`任务命令已发送: ${command}`);
}

function bindTeleopButton(button) {
  const vx = Number(button.dataset.vx || 0);
  const vz = Number(button.dataset.vz || 0);
  const start = async () => {
    clearInterval(state.teleopTimer);
    await apiPost("/api/cmd_vel", { vx, vz });
    state.teleopTimer = setInterval(() => {
      apiPost("/api/cmd_vel", { vx, vz }).catch(console.error);
    }, 120);
  };
  const stop = async () => {
    clearInterval(state.teleopTimer);
    await apiPost("/api/stop");
  };
  button.addEventListener("pointerdown", start);
  button.addEventListener("pointerup", stop);
  button.addEventListener("pointerleave", stop);
}

function installActions() {
  dom.refreshButton.addEventListener("click", refreshStatus);
  dom.loadMapButton.addEventListener("click", () => loadMap(dom.mapSelect.value));
  dom.saveAnnotationsButton.addEventListener("click", saveAnnotations);
  dom.saveRouteButton.addEventListener("click", saveRoute);

  dom.startMappingButton.addEventListener("click", () =>
    sendMission("enter_mapping", { detail: "网页进入建图态" })
  );
  dom.enterAnnotationButton.addEventListener("click", () =>
    sendMission("start_annotation", { map_id: state.currentMapId, detail: "网页进入标注态" })
  );
  dom.missionReadyButton.addEventListener("click", () =>
    sendMission("mission_ready", {
      map_id: state.currentMapId,
      route_id: state.selectedRouteId,
      detail: "网页标注完成，任务就绪",
    })
  );
  dom.startSinglePatrolButton.addEventListener("click", () =>
    sendMission("start_patrol", {
      map_id: state.currentMapId,
      route_id: state.selectedRouteId,
      mode: "single_run",
      detail: "网页启动单次巡航",
    })
  );
  dom.startLoopPatrolButton.addEventListener("click", () =>
    sendMission("start_patrol", {
      map_id: state.currentMapId,
      route_id: state.selectedRouteId,
      mode: "loop",
      detail: "网页启动循环巡航",
    })
  );
  dom.stopPatrolButton.addEventListener("click", () =>
    sendMission("stop_patrol", { detail: "网页要求停止巡航" })
  );

  dom.triggerFireButton.addEventListener("click", () =>
    apiPost("/api/fire", {
      active: true,
      source: "web_panel",
      camera_id: "manual",
      level: "warning",
      description: "网页手动触发火情",
    })
  );
  dom.clearFireButton.addEventListener("click", () =>
    apiPost("/api/fire", {
      active: false,
      source: "web_panel",
      camera_id: "manual",
      level: "info",
      description: "网页手动清除火情",
    })
  );

  dom.saveMapButton.addEventListener("click", async () => {
    const mapId = window.prompt("保存地图 ID", state.currentMapId || `map_${Date.now()}`);
    if (!mapId) return;
    const result = await apiPost("/api/maps/save", { map_id: mapId });
    appendLog(`地图已保存: ${result.map_id}`);
    await refreshStatus();
    await loadMap(result.map_id);
  });

  dom.pumpOnButton.addEventListener("click", () => apiPost("/api/pump", { enabled: true }));
  dom.pumpOffButton.addEventListener("click", () => apiPost("/api/pump", { enabled: false }));
  dom.stopButton.addEventListener("click", () => apiPost("/api/stop"));

  document.querySelectorAll(".teleop-btn[data-vx]").forEach(bindTeleopButton);
}

async function boot() {
  initDom();
  installMapInteractions();
  installActions();
  await refreshStatus();
  if (state.currentMapId) {
    await loadMap(state.currentMapId);
  }
  window.addEventListener("resize", () => {
    resizeCanvas();
    renderMapOverlay();
  });
  setInterval(() => refreshStatus().catch((error) => appendLog(error.message)), 1000);
}

window.addEventListener("DOMContentLoaded", boot);
