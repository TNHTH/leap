# Leap 树莓派 TF 卡部署设计

- 创建时间：2026-04-11
- 适用仓库：`/home/gwh/leap`
- 工作分支：`codex/leap-pi-bootstrap`

## 目标

- 把当前接入主机的 TF 卡制作成可用于 Leap 小车的树莓派系统卡。
- 系统首选 `Ubuntu Server 22.04.5 arm64`，以匹配当前仓库固定的：
  - `ROS 2 Humble`
  - `/opt/ros/humble`
  - `Python 3.10`
- 首启后自动完成：
  - SSH 接入
  - 网络配置
  - ROS 2 Humble 安装
  - Docker / `socat` / OpenCV / NumPy / YAML 运行依赖安装
  - Leap ROS 2 工作空间构建
  - `leap1-a20.service` 开机启动配置

## 已确认事实

- 当前 TF 卡设备：`/dev/sda`
- 当前 TF 卡分区：仅 `1` 个 `FAT32` 分区，根目录为空，不是可直接继续增量配置的树莓派系统卡。
- Leap 当前车载链路已经固定为：
  - 树莓派主控
  - ESP32 执行
  - `serial micro-ROS`
  - 雷达 UDP 转发 + `socat`
  - 车载相机 `/dev/video0`
  - A20 Web 面板默认端口 `8090`

## 设计决策

### 1. 镜像来源

- 使用 Ubuntu 官方镜像：
  - `ubuntu-22.04.5-preinstalled-server-arm64+raspi.img.xz`
- 使用 Ubuntu 官方 `SHA256SUMS` 做校验。

### 2. 首启配置策略

- 不依赖 Raspberry Pi Imager GUI。
- 直接在 Linux 主机上完成：
  - 镜像下载
  - 校验
  - `dd` 刷写
  - cloud-init 注入
  - 本地 Leap 仓库快照拷入 rootfs
- 这样可以避免：
  - GitHub 私有仓库凭据问题
  - 首启后再手动复制代码
  - 刷卡工具版本差异

### 3. 代码下发策略

- 不让树莓派首启去 `git clone`。
- 直接把本机的 Leap 仓库必要内容拷入：
  - `README.md`
  - `AGENTS.md`
  - `docs/`
  - `deploy/raspi/`
  - `ros2_ws/`
- 不拷贝 `.git`、`build/`、`install/`、`log/`、`.tmp/` 等临时内容。

### 4. 服务化策略

- 首启执行一次 `install_leap1_pi.sh`。
- 完成依赖安装和构建后，注册：
  - `leap1-a20.service`
- 该服务负责拉起：
  - `run_leap1_a20_vehicle.sh`
- 默认控制参数：
  - `agent_transport=serial`
  - `agent_serial_dev=/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0`
  - `agent_serial_baud=921600`
  - `vehicle_camera_device=/dev/video0`
  - `web_port=8090`

## 风险与取舍

- Wi-Fi 密码无法从当前主机自动恢复，因此刷卡前仍需用户提供目标 Wi-Fi 密码，或者改为有线首启。
- 如果树莓派型号过旧且不支持 `Ubuntu Server 22.04 arm64`，需要改成其它镜像；当前先按 Leap 现有脚本的系统约束优先。
- `leap1_stack.launch.py` 当前通过 Docker 拉起 `micro-ROS agent`，所以树莓派必须安装并启用 Docker。
- A20 栈相机与串口设备名仍可能因具体硬件枚举顺序变化，首启后需要做一次设备核对。

## 交付产物

- `deploy/raspi/README.md`
- `deploy/raspi/flash_and_seed_leap_pi.sh`
- `deploy/raspi/install_leap1_pi.sh`
- `deploy/raspi/leap1-a20.service`

## 待用户提供的最少信息

- 目标树莓派使用的 Wi-Fi 密码。
- 若不走 Wi-Fi，则确认首启采用有线网络。
