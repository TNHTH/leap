# leap

`leap` 是 Leap 小车的统一主仓库，用来把原先分散在两个仓库中的内容合并到一起，方便后续协作、评审和发布。

## 仓库目标

- `firmware/leap_1_v1.1`
  - ESP32 固件源码
  - 以已归档、已验证过的整车固件基线为主
- `ros2_ws/src/leap1`
  - Leap 小车 ROS 2 工作空间源码
  - 在 `work` 分支中承接当前仍在持续演进的开发线
- `archives/flashed-firmware`
  - 已烧录固件归档
  - 用于保留可追溯的历史快照

## 分支约定

- `main`
  - 只存放已经确认可用、适合作为稳定基线的代码
  - 不直接堆叠日常试验性改动
- `work`
  - 作为当前开发分支
  - 日常改动、调试、功能迭代默认都在这里进行
  - 验证稳定后，再合并回 `main`

## 目录说明

```text
archives/flashed-firmware
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
