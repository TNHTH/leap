# 树莓派 serial 控制迁移方案

- 创建时间：2026-04-11
- 适用仓库：`/home/gwh/leap`

## 目标链路

- 主控侧：树莓派
- 执行侧：ESP32
- 主传输：USB-C `serial micro-ROS`
- 回退链路：
  - `udp_client`
  - ESP32 原生网页

## 核心判断

- 网页卡顿的主因在网页交互链路，不在底盘 `100 Hz` 控制环。
- 如果要减少网页控制卡顿，最优先方案不是继续改 ESP32 网页，而是：
  - 树莓派承接 Web / 控制节点
  - ESP32 仅做底层执行
- `Serial2` 已被雷达透传占用，不应再承担 micro-ROS。

## 最小可落地方案

1. 树莓派通过 USB-C 直连 ESP32。
2. `micro-ROS agent` 改走 `serial --dev /dev/serial/by-id/* -b 921600`。
3. 浏览器只连树莓派广播中心，不再直接调 ESP32 `/set`。
4. 树莓派后端以 `20 Hz` 持续发布 `/cmd_vel`。
5. ESP32 固件保持：
   - `cmd_vel` watchdog
   - agent 断开自动停车
   - 泵超时自动关断

## 迁移步骤

1. 先保持 `udp` 默认不变，增加 `serial` 可选启动能力。
2. 在树莓派 / 电脑侧验证：
   - agent 可连
   - `/odom` 可收
   - `/cmd_vel` 可控
3. 广播中心接管主控制入口。
4. 验证无回归后，再考虑是否把默认 transport 改成 `serial`。

## 当前仓库支撑点

- `leap1_stack.launch.py`
  - 已支持 `agent_transport:=udp|serial`
- `run_leap1_a20_vehicle.sh`
  - 已按 `serial` 默认启动
- 固件
  - 已支持 `udp_client`
  - 已支持 `serial`
  - 已补 `cmd_vel` watchdog

## 回退方案

- 如果 `serial` 侧异常：
  - 切回 `agent_transport:=udp`
- 如果广播中心故障：
  - 临时回退到 ESP32 原生网页
- 如果树莓派 / 电脑 Web 端异常：
  - 保留 `/pump_cmd` 与最小 ROS 话题调试能力

## 验证步骤

1. 起 serial agent
2. 确认 `/odom`
3. 确认 `/pump_state`
4. 广播中心 `/api/status` 返回 `healthy=true`
5. 长按前进 / 转向时速度平滑
6. 断开 agent 后自动停车

## 与 A20 阶段关系

- 本方案是 A20 项目的底层控制基线。
- 只有这个链路稳定后，地图标注、巡航、火情处置和广播中心才有稳定承载面。
