# Leap 小车会话交接

- 创建时间：2026-04-11
- 适用仓库：`/home/gwh/leap`
- 当前分支：`work`

## 当前进度

- 已完成统一仓库内的 A20 电脑直连骨架落地：
  - `leap1_a20_interfaces`
  - `leap1_a20`
  - `xuegecar_bringup` / `xuegecar_navigation2` / `xuegecar_description` 联动改造
- 已完成 ESP32 固件安全补丁：
  - `cmd_vel` watchdog
  - agent 断开自动停车
  - 保留现有泵超时保护
- 已完成本机直连联调：
  - ESP32 C 口直连电脑
  - C100 车载相机接到电脑
  - `serial micro-ROS + A20 Web + 相机 + /odom` 已打通

## 已完成事项

- ROS 2 侧
  - 新增 A20 状态机、地图标注、广播中心、巡航执行、相机桥接节点。
  - `leap1_stack.launch.py` 支持 `agent_transport:=udp|serial` 与 A20 相关参数。
  - 广播中心后端改为把 `map.pgm / keepout_mask.pgm` 转成 PNG 再给浏览器。
  - URDF 增补 `camera_link` 与 `ground_camera_link`。
- 固件侧
  - `ap_safety.*` 新增运动安全逻辑。
  - `ap_ros_transport.cpp` 改为在 `create_transport()` 每一步都明确失败返回，并记录 stage。
  - 已重新编译并烧录到当前板子。
- 调试侧
  - 当前电脑连接 WiFi：`Redmi K70 Pro`
  - 当前电脑 IPv4：`10.127.143.124`
  - 已把车端 NVS 切到当前网络并保持 `microros_mode=serial`

## 现有控制链路

- 主控制链路
  - 浏览器 / 控制节点
  - 广播中心 Web 后端
  - `/cmd_vel` / `/pump_cmd`
  - serial micro-ROS agent
  - ESP32 底盘执行
- 雷达链路
  - ESP32 `Serial2`
  - UDP 透传
  - 主机 `socat` -> `/tmp/lidar`
  - `ydlidar_ros2_driver`
- 相机链路
  - C100 UVC
  - `camera_bridge_node`
  - `/a20/vehicle_camera/image_raw`
  - `http://127.0.0.1:8091/snapshot.jpg`
  - 广播中心前端显示

## 网页卡顿判断

- 旧 ESP32 原生网页卡顿的主因仍是：
  - 按钮点击
  - HTTP `/set`
  - 阶梯式下发速度
- 不是底盘 `100 Hz` 控制环本身慢。
- 当前建议继续坚持：
  - 浏览器和控制节点放到树莓派 / 电脑主机侧
  - ESP32 只做底层执行

## 树莓派 / 电脑 C 口直连判断

- 判断结论已经成立：
  - C 口直连应统一走 USB 对应的 `Serial`
  - 不走 `Serial2`
  - `Serial2` 继续留给雷达
- 本轮实测已证明：
  - serial agent 能与 ESP32 建立 XRCE 会话
  - 烧录新固件后，`/odom` 已恢复发布
  - A20 Web 状态机在最小闭环中保持 `IDLE`

## 当前已验证项

- `pio run` 成功
- `pio run -t upload --upload-port /dev/ttyUSB0` 成功
- `colcon build --packages-select leap1_a20_interfaces leap1_a20 xuegecar_bringup xuegecar_navigation2 xuegecar_description` 成功
- `ros2 topic info /odom -v`
  - `Publisher count = 1`
  - 发布者节点：`xuege_motion_control`
- `ros2 topic echo --once /odom` 成功收到消息
- `curl -s http://127.0.0.1:8090/api/status`
  - 返回 `mission.state=IDLE`
  - `healthy=true`
  - `vehicle_camera.online=true`
- `curl http://127.0.0.1:8091/snapshot.jpg`
  - 返回 `200`
  - JPEG `640x480`

## 当前风险

- 电池电压当前仍显示约 `0.71V`
  - 明显不合理
  - 需要单独校准电池采样链路
- 雷达驱动仍有历史告警：
  - `Fail to get baseplate device information`
  - 单独停主机或停桥接时会出现 timeout
- 广播中心 / 相机节点的退出路径已基本收敛，但仍可能看到 `ioctl(VIDIOC_QBUF): Bad file descriptor`
  - 当前不影响正常退出
  - 若要完全清零日志，还需继续收尾 OpenCV 采集线程
- 地图标注、keepout、巡航、火情触发、喷水冷却完整闭环，本轮还未在“最终已烧录固件 + 当前 WiFi”条件下重新跑完一遍

## 下一步任务

1. 重新跑建图工作台：
   - `run_leap1_a20_mapping.sh`
2. 保存地图并验证：
   - Web 载入地图
   - keepout 生成
3. 在 Web 中创建 patrol zone / waypoint / route
4. 跑 `single_run` 与 `loop` 巡航
5. 手动触发火情，验证：
   - 停车
   - 开泵
   - 冷却
   - 恢复
6. 单独校准电池电压链路
