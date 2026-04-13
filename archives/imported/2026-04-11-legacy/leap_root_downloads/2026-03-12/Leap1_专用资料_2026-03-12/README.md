# Leap1 使用准备与全流程说明

生成日期：2026-03-12

## 结论

基于 `leap1使用手册V1.1.pdf`、`Leap1安装说明.pdf` 和当前本地资料包检查，我已在这台 `Ubuntu 22.04.5` 机器上完成 `ROS 2 Humble`、`Docker`、`socat`、`net-tools`、`Nav2`、`Cartographer`、`joint_state_publisher`、`YDLidar-SDK` 以及 `Leap1 ROS2 工作空间` 的准备与构建。当前已经具备直接作为 Leap1 上位机的基础条件。

你现在最需要补齐的，不是手册本身，而是下面这些配套软件和资料：

- 已启用：`ROS 2 Humble`，并已写入 `~/.bashrc`
- 已安装：`Docker`，且 `docker.service` 已启动
- 已拉取：`registry.cn-hangzhou.aliyuncs.com/fishros/micro-ros-agent:humble`
- 已安装：`socat`
- 已安装：`net-tools`
- 已安装：`YDLidar-SDK`，路径在 `/usr/local`
- 已获取并构建：`Leap1 ROS2 功能包源码`，源码在 `/home/gwh/xuegeros_ws/src/leap1`
- 已构建工作空间：`/home/gwh/xuegeros_ws/install_syspy`
- 仍需人工完成：如果机器人尚未刷好固件，需要用 `Windows` 或 `Wine` 运行 `xueger_tool.exe`
- 仍需人工完成：接入真实硬件后，在配置工具里写入 `wifi_ssid / wifi_pswd / udpserver_ip / udpserver_port`
- 按需安装：`PlatformIO`，仅在你准备修改或重新编译主控板固件时需要
- 可能需要安装：`CH340` 驱动，前提是你用 Windows 烧录时电脑不能识别串口

## 已整理到本目录的资料

- `01_手册/leap1使用手册V1.1.pdf`
- `01_手册/Leap1安装说明.pdf`
- `02_烧录与固件/xueger_tool.exe`
- `02_烧录与固件/leap1.bin`
- `03_源码/leap_1_v1.1/`
- `03_源码/使用前请读我！！！！.txt`
- `04_原理图/主控板.pdf`

说明：

- 我只整理了一份主资料包，没有删除原始下载目录中的重复文件。
- `03_源码/leap_1_v1.1/` 复制时排除了 `.pio` 和 `build` 这类缓存/构建目录，避免把无关中间产物一起带进来。

## 已执行安装结果与剩余项

### 1. 运行 Leap1 的必需项

- `ROS 2 Humble`
  作用：运行 `ros2`、`rviz2`、`nav2`、`slam` 等整条链路。
  当前情况：已经安装在 `/opt/ros/humble`。
  你现在需要做的是在新终端先执行：

```bash
source /opt/ros/humble/setup.bash
```

- `Docker`
  作用：运行 `micro-ROS Agent` 容器。
  当前情况：已安装，`docker.service` 已启动。
  手册给出的国内安装命令：

```bash
curl -fsSL https://get.docker.com | bash -s docker --mirror Aliyun
```

- `micro-ROS Agent` 镜像
  作用：作为机器人与 ROS 2 的代理。
  手册里给了两种写法，推荐直接按这条执行：

```bash
sudo docker run -it --rm \
  -v /dev:/dev \
  -v /dev/shm:/dev/shm \
  --privileged \
  --net=host \
  microros/micro-ros-agent:humble udp4 --port 8888 -v6
```

  国内镜像可用：

```bash
sudo docker run -it --rm \
  -v /dev:/dev \
  -v /dev/shm:/dev/shm \
  --privileged \
  --net=host \
  registry.cn-hangzhou.aliyuncs.com/fishros/micro-ros-agent:humble udp4 --port 8888 -v6
```

- `socat`
  作用：把机器人发来的雷达 UDP 数据桥接成虚拟串口 `/dev/lidar`。
  当前情况：已安装。
  启动命令：

```bash
sudo socat -d -d PTY,link=/dev/lidar,raw,echo=0,mode=666 UDP4-LISTEN:8889,reuseaddr,fork
```

