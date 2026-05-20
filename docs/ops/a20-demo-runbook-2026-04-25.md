---
title: A20 比赛演示 Runbook
created: 2026-04-25
type: operation-runbook
status: implemented
---

# A20 比赛演示 Runbook

## 结论

比赛演示按“先保安全、再起底盘、再起感知与广播中心、最后触发闭环”的顺序执行。任何异常情况下先停泵停底盘，再排查 Agent、雷达、相机和 Web 面板。

## 启动前检查

1. 小车上电后水泵默认关闭。
2. 轮子悬空或地面安全区域内确认 `/cmd_vel` 超时停车有效。
3. 主机和车端处于同一网络，或 serial micro-ROS Agent 已可用。
4. 雷达默认 PTY 为 `/tmp/lidar`；如现场已配置 udev，可使用 `/dev/lidar`。
5. A20 runtime 目录可写，默认由程序创建。

## 标准启动

```bash
source /opt/ros/humble/setup.bash
cd /home/gwh/leap/ros2_ws
source install/setup.bash
ros2 launch xuegecar_bringup leap1_stack.launch.py \
  with_a20_stack:=true \
  with_vehicle_web_teleop:=true \
  with_rviz:=true
```

实车严格联动模式下，如果希望 Agent 或雷达桥接退出时整套 Launch 立即关闭，可追加：

```bash
shutdown_on_agent_exit:=true shutdown_on_lidar_bridge_exit:=true
```

打开广播中心：

```text
http://127.0.0.1:8090/
```

## 降级启动

当 Docker Agent 或 socat 已由外部进程托管时，只启动 ROS2 和 A20 层：

```bash
ros2 launch xuegecar_bringup leap1_stack.launch.py \
  start_agent:=false \
  start_lidar_bridge:=false \
  with_a20_stack:=true \
  with_vehicle_web_teleop:=true
```

当本机已安装 native micro-ROS Agent，希望避免 Docker：

```bash
ros2 launch xuegecar_bringup leap1_stack.launch.py \
  agent_backend:=native \
  agent_transport:=udp
```

## 演示流程

1. 确认广播中心系统状态：odom、雷达、相机、感知、安全守护。
2. 启动巡航或手动展示小车可控运动。
3. 触发模拟火情或启用 `with_flame_detector:=true`。
4. 观察状态机进入发现火情、停车、喷水、冷却、恢复。
5. 广播中心展示事件日志、当前状态、水泵状态和相机状态。
6. 执行一次急停或停止命令，证明异常可控。

## 快速排查

- 看不到 odom：检查 micro-ROS Agent、ESP32 NVS 传输模式、`/odom` publisher count。
- 雷达无 scan：检查 `socat`、`lidar_link`、UDP 8889、雷达供电。
- Web 无画面：检查 `leap1_a20` 是否启动、端口 8090/8091/8092 是否被占用。
- 水泵不动作：检查 `/pump_cmd`、`/pump_state`、任务状态是否允许喷水、固件 `pump_timeout_ms`。
- Agent 抖动：使用 `start_agent:=false`，手动拉起 Agent 后再启动 ROS2 栈。
- 严格安全演示：使用 `shutdown_on_agent_exit:=true shutdown_on_lidar_bridge_exit:=true`，并现场验证固件 500ms `/cmd_vel` 超时停车。
