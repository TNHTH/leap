# Leap A20 电脑直连调试验收记录

- 创建时间：2026-04-11
- 适用仓库：`/home/gwh/leap`
- 电脑角色：临时代替树莓派作为车载主机

## 当前设备映射

- ESP32 串口
  - `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0`
- 车载 C100
  - `/dev/video0`
- 当前开发 WiFi
  - `Redmi K70 Pro`
- 当前主机 IPv4
  - `10.127.143.124`

## 已执行调试

### 1. 依赖与构建

- `python3 -m py_compile` 通过
- `colcon build --packages-select leap1_a20_interfaces leap1_a20 xuegecar_bringup xuegecar_navigation2 xuegecar_description` 通过
- `pio run` 通过
- `pio run -t upload --upload-port /dev/ttyUSB0` 通过

### 2. 电脑直连 serial micro-ROS

- 已把板子当前 NVS 切到：
  - `microros_mode=serial`
  - `wifi_ssid=Redmi K70 Pro`
  - `udpserver_ip=10.127.143.124`
- micro-ROS agent 实测日志已出现：
  - `create_client`
  - `session established`
  - `create_participant`
  - `create_topic`
  - `create_publisher`
  - `create_datawriter`
  - `create_subscriber`
  - `create_datareader`

### 3. A20 状态机 / Web / 相机

- `ros2 launch leap1_a20 a20_vehicle.launch.py ...`
  - 广播中心启动成功
  - C100 MJPEG 启动成功
- `curl -s http://127.0.0.1:8090/api/status`
  - 返回 `state=IDLE`
  - 返回 `healthy=true`
  - `vehicle_camera.online=true`
- `curl http://127.0.0.1:8091/snapshot.jpg`
  - 返回 `200`
  - 实际文件类型为 JPEG

### 4. 底盘话题

- `ros2 topic info /odom -v`
  - `Publisher count = 1`
  - 发布者：`xuege_motion_control`
- `ros2 topic echo --once /odom`
  - 成功收到 `nav_msgs/msg/Odometry`
- `ros2 topic echo --once /battery_state`
  - 成功收到 `sensor_msgs/msg/BatteryState`

## 关键修复点

- `gmapping_navigation.launch.py`
  - 补 `IfCondition` 导入
- 广播中心
  - 地图 / keepout 改为服务端转 PNG
- A20 相机节点
  - 修 `ThreadingHTTPServer` MRO 问题
  - 补退出时采集线程 `join`
- Mission Manager
  - 火情事件改为只对边沿变化响应
  - 相机 warmup 宽限后再判定超时
- 固件
  - `cmd_vel` watchdog
  - agent 断开自动停车
  - `create_transport()` 改为按 stage 明确失败返回

## 已验收项

- serial micro-ROS 会话建立成功
- `/odom` 恢复发布
- `/battery_state` 恢复发布
- 广播中心状态接口正常
- C100 快照接口正常
- A20 状态机在最小闭环中保持 `IDLE`

## 未完成验收

- 建图工作台完整链路
- 地图保存后 Web 标注 keepout
- Nav2 keepout 实际避让
- `single_run` / `loop` 巡航
- 火情触发 -> 停车 -> 喷水 -> 冷却 -> 恢复
- 固定摄像头接入

## 剩余风险

- 当前电池电压读数约 `0.71V`
  - 需要单独校准
- 雷达驱动仍存在历史告警
  - `Fail to get baseplate device information`
- 广播中心静态文件接口目前不支持 `HEAD`
  - 不影响浏览器正常加载
- WiFi 凭据未写入仓库
  - 当前设备已写入 NVS
  - 若后续整板擦除，需要再次通过串口下发
