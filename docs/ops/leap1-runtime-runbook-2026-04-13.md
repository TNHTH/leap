# Leap1 运行手册

- 创建时间：2026-04-13
- 适用仓库：`/home/gwh/leap`
- 适用范围：新入口脚本、center/vehicle 角色拆分、systemd 模板安装、preflight 检查
- 约束：本文只描述运行与部署入口，不涉及源码修改

## 结论

- `center` 和 `vehicle` 已拆成两个独立运行角色：
  - `center` 负责广播中心 Web 面板与固定摄像头桥接。
  - `vehicle` 负责 micro-ROS 串口链路、底盘 ROS 运行态、A20 任务节点与车载相机。
- 推荐部署方式：
  1. 先执行 `run_leap1_preflight.sh` 检查环境。
  2. 常驻场景用 `deploy/systemd/` 下的模板安装服务。
  3. 按角色分别启 `leap1-microros-agent.service`、`leap1-vehicle-runtime.service`、`leap1-center-console.service`。

## 目录与入口

- systemd 模板目录：`/home/gwh/leap/deploy/systemd/`
- 工具脚本目录：`/home/gwh/leap/ros2_ws/src/leap1/tools/`
- 主要入口脚本：
  - `run_leap1_preflight.sh`
  - `run_leap1_microros_agent.sh`
  - `run_leap1_vehicle_runtime.sh`
  - `run_leap1_patrol_runtime.sh`
  - `run_leap1_center_console.sh`
  - `run_leap1_control_stack.sh`

## 一键入口

- 单命令统一启动入口：
  - `/home/gwh/leap/ros2_ws/src/leap1/tools/run_leap1_control_stack.sh`
- 默认行为：
  1. SSH 检查树莓派连通性
  2. 远端优先用 systemd 启动 `leap1-microros-agent.service`
  3. 启动树莓派 `vehicle` 或 `patrol` 运行态
  4. 本地后台启动广播中心网页
  5. 等待 `http://127.0.0.1:8090/` 就绪并尝试打开浏览器
- 常用示例：

```bash
cd /home/gwh/leap/ros2_ws/src/leap1/tools
./run_leap1_control_stack.sh
./run_leap1_control_stack.sh --remote-mode patrol
./run_leap1_control_stack.sh --remote-host leap@10.127.143.229 --no-open
```

## 角色划分

### center 角色

- 入口脚本：`/home/gwh/leap/ros2_ws/src/leap1/tools/run_leap1_center_console.sh`
- 对应 launch：`ros2 launch leap1_a20 a20_center.launch.py`
- 负责内容：
  - 启动广播中心 Web 面板
  - 提供状态接口与静态页面
  - 可选启动固定摄像头桥接与 MJPEG 输出
- 默认环境变量：
  - `LEAP1_A20_RUNTIME_ROOT`
  - `LEAP1_A20_WEB_PORT=8090`
  - `LEAP1_PANEL_MODE=status_only`
  - `LEAP1_EXPECTED_VEHICLE_CAMERA=true`
  - `LEAP1_WITH_GROUND_CAMERA=false`
  - `LEAP1_GROUND_CAMERA_DEVICE=`
  - `LEAP1_GROUND_CAMERA_PORT=8092`
  - `LEAP1_A20_TOPIC_PREFIX=/a20`

### vehicle 角色

- 入口脚本：`/home/gwh/leap/ros2_ws/src/leap1/tools/run_leap1_vehicle_runtime.sh`
- 对应 launch：`run_leap1_stack.sh backend:=real`
- 负责内容：
  - 接入 external serial micro-ROS agent
  - 启动车端 ROS 运行态
  - 启动 A20 车端任务节点
  - 启动车载相机桥接
