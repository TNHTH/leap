# Leap 树莓派部署

- 创建时间：2026-04-11
- 适用仓库：`/home/gwh/leap`

## 目标

把一张空 TF 卡制作成 Leap 小车可用的树莓派系统卡，并在首启后自动完成 Leap 运行环境安装。

## 当前方案

- 系统镜像：`Ubuntu Server 22.04.5 arm64`
- ROS 发行版：`ROS 2 Humble`
- 默认用户：`leap`
- 默认主机名：`leap-pi`
- 默认启动服务：`leap1-a20.service`

## 文件说明

- `flash_and_seed_leap_pi.sh`
  - 在主机上执行。
  - 下载官方镜像、校验、刷卡、注入 cloud-init、拷入 Leap 仓库快照。
- `install_leap1_pi.sh`
  - 在树莓派首启时执行。
  - 安装 ROS 2、Docker、运行依赖并构建工作空间。
- `leap1-a20.service`
  - 树莓派开机后自动启动 Leap A20 车载栈。

## 推荐执行方式

### 1. 有线首启

如果暂时不想填 Wi-Fi，可直接让脚本只配置以太网 DHCP：

```bash
cd /home/gwh/leap
sudo ./deploy/raspi/flash_and_seed_leap_pi.sh /dev/sdX
```

### 2. Wi-Fi 首启

```bash
cd /home/gwh/leap
sudo LEAP_WIFI_SSID='你的WiFi名' \
     LEAP_WIFI_PASSWORD='你的WiFi密码' \
     ./deploy/raspi/flash_and_seed_leap_pi.sh /dev/sdX
```

### 3. 刷卡后首启验证

树莓派上电并联网后，在当前主机执行：

```bash
ssh leap@leap-pi.local
sudo journalctl -u leap-firstboot.service -f
sudo journalctl -u leap1-a20.service -f
```

## 可调环境变量

- `LEAP_HOSTNAME`
  - 默认：`leap-pi`
- `LEAP_PI_USER`
  - 默认：`leap`
- `LEAP_WIFI_SSID`
  - 默认：空
- `LEAP_WIFI_PASSWORD`
  - 默认：空
- `LEAP_SSH_PUBKEY`
  - 默认：自动读取当前主机的 `~/.ssh/id_ed25519_dashgo.pub`
- `LEAP_AGENT_SERIAL_DEV`
  - 默认：`/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0`
- `LEAP_VEHICLE_CAMERA_DEVICE`
  - 默认：`/dev/video0`

## 刷卡脚本的保护机制

- 会先列出待覆盖设备。
- 会要求手工输入确认串。
- 若设备仍有挂载分区，会先尝试卸载。

## 首启后默认行为

- 创建 `leap` 用户并注入 SSH 公钥。
- 首启自动执行 `install_leap1_pi.sh`。
- 安装完成后自动启用 `leap1-a20.service`。
- `leap1-a20.service` 默认会拉起：
  - `serial micro-ROS agent`
  - 雷达 UDP 桥接
  - Leap bringup
  - A20 Web 面板
  - 车载相机桥接
