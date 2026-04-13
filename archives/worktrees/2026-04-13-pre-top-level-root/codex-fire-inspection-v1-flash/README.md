# Leap1 Robot Code

`leap1-robot-code` 现包含 Leap1 底盘固件、ROS 2 工作区，以及消防巡检车 V1 所需的自动识别与自动喷水链路。

## 目录

- `firmware/leap_1_v1.1`
  - ESP32 固件
  - USB-C 串口作为 micro-ROS 主链路
  - 保留 WiFi 雷达 UDP 桥
- `ros2_ws/src/leap1`
  - Leap1 ROS 2 工作区
  - `xuegecar_bringup/launch/fire_stack.launch.py` 为消防模式统一入口
  - `xuegecar_fire_inspection` 为 RGB 相机、火焰检测、巡检状态机和泵控守护

## 固件编译

```bash
cd firmware/leap_1_v1.1
pio run
```

## ROS 2 依赖

Ubuntu 22.04 / ROS 2 Humble 建议安装：

```bash
sudo apt update
sudo apt install -y \
  python3-colcon-common-extensions \
  python3-opencv \
  ros-humble-cv-bridge \
  ros-humble-nav2-bringup \
  ros-humble-nav2-msgs \
  ros-humble-rviz2 \
  ros-humble-joint-state-publisher \
  ros-humble-robot-state-publisher \
  ros-humble-ydlidar-ros2-driver
```

## ROS 2 编译

```bash
source /opt/ros/humble/setup.bash
cd ros2_ws
colcon build --packages-select xuegecar_bringup xuegecar_navigation2 xuegecar_fire_inspection
source install/setup.bash
```

## 消防模式启动

```bash
source /opt/ros/humble/setup.bash
cd ros2_ws
source install/setup.bash
ros2 launch xuegecar_bringup fire_stack.launch.py
```

常用参数：

```bash
ros2 launch xuegecar_bringup fire_stack.launch.py \
  with_mapping:=false \
  with_rviz:=true \
  fire_params_file:=/absolute/path/to/fire_inspection.yaml
```

## 视频查看

默认 MJPEG 视频流地址：

```text
http://<raspberry-pi-ip>:8090/stream
```

## 关键链路说明

- ESP32 侧 `transport_mode=serial` 时，USB-C `Serial` 固定为 micro-ROS 主链路。
- 文本配置解析不再与 `Serial` 主链路复用，避免吞掉 XRCE-DDS 二进制流。
- `GPIO16` 固定为水泵控制脚，`pump_active_level=1` 表示高电平开泵。
- `serial_id=2` 在消防模式下不再作为 micro-ROS 传输口使用。
- WiFi 仍用于雷达 UDP 桥，目标端口为 `8889`。
- 板载 HTTP 控车页面默认关闭，只有显式启用 `web_control_enabled` 才会开放。

## 安全说明

- 固件上电默认关泵。
- agent 断开、串口断开、ESP32 重启、命令超时、状态切换时，固件都会强制关泵并停车。
- `pump_guard_node` 会在巡检管理节点心跳丢失时兜底发布 `/pump_cmd=false` 与零速 `/cmd_vel`。
- `xuegecar_fire_inspection.launch.py` 中任一关键节点退出时，会触发整个消防模式停机。

## 主要参数文件

- 底盘/系统消防参数：
  - `ros2_ws/src/leap1/xuegecar_bringup/config/fire_inspection.yaml`
- 消防包默认参数：
  - `ros2_ws/src/leap1/xuegecar_fire_inspection/config/fire_inspection.yaml`

根据现场环境，优先调整以下参数：

- `min_fire_area`
- `required_consecutive_detections`
- `clear_frames`
- `spray_duration_sec`
- `cooldown_sec`
- `waypoints_x / waypoints_y / waypoints_yaw_deg`