- 默认环境变量：
  - `LEAP1_AGENT_TRANSPORT=external_serial`
  - `LEAP1_AGENT_SERIAL_DEV=/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0`
  - `LEAP1_AGENT_SERIAL_BAUD=921600`
  - `LEAP1_WITH_A20_STACK=true`
  - `LEAP1_WITH_WEB_TELEOP=false`
  - `LEAP1_WITH_KEEPOUT_FILTER=false`
  - `LEAP1_WITH_VEHICLE_CAMERA=true`
  - `LEAP1_VEHICLE_CAMERA_DEVICE=/dev/video0`
  - `LEAP1_A20_WEB_PORT=8090`
  - `LEAP1_A20_TOPIC_PREFIX=/a20`

### patrol 角色

- 入口脚本：`/home/gwh/leap/ros2_ws/src/leap1/tools/run_leap1_patrol_runtime.sh`
- 用途：在 `vehicle` 基础上打开巡航运行参数。
- 与 `vehicle` 的主要差异：
  - `LEAP1_WITH_KEEPOUT_FILTER=true`
  - `with_mapping:=false`
  - `with_navigation:=true`
  - `with_rviz:=false`

## Preflight 用法

### 检查项

- 命令存在：
  - `ros2`
  - `python3`
  - `socat`，仅 `vehicle/mapping/patrol` 模式强制要求
- 设备存在性：
  - `LEAP1_AGENT_SERIAL_DEV`
  - `LEAP1_VEHICLE_CAMERA_DEVICE`
  - `LEAP1_GROUND_CAMERA_DEVICE`
- 用户组提示：
  - 若当前用户不在 `docker` 组，会输出警告，但不会直接失败

### 基本执行

```bash
cd /home/gwh/leap/ros2_ws/src/leap1/tools
./run_leap1_preflight.sh
```

### 模式化执行

```bash
LEAP1_PREFLIGHT_MODE=vehicle ./run_leap1_preflight.sh
LEAP1_PREFLIGHT_MODE=center ./run_leap1_preflight.sh
```

### 带设备参数执行

```bash
export LEAP1_AGENT_SERIAL_DEV=/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0
export LEAP1_VEHICLE_CAMERA_DEVICE=/dev/video0
export LEAP1_GROUND_CAMERA_DEVICE=/dev/video2
/home/gwh/leap/ros2_ws/src/leap1/tools/run_leap1_preflight.sh
```

### 判定规则

- 输出 `[Preflight] PASS` 才进入后续启动。
- 遇到 `[Preflight] FAIL:` 先修复环境，再重试。

## 手工启动顺序

### 1. 启 micro-ROS agent

```bash
export MICROROS_WS_ROOT=/home/gwh/microros_ws
export MICROROS_AGENT_DEV=/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0
export MICROROS_AGENT_BAUD=921600
/home/gwh/leap/ros2_ws/src/leap1/tools/run_leap1_microros_agent.sh
```

### 2. 启动车端运行态

```bash
export LEAP1_AGENT_SERIAL_DEV=/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0
export LEAP1_VEHICLE_CAMERA_DEVICE=/dev/video0
/home/gwh/leap/ros2_ws/src/leap1/tools/run_leap1_vehicle_runtime.sh
```

### 3. 启动中心控制台

```bash
export LEAP1_A20_RUNTIME_ROOT=/home/gwh/leap/runtime/a20
export LEAP1_GROUND_CAMERA_DEVICE=/dev/video2
export LEAP1_WITH_GROUND_CAMERA=true
/home/gwh/leap/ros2_ws/src/leap1/tools/run_leap1_center_console.sh
```

### 4. 巡航场景替代入口

```bash
export LEAP1_AGENT_SERIAL_DEV=/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0
export LEAP1_VEHICLE_CAMERA_DEVICE=/dev/video0
/home/gwh/leap/ros2_ws/src/leap1/tools/run_leap1_patrol_runtime.sh
```

## 2026-04-13 调试边界

