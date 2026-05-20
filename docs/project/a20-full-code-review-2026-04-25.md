---
title: A20 一日完整静态审查
created: 2026-04-25
type: code-review
status: implemented
---

# A20 一日完整静态审查

## 结论

本轮已完成现役一方代码静态审查并实施 P0/P1 收口。重点修复配置解析安全、密码输出、雷达转发日志、任务创建错误可见性、TF 发布方式、Launch 参数化、包元信息和仓库污染问题。第三方驱动只检查接口与配置风险，不做逐函数重构。

## 严重问题

1. `firmware/leap_1_v1.1/lib/AP_Config/ap_config.cpp`：串口配置解析原先没有限制行长和 token 长度，超长输入可能写越界。已修复为 511 字符行长、31 字符 token 上限，并要求严格 `$key=value`。
2. `firmware/leap_1_v1.1/lib/AP_Config/ap_config.cpp` 与 OLED 显示：WiFi 密码原先可通过配置输出和屏幕显示明文泄露。已改为 `******` 遮挡。
3. `firmware/leap_1_v1.1/src/tasks.cpp`：原先存在硬编码 fallback WiFi 热点和密码。已移除，雷达串口 WiFi 只使用 NVS 配置。
4. `firmware/leap_1_v1.1/src/tasks.cpp`：雷达 UDP 转发原先逐包打印，可能拖慢串口和 FreeRTOS 调度。已改为每秒统计包数、字节数和 UDP 失败数。
5. `firmware/leap_1_v1.1/src/tasks.cpp`：serial micro-ROS 使用 UART0 时，雷达任务日志会污染 XRCE-DDS 二进制流。已在 UART0 serial 模式下关闭雷达任务日志；当 `serial_id=2` 与雷达 UART2 冲突时，雷达任务直接停用并输出一次错误。
6. `ros2_ws/src/leap1/xuegecar_bringup/src/xuegecar_bringup.cpp`：TF 原先 1000Hz 轮询发布，增加 CPU、DDS 和 TF 缓存压力。已改为收到 odom 回调时同步发布。

## 警告

1. `ros2_ws/src/leap1/xuegecar_bringup/launch/leap1_stack.launch.py`：原先 Docker Agent、端口、socat 链路和退出联动写死。已改为参数化，默认不因 Agent 或雷达桥接退出关闭全局 Launch。
2. `ros2_ws/src/leap1/leap1_a20/leap1_a20/broadcast_center_server.py`：原先 HTTP 路由、系统采集和 ROS 节点逻辑过于集中。已拆出 `broadcast_center_http.py` 和 `broadcast_center_system.py`。
3. `ros2_ws/src/leap1/leap1_a20/leap1_a20/broadcast_center_http.py`：HTTP POST 原先对畸形 `Content-Length` 不稳定。已改为 JSON 400 响应，并给 HTTP server 增加启动状态保护。
4. `ros2_ws/src/leap1/xuegecar_*`：多个第一方包仍带模板元信息。已统一版本、描述、维护者和 Apache-2.0 许可证。
5. `firmware/leap_1_v1.1/platformio.ini`：micro-ROS PlatformIO 依赖原先未固定 commit。已固定到 `cfee17faffaa532363b7151dd13af6a85c69d3c1`，并新增 debug/release 环境。

## 建议

1. `leap1_a20` 仍有较大的业务节点，例如 `mission_manager_node.py`、`camera_bridge_node.py`、`flame_detection_node.py`。本轮优先拆了广播中心，后续可继续把状态机表、摄像头采集后端、火焰候选评分拆为独立类。
2. 第三方包 `ydlidar_ros2_driver`、`ldlidar_stl_ros2`、`slam_gmapping`、`openslam_gmapping` 暂不做风格清洗，后续只通过配置和上层适配隔离。
3. 本轮未做真实上车联调，仍需在比赛设备上复测 micro-ROS Agent、雷达 PTY、Nav2、Web 面板和水泵安全链路。
4. Launch 默认不因 Agent 或雷达桥退出关闭全局栈，便于现场降级排障；实车严格联动演示时建议显式设置 `shutdown_on_agent_exit:=true shutdown_on_lidar_bridge_exit:=true`。

## 已保留的兼容性

- ROS topic、service、message 和包名不变。
- `leap1_a20_interfaces` 消息定义不变。
- 原有 `ros2 launch xuegecar_bringup leap1_stack.launch.py` 命令仍可使用。
- `with_flame_detector` 继续从总 Launch 透传到 A20 vehicle Launch。
- `/tmp/lidar` 保持默认，现场可通过 `lidar_link:=/dev/lidar` 覆盖。

## 验证记录

截至 2026-04-25，本轮已完成以下上车前验证：

- `python3 -m py_compile`：总 Launch、A20 Launch、广播中心拆分模块通过。
- `colcon build --packages-select xuegecar_bringup xuegecar_navigation2 xuegecar_description xuegecar_cartographer xuegecar_gazebo leap1_a20 leap1_a20_interfaces`：通过。
- `colcon test --packages-select leap1_a20 xuegecar_bringup`：`leap1_a20` 19 项通过，`xuegecar_bringup` 7 项通过。
- `ros2 launch xuegecar_bringup leap1_stack.launch.py --show-args`：新增参数可见。
- 降级启动 smoke：去掉 Conda `libstdc++` 影响后可进入运行态；由于本机未手动启动 `/tmp/lidar` 桥接，YDLIDAR 绑定串口失败属于无硬件桥接环境下的预期限制。
- `pio run -d firmware/leap_1_v1.1 -e leap1_release`：通过，Flash 55.0%，RAM 26.4%。
- `pio run -d firmware/leap_1_v1.1 -e leap1_debug`：通过，Flash 55.2%，RAM 26.4%。
- Git 索引污染检查：生成物、历史归档和二进制交付物匹配数为 0。
