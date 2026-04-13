# Leap1 Robot Code

本仓库整理了 Leap1 小车当前使用的两部分代码：

- `firmware/leap_1_v1.1`
  - ESP32 固件源码
  - 已包含低速补偿相关修改
- `ros2_ws/src/leap1`
  - Leap1 的 ROS 2 工作空间源码
  - 已包含单入口启动 `xuegecar_bringup/launch/leap1_stack.launch.py`

## 目录说明

```text
firmware/leap_1_v1.1
ros2_ws/src/leap1
```

## 固件编译

```bash
cd firmware/leap_1_v1.1
pio run
```

## ROS 2 编译

```bash
source /opt/ros/humble/setup.bash
cd ros2_ws
colcon build --packages-select xuegecar_bringup
```

## 单入口启动

```bash
source ~/.bashrc
ros2 launch xuegecar_bringup leap1_stack.launch.py
```

建图模式：

```bash
source ~/.bashrc
ros2 launch xuegecar_bringup leap1_stack.launch.py with_mapping:=true with_rviz:=true
```