- 电脑段调试模式只用于把 ESP32 固件、雷达 UDP 和泵控制先调稳。
- 最终正式控制链仍然是：
  - ESP32 接回树莓派串口
  - 树莓派本机运行 `leap1-microros-agent.service`
  - 树莓派本机运行 `leap1-vehicle-runtime.service`
- `external_serial` 只保留给临时联调场景：
  - 例如 ESP32 暂时接在电脑上刷固件
  - 树莓派只负责接收雷达 UDP 或验证 ROS 图可见性
- `run_leap1_preflight.sh` 已兼容 `LEAP1_AGENT_TRANSPORT=external_serial`，在该模式下会跳过“本机必须存在串口设备”的错误检查。

## 雷达验收

- 2026-04-13 当前已确认：
  - ESP32 在热点网络内会持续发送 `UDP 8889` 雷达报文。
  - 树莓派可抓到 `10.127.143.212 -> 10.127.143.255:8889` 的 `aa55...` 数据。
  - 树莓派可通过 `socat` 把 UDP 桥到 `${LEAP1_LIDAR_LINK:-/tmp/lidar}`。
  - `ydlidar_ros2_driver` 在隔离环境下能成功发布 `/scan`。
- 推荐直接用新增脚本做验收：

```bash
cd /home/leap/leap/ros2_ws/src/leap1/tools
./run_leap1_lidar_udp_acceptance.sh
```

- 如需指定自定义参数，可覆盖：
  - `LEAP1_LIDAR_LINK`
  - `LEAP1_LIDAR_UDP_PORT`
  - `LEAP1_LIDAR_ACCEPTANCE_DOMAIN_ID`
  - `LEAP1_LIDAR_ACCEPTANCE_WAIT_SEC`

## 泵控验收

- 2026-04-13 已确认：
  - ESP32 本机 HTTP 接口 `GET /pump?enabled=1|0` 能切换状态。
  - `GET /status` 返回的 `pump` 字段能跟随变化。
  - 现场已肉眼确认物理水泵被正常驱动。
- 电脑段调试时可直接访问板载 HTTP 接口：

```bash
curl -s http://10.127.143.212/status
curl -s 'http://10.127.143.212/pump?enabled=1'
curl -s 'http://10.127.143.212/pump?enabled=0'
```

- 最终回插树莓派后，再用 ROS 侧 `/pump_cmd` 与 `/pump_state` 做整车联调验收。

## systemd 部署

### 模板文件

- `/home/gwh/leap/deploy/systemd/leap1-microros-agent.service`
- `/home/gwh/leap/deploy/systemd/leap1-vehicle-runtime.service`
- `/home/gwh/leap/deploy/systemd/leap1-center-console.service`

### 安装模板

安装脚本会把模板中的 `__LEAP_USER__` 替换成指定 Linux 用户，并写入 `/etc/systemd/system/`。

```bash
cd /home/gwh/leap/deploy/systemd
./install_services.sh leap
```

如果实际用户名不是 `leap`，把上面参数替换为目标用户名。

### 启用服务

```bash
sudo systemctl enable --now leap1-microros-agent.service
sudo systemctl enable --now leap1-vehicle-runtime.service
sudo systemctl enable --now leap1-center-console.service
```

### 建议启动顺序

1. `leap1-microros-agent.service`
2. `leap1-vehicle-runtime.service`
3. `leap1-center-console.service`

说明：

- `leap1-vehicle-runtime.service` 的 unit 已声明 `After=` 和 `Wants=` 指向 `leap1-microros-agent.service`。
- `leap1-center-console.service` 不依赖底盘节点先启动，但面板健康状态会受车端在线情况影响。

### 查看状态与日志

```bash
systemctl status leap1-microros-agent.service
systemctl status leap1-vehicle-runtime.service
systemctl status leap1-center-console.service
```

```bash
journalctl -u leap1-microros-agent.service -f
journalctl -u leap1-vehicle-runtime.service -f
journalctl -u leap1-center-console.service -f
```