- `YDLidar-SDK`
  作用：手册明确要求安装。
  当前情况：已安装到 `/usr/local`。
  手册给出的命令：

```bash
git clone https://github.com/YDLIDAR/YDLidar-SDK.git
mkdir build
cd build
cmake ..
make
sudo make install
```

- `Leap1 ROS2 功能包源码`
  作用：手册后续大量命令依赖这些包。
  当前情况：已从手册给出的仓库拉取到 `/home/gwh/xuegeros_ws/src/leap1`，并确认包含：
  `xuegecar_bringup`
  `xuegecar_navigation2`
  `xuegecar_cartography`
  `slam_gmapping`
  `ydlidar_ros2_driver`
  另外手册在 `2.2.1` 给出过一个来源：

```bash
git clone https://gitee.com/czulcl/leap1.git
```

  但我没有联网验证该仓库当前状态，因此这里仅按手册原文保留。

### 2. ROS 2 额外依赖包

手册明确列出的 apt 包如下：

```bash
sudo apt install ros-humble-cartographer
sudo apt install ros-humble-cartographer-ros
sudo apt install ros-humble-cartographer-ros-msgs
sudo apt install ros-humble-nav2-bringup
sudo apt install ros-humble-navigation2
sudo apt install ros-humble-joint-state-publisher
```

补充建议：

- 当前机器已经安装 `ROS 2 Humble Desktop`
- 当前机器已经安装本节列出的 `nav2/cartographer/joint-state-publisher`
- 每次开新终端时，`~/.bashrc` 会自动载入 `ROS 2` 与 `Leap1` 工作空间

### 3. 烧录与开发相关的按需项

- `CH340` 驱动
  作用：电脑无法识别主控板串口时使用。
  是否必须：不是。仅当 Windows 侧无法识别串口时再装。

- `PlatformIO`
  作用：重新编译 `03_源码/leap_1_v1.1/` 中的 ESP32 固件。
  依据：源码目录存在 `platformio.ini`，并依赖 `micro_ros_platformio`。
  是否必须：不是。只用现成 `leap1.bin` 时不需要。

- `Wine` 或 `Windows`
  作用：运行 `xueger_tool.exe`。
  当前情况：本机没有发现 `wine`，而烧录工具是标准 Windows PE 程序。
  是否必须：如果你要在当前 Ubuntu 主机上烧录，就需要。

- `net-tools`
  作用：提供 `ifconfig`。
  当前情况：本机没有发现 `ifconfig`。
  是否必须：不是。你也可以用 `ip addr` 代替。

## 按手册跑通的推荐顺序

下面这套顺序是把手册内容压缩成一条最短路径。

### 第 1 步：确认硬件与资料

- 按 `01_手册/Leap1安装说明.pdf` 完成底盘、电机、雷达、电池和主控板安装。
- 确认你手里的固件型号和底盘型号一致。手册写的是“选择对应型号固件”，如果不确定，先问客服，不要直接刷。

### 第 2 步：补齐软件环境

在 Ubuntu 22.04 环境中准备：

- `Docker`
- `socat`
- `YDLidar-SDK`
- `Leap1 ROS2 功能包源码`

如果你打算完全按手册的命令来操作，再补一个：

```bash
sudo apt install net-tools
```

### 第 3 步：如果还没刷固件，先刷固件

如果机器人当前没有可用固件，或你需要重刷：

- 使用 `02_烧录与固件/xueger_tool.exe`
- 选择串口
- 选择 `02_烧录与固件/leap1.bin`
- 点击烧录

注意：

- 手册写明主控使用 `CH340K` 串口芯片。
- 当前工具是 `.exe`，更适合 Windows 环境。

### 第 4 步：写入网络参数

烧录后在配置工具里至少填这四项：

- `wifi_ssid`
- `wifi_pswd`
- `udpserver_ip`
- `udpserver_port=8888`

关键注意：

- 手册明确要求连接 `2.4G Wi-Fi`
- `udpserver_ip` 必须填 Ubuntu 虚拟机或主机的实际 IP
- 手册要求虚拟机使用桥接模式

### 第 5 步：获取 Ubuntu 侧 IP

手册写法：

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
