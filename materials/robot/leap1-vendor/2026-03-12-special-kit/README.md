# Leap1 厂商专用资料包索引

- 导入时间：2026-04-12
- 原始来源：`/home/gwh/leap/_legacy_2026-04-11/leap_root_downloads/2026-03-12/Leap1_专用资料_2026-03-12`
- 当前导入位置：`/home/gwh/leap/materials/robot/leap1-vendor/2026-03-12-special-kit`

## 关键内容

- 手册：
  - `01_手册/leap1使用手册V1.1.pdf`
  - `01_手册/Leap1安装说明.pdf`
- 烧录与固件：
  - `02_烧录与固件/leap1.bin`
  - `02_烧录与固件/xueger_tool.exe`
- 原理图：
  - `04_原理图/主控板.pdf`
- 源码包：
  - `03_源码/leap_1_v1.1/`
  - `03_源码/使用前请读我！！！！.txt`

## 导入说明

- 为方便后续阅读与检索，导入时排除了 `.pio`、`build`、`install`、`log`、`.vscode` 等生成物。
- 该目录作为厂商原始资料副本保留，不作为当前活跃代码入口。

## 使用建议

- 需要查安装、固件烧录和板级原理图时，优先从本目录进入。
- 若后续要回溯更早的原始导入快照，可再到 `archives/imported/2026-04-11-legacy` 查原样副本。


```bash
ifconfig
```

如果你当前机器没有 `ifconfig`，可以直接用：

```bash
ip addr show
```

找到当前网络接口的 IPv4 地址，填回上一步的 `udpserver_ip`。

### 第 6 步：编译 ROS2 工作空间

手册给出的基本流程如下：

```bash
mkdir -p ~/xuegeros_ws/src
cd ~/xuegeros_ws/src
git clone https://github.com/YDLIDAR/YDLidar-SDK.git
git clone https://gitee.com/czulcl/leap1.git
cd ~/xuegeros_ws
colcon build
```

永久加载环境变量时，正确命令应为：

```bash
gedit ~/.bashrc
```

在文件末尾添加：

```bash
source /你的实际路径/install/setup.bash
```

然后执行：

```bash
source ~/.bashrc
```

### 第 7 步：启动 micro-ROS 代理

```bash
sudo docker run -it --rm \
  -v /dev:/dev \
  -v /dev/shm:/dev/shm \
  --privileged \
  --net=host \
  microros/micro-ros-agent:humble udp4 --port 8888 -v6
```

说明：

- 手册 `4.1` 和 `4.2` 节里有 `--port 8888-v4`、`--port 8888-v6` 这种连写，明显是 PDF 排版/提取时丢了空格。
- 我这里采用的是 `3.3` 节里最完整、可读性最高的写法：`udp4 --port 8888 -v6`。

### 第 8 步：启动雷达桥接与驱动

先桥接：

```bash
sudo socat -d -d PTY,link=/dev/lidar,raw,echo=0,mode=666 UDP4-LISTEN:8889,reuseaddr,fork
```

确认虚拟串口存在：

```bash
ls /dev/lidar
```

再启动驱动：

```bash
ros2 launch ydlidar_ros2_driver ydlidar_launch.py
```

### 第 9 步：启动底盘 TF、建图、导航

底盘 TF：

```bash
ros2 launch xuegecar_bringup xuegecar_bringup.launch.py
```

Gmapping 建图：

```bash
ros2 launch slam_gmapping slam_gmapping.launch.py
```

保存地图：

```bash
ros2 run nav2_map_server map_saver_cli -t map -f room
```

Cartographer 建图：

```bash
ros2 launch xuegecar_cartography cartography.launch.py
```

导航：

```bash
ros2 launch xuegecar_navigation2 navigation2.launch.py
```

如果使用保存的地图：

```bash
ros2 launch xuegecar_navigation2 navigation2.launch.py map:=/path/to/your/map.yaml
```

## 基于当前机器的状态判断

当前机器检查结果：

- 已满足：`Ubuntu 22.04.5 LTS`
- 已发现：`ROS 2 Humble`，路径为 `/opt/ros/humble`
- 已发现：`colcon`、`git`、`code`、`ip`
- 已安装：`docker`
- 已安装：`socat`
- 已安装：`ifconfig`
- 已拉取：`micro-ROS Agent` 国内镜像
- 已构建：`/home/gwh/xuegeros_ws/install_syspy`
- 未发现：`pio`
- 未发现：`wine`

因此，如果你想从“现在这台机器”直接开始，建议按下面顺序补齐：

1. 连接真实硬件
2. 如果需要刷固件，先决定用 `Windows` 还是 `Wine`
3. 在配置工具里写入 `wifi_ssid / wifi_pswd / udpserver_ip / udpserver_port`
4. 终端里启动 `micro-ROS Agent`
5. 启动 `socat` 桥接 `/dev/lidar`
6. 启动 `ydlidar_ros2_driver`、`xuegecar_bringup`、`slam_gmapping` 或 `xuegecar_navigation2`
7. 只有在要改固件时，再安装 `PlatformIO`

## 最后提醒

- 手册明确建议 `Ubuntu 22.04 + ROS 2 Humble`，不要自行换成 `20.04` 或 `24.04`
- Wi-Fi 侧要使用 `2.4G`
- 虚拟机网络要走桥接
- `udpserver_port` 默认按手册保持 `8888`
- 本地资料包不含完整 ROS2 运行包，这一点是当前最主要缺口
