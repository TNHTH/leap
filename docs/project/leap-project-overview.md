# Leap 项目梗概

- 创建时间：2026-04-11
- 最近更新：2026-04-13
- 适用仓库：`/home/gwh/leap`
- 当前默认开发分支：`work`
- 文档目的：作为 Leap 项目的固定概览入口。后续对话只要提到“leap 项目”“Leap 小车”“/home/gwh/leap”，应优先读取本文件，再按任务需要进入更细的专题文档。

## 项目定位

- `leap` 是 Leap 小车的统一主仓库，用来收口固件、ROS 2、资料层与历史归档，方便持续开发、联调、评审和协作。
- 当前项目已经从“基础小车”演进到“消防巡检/抽水演示平台”方向，后续整体目标参考：
  - `docs/project/a20-fire-inspection-project-framework-2026-04-10.md`
- 当前阶段的策略是：
  - 保留现有底盘、导航、网页控制和抽水能力
  - 继续补齐相机接入、火情检测链路、巡检状态机和广播中心
  - 深度模型本体后续再接，本轮先把系统骨架和接口固定

## 仓库结构与分支

- 主仓库路径：`/home/gwh/leap`
- 历史本地目录归档：`/home/gwh/leap/archives/imported/2026-04-11-legacy`
- 关键目录：
  - `firmware/leap_1_v1.1`：ESP32 固件
  - `ros2_ws/src/leap1`：ROS 2 工作空间源码
  - `runtime/`：运行时占位与环境输出目录
  - `materials/`：厂商资料、历史参数与参考包
  - `archives/flashed-firmware`：已烧录固件归档
  - `docs/`：项目说明文档
- 分支约定：
  - `main`：只放已确认稳定的基线
  - `work`：当前日常开发、调试和实验分支

## 当前已确认能力

- ESP32 固件已经负责：
  - 底盘电机控制
  - 编码器采集
  - IMU / 电池 / OLED
  - WiFi 网页控制
  - micro-ROS 通信
- ROS 2 主工作区已经具备：
  - bringup
  - 雷达
  - 建图/导航基础链路
- 水泵控制已经完成并实机验证成功：
  - 控制 IO：`GPIO27`
  - 驱动方式：高电平有效
  - 固件接口：
    - 网页：`GET /pump?enabled=1/0`
    - ROS 2：`/pump_cmd`
    - 状态：`/pump_state`
  - 工具脚本：
    - `ros2_ws/src/leap1/tools/run_leap1_pump.sh`
    - `ros2_ws/src/leap1/tools/run_leap1_pump.py`
- 当前网页已经支持在运动控制页内直接点按抽水。

## 当前控制链路判断

- 固件底层控制环是 `100 Hz`，底盘本体控制不是当前主要瓶颈。
- 固件支持两种 micro-ROS 传输模式：
  - `udp_client`
  - `serial`
- 当前默认配置和现有启动链路偏向 `udp_client`，ROS 启动时默认拉起的是 UDP micro-ROS agent。
- 当前 ESP32 网页运动控制链路是：
  - `浏览器 -> WiFi -> ESP32 HTTP /set`
- 当前网页卡顿的主要可疑点不是电机环，而是网页控制本身仍是“按钮点击 + HTTP 请求”的阶梯式控制。
- 判断结论：
  - 如果继续直接用 ESP32 自带网页控制，树莓派通过 C 口直连并不会自动消除网页卡顿。
  - 如果改成“浏览器/控制节点运行在树莓派上，再通过 C 口串口 micro-ROS 下发到底盘”，控制稳定性和时延大概率会更好。

## 当前开发网络与电脑直连联调状态

- 2026-04-11 当前电脑连接的开发 WiFi 已切到：`Redmi K70 Pro`。
- 2026-04-11 当前电脑在该 WiFi 下的 IPv4：`10.127.143.124`。
- 2026-04-11 通过串口读取到车端 NVS 仍保留旧网络配置：
  - `wifi_ssid=TNHTH`
  - `wifi_pswd` 已配置，但不在仓库文档中明文记录
  - `udpserver_ip=192.168.5.17`
- 2026-04-11 已通过电脑直连 C 口拉起 serial micro-ROS agent，并在 agent 日志中看到 `create_client` 与 `session established`，说明 USB 串口 XRCE 会话已经建立。
- 2026-04-11 当前阻塞点不是“agent 起不来”，而是 ESP32 会话建立后仍未在 ROS 图中创建 `odom / battery_state / pump_state` 发布者，上层状态机因此进入 `odom_timeout -> FAULT`。
- 2026-04-11 如果后续仍保留雷达 UDP 转发和 UDP 回退链路，必须把车端 WiFi SSID/密码和 `udpserver_ip` 一并迁到当前开发网络。

## 当前已知资料与事实

- 技术路线主参考：
  - `docs/project/a20-fire-inspection-project-framework-2026-04-10.md`
- 相机资料包：
  - `/home/gwh/leap/materials/cameras/wheeltec-c100-c70/2024-08-29`
- 已确认当前系统还缺少的核心模块：
  - 车载相机 ROS 节点
  - 火情检测触发链路
  - 巡检状态机/任务管理
  - 消防守护节点
  - 广播中心浏览器面板

## 后续接手默认顺序

1. 先执行 `git -C /home/gwh/leap status -sb`，确认当前工作区状态，不要覆盖已有未提交改动。
2. 先读本文件，明确项目整体状态。
3. 如果任务涉及固件、泵控、IO、Web 控制、micro-ROS 传输，再读：
   - `docs/hardware/firmware-current-state-2026-04-11.md`
4. 如果任务涉及仓库来源、目录收口、主分支/开发分支关系，再读：
   - `docs/project/repository-merge-2026-04-10.md`
5. 如果任务涉及网页卡顿与树莓派直连，优先从“控制链路迁移到树莓派”角度分析，不要先把问题简单归因于 WiFi 信号。

## 当前推荐的下一阶段重点

- 为 Leap 项目建立树莓派直连 ESP32 的串口 micro-ROS 方案。
- 把“网页控制入口”逐步迁移到树莓派，而不是继续把 ESP32 原生网页当作主要交互层。
- 按 A20 技术路线继续补齐：
  - 相机接入
  - 火情检测接口
  - 巡检状态机
  - 广播中心前端

## 相关入口文档

- 文档入口：`docs/README.md`
- A20 总体方案：`docs/project/a20-fire-inspection-project-framework-2026-04-10.md`
- 仓库合并记录：`docs/project/repository-merge-2026-04-10.md`
- 固件现状记录：`docs/hardware/firmware-current-state-2026-04-11.md`
