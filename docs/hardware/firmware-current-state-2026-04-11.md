# Leap 固件现状记录

- 创建时间：2026-04-11
- 适用仓库：`/home/gwh/leap`
- 固件目录：`firmware/leap_1_v1.1`
- 记录目的：沉淀当前车载固件结构、关键配置、IO 占用和联调方法，便于后续修改或新会话快速接手。

## 固件职责

- 主控为 ESP32，负责底盘电机控制、编码器采集、IMU、电池检测、OLED 显示、WiFi Web 控制与 micro-ROS 通信。
- 固件与 ROS 2 的主要桥接在 `src/ap_ros_transport.cpp`。
- 底盘闭环控制在 `src/ap_control.cpp`。
- 板级初始化与 Web 控制在 `src/ap_borad_init.cpp`。

## 任务结构

- `transport` 任务
  - 初始化 micro-ROS 传输层。
  - 维护 agent 探测、节点创建、executor spin。
- `control` 任务
  - 100 Hz 控制循环。
  - 更新里程计、编码器、PID、电机输出、电池与显示。
- `wifi` 任务
  - 处理网页控制接口。
- `lidar` 任务
  - 从 UART2 读取雷达数据并通过 UDP 透传。

## 当前主要 ROS / micro-ROS 接口

- 订阅
  - `cmd_vel`
  - `/pump_cmd`
- 发布
  - `odom`
  - `imu`
  - `battery_state`
  - `/pump_state`

## 当前泵控制设计

- 新增时间：2026-04-11
- 目标功能：通过 `IO27` 高电平驱动外接泵，不破坏原有底盘控制与 Web 控制。
- 默认配置：
  - `pump_gpio=27`
  - `pump_active_level=1`
  - `pump_timeout_ms=1500`
- 安全策略：
  - 上电默认关闭泵。
  - ROS 话题控制时，只有 agent 已连接才允许开泵。
  - 网页本地控制时，不依赖 ROS agent，可直接通过同一网页进行抽水。
  - 超时未刷新命令时自动关泵。
  - agent 断开时，只会强制关闭 ROS 控制来源的泵输出，不会打断网页本地控制。

## 当前网页控制入口

- 根页面：`http://机器人IP/`
- 底盘运动接口：
  - `GET /set?vx=<线速度>&vz=<角速度>`
- 泵控制接口：
  - `GET /pump?enabled=1`
  - `GET /pump?enabled=0`
- 状态接口：
  - `GET /status`
- 网页行为：
  - 页面内新增“开启抽水 / 停止抽水”按钮。
  - 网页保持抽水开启时，会每 `500ms` 发送一次保活命令。
  - 若网页断开或网络中断，超过 `pump_timeout_ms` 后会自动关泵。

## 当前仓库内抽水工具

- 位置：
  - `ros2_ws/src/leap1/tools/run_leap1_pump.sh`
  - `ros2_ws/src/leap1/tools/run_leap1_pump.py`
- 用途：
  - 以后需要抽水时，直接运行工具并改参数，不需要再次修改固件代码。
- 示例：

```bash
cd /home/gwh/leap/ros2_ws/src/leap1/tools
./run_leap1_pump.sh --backend http --host 192.168.5.7 --pulse 2.0
./run_leap1_pump.sh --backend ros --pulse 1.5
./run_leap1_pump.sh --backend http --on
./run_leap1_pump.sh --backend http --off
```

## 重要 IO 占用

- 电机驱动
  - 左电机：`GPIO22`、`GPIO23`
  - 右电机：`GPIO12`、`GPIO13`
- 编码器
  - 电机 0：`GPIO32`、`GPIO33`
  - 电机 1：`GPIO26`、`GPIO25`
- IMU / OLED I2C
  - `GPIO18`、`GPIO19`
- 电池采样
  - `GPIO34`
- 泵控制
  - `GPIO27`
- 预留/历史宏
  - `CONFIG_DEFAULT_ULTRASONIC_TRIG_GPIO` 仍定义为 `27`，但当前代码未实际启用超声波业务逻辑，因此本次将 `GPIO27` 复用于泵控制。

## 2026-04-11 电脑直连联调增量结论

- 当前电脑连接 WiFi：`Redmi K70 Pro`。
- 当前电脑 IPv4：`10.127.143.124`。
- 当前车端 NVS 仍保留旧网络参数：
  - `wifi_ssid=TNHTH`
  - `wifi_pswd` 已配置，但不在仓库文档中明文记录
  - `udpserver_ip=192.168.5.17`
- 已通过串口命令把 `microros_mode` 写为 `serial` 并重启板子。
- 重新联调后，micro-ROS agent 已打印 `create_client` 和 `session established`，说明 ESP32 与主机 serial XRCE 会话已经建立。
- 但截至 2026-04-11，ROS 图里 `odom / battery_state / pump_state` 仍然是 `Publisher count = 0`，说明问题已收敛到 ESP32 在会话建立后的 `rclc` 实体创建阶段，而不是 host 侧 launch 或 agent 拉起阶段。
- 已把 `create_transport()` 从“软失败继续”改成“按 stage 明确失败返回”，后续下一轮联调可直接看到卡在 `rcl_init_options_init / rclc_support_init_with_options / publisher_init / executor_add_*` 的哪一步。

## 当前已知运行约束

- 当前仓库默认固件配置常量里 `microros_mode` 仍是 `udp_client`，但实际运行值可能由 NVS 中的历史配置覆盖。
- 如果 micro-ROS 走 USB 串口，同一个串口不能再同时被配置解析逻辑抢读，否则可能导致 XRCE-DDS 数据流被破坏。
- `Serial2` 仍被雷达透传任务占用；本次泵控制使用 `GPIO27`，不占用 `GPIO16/17`。

## 关键源码入口

- 固件主入口：`firmware/leap_1_v1.1/src/main.cpp`
- 任务创建：`firmware/leap_1_v1.1/src/tasks.cpp`
- 全局对象：`firmware/leap_1_v1.1/src/ap_global.cpp`
- 运动控制：`firmware/leap_1_v1.1/src/ap_control.cpp`
- 板级初始化：`firmware/leap_1_v1.1/src/ap_borad_init.cpp`
- ROS 传输：`firmware/leap_1_v1.1/src/ap_ros_transport.cpp`
- 参数存储：`firmware/leap_1_v1.1/lib/AP_Config/ap_config.cpp`

## 常用命令

```bash
cd /home/gwh/leap/firmware/leap_1_v1.1
pio run
pio run -t upload --upload-port /dev/ttyUSB0
```

```bash
docker run --rm --net=host --device=/dev/ttyUSB0 \
  registry.cn-hangzhou.aliyuncs.com/fishros/micro-ros-agent:humble \
  serial --dev /dev/ttyUSB0 -b 921600 -v6
```

```bash
source /opt/ros/humble/setup.bash
ros2 topic list
ros2 topic pub --once /pump_cmd std_msgs/msg/Bool "{data: true}"
ros2 topic pub --once /pump_cmd std_msgs/msg/Bool "{data: false}"
ros2 topic echo /pump_state
```

## 后续修改建议

- 若后续要恢复超声波功能，先重新分配 `GPIO27`，不要直接与泵控制共用。
- 若需要把泵控制做成长期能力，建议后续在 ROS 2 工作空间中补一个最小测试节点或 launch 内可选测试工具。
