# Leap 雷达资料索引

## 当前活跃运行参数

- 主链当前活跃参数文件：
  - `ros2_ws/src/leap1/xuegecar_bringup/config/ydlidar_udp_bridge.yaml`
- 当前 LD19 参考 launch：
  - `ros2_ws/src/leap1/ldlidar_stl_ros2/launch/ld19.launch.py`

## 历史本地参数与厂商文档

- 历史本地参数：
  - `/home/gwh/leap/materials/lidar/params/legacy/ydlidar-local.yaml`
- YDLidar SDK 协议与 API 文档：
  - `/home/gwh/leap/materials/lidar/vendor/ydlidar-sdk-docs`

## 当前链路判断

- 当前雷达运行链仍是：
  - `ESP32 UART2 -> WiFi UDP:8889 -> socat -> /tmp/lidar -> ydlidar_ros2_driver`
- 最近一次专门核查记录：
  - `/home/gwh/文档/Obsidian Vault/03_项目记录/Leap_雷达链路核查_2026-04-12_14-33.md`

## 使用建议

- 先区分“活跃运行参数”和“历史本地参数”，不要混改。
- 若后续确认实机雷达型号是 LD19 / LD06，优先同时对照 `ldlidar_stl_ros2` 与当前 `ydlidar_udp_bridge.yaml`。