## 服务默认参数总览

### leap1-microros-agent.service

- 工作目录：`/home/<user>`
- 关键环境变量：
  - `MICROROS_WS_ROOT=/home/<user>/microros_ws`
  - `MICROROS_AGENT_DEV=/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0`
  - `MICROROS_AGENT_BAUD=921600`
  - `MICROROS_AGENT_VERBOSITY=6`

### leap1-vehicle-runtime.service

- 工作目录：`/home/<user>/leap/ros2_ws`
- 关键环境变量：
  - `LEAP1_AGENT_TRANSPORT=external_serial`
  - `LEAP1_AGENT_SERIAL_DEV=/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0`
  - `LEAP1_AGENT_SERIAL_BAUD=921600`
  - `LEAP1_WITH_VEHICLE_CAMERA=true`
  - `LEAP1_VEHICLE_CAMERA_DEVICE=/dev/video0`
  - `LEAP1_A20_RUNTIME_ROOT=/home/<user>/leap/runtime/a20`

### leap1-center-console.service

- 工作目录：`/home/<user>/leap/ros2_ws`
- 关键环境变量：
  - `LEAP1_A20_RUNTIME_ROOT=/home/<user>/leap/runtime/a20`
  - `LEAP1_A20_WEB_PORT=8090`
  - `LEAP1_PANEL_MODE=status_only`
  - `LEAP1_EXPECTED_VEHICLE_CAMERA=true`
  - `LEAP1_WITH_GROUND_CAMERA=false`
  - `LEAP1_GROUND_CAMERA_DEVICE=`

## 最小验收命令

### 面板与状态

```bash
curl -s http://127.0.0.1:8090/api/status
```

预期至少能看到：

- `healthy=true`
- `state`
- 车载相机在线状态字段

### 车载相机快照

```bash
curl -I http://127.0.0.1:8091/snapshot.jpg
```

### 固定摄像头快照

```bash
curl -I http://127.0.0.1:8092/snapshot.jpg
```

### A20 冒烟验收脚本

```bash
cd /home/gwh/leap/ros2_ws/src/leap1/tools
./run_leap1_a20_smoke_acceptance.sh
```

说明：

- 该脚本会检查核心文件、关键 topic 和中心端 HTTP 接口。
- 若当前 ROS 图或面板未启动，脚本会按预期失败。

### ROS 话题

```bash
ros2 topic echo --once /odom
ros2 topic echo --once /battery_state
```

## 常见故障定位

### preflight 失败

- 缺 `ros2`、`python3`、`socat`：
  - 先补依赖，再重跑 preflight。
- 串口或相机设备不存在：
  - 先确认 `/dev/serial/by-id/*` 和 `/dev/video*` 实际编号，再覆盖环境变量。

### vehicle 起不来

- 先看 `journalctl -u leap1-microros-agent.service -f` 是否已经建立 serial 会话。
- 再看 `journalctl -u leap1-vehicle-runtime.service -f` 是否卡在 launch 参数或设备缺失。

### center 面板异常

- 先确认 `leap1-center-console.service` 已绑定 `8090`。
- 若固定摄像头未接入，可临时设置：

```bash
export LEAP1_WITH_GROUND_CAMERA=false
```

### 设备号变化

- 不要改源码。
- 直接通过环境变量或 systemd 模板中的 `Environment=` 覆盖设备路径。

## 推荐执行方案

### 调试场景

1. 手工执行 `run_leap1_preflight.sh`
2. 手工执行 `run_leap1_microros_agent.sh`
3. 手工执行 `run_leap1_vehicle_runtime.sh`
4. 手工执行 `run_leap1_center_console.sh`

### 常驻场景

1. 用 `install_services.sh <linux-user>` 安装模板
2. `enable --now` 三个服务
3. 用 `systemctl status` 与 `journalctl -f` 做首轮验收
