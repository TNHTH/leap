# Leap Web / Camera / Gamepad 交接

- 创建时间：2026-04-19
- 适用仓库：`/home/gwh/leap`
- 当前分支：`work`

## 本轮结论

- 网页控制端已经可拉起，full-stack 页面和关键 API 可用。
- 未建图阶段的手柄控制入口已补齐：
  - 浏览器侧 Gamepad API -> `/api/cmd_vel`
  - 独立脚本 `run_leap1_manual_drive_runtime.sh`
- 真机导航已验证到：
  - `/odom` 有发布者 `xuege_motion_control`
  - `/scan` 有发布者 `ydlidar_ros2_driver_node`
  - 发布 `/initialpose` 后，`/amcl_pose` 可出现
  - `NavigateToPose` 近零位姿目标返回 `SUCCEEDED`
- 但正式巡航仍未完全收口：
  - `keepout` mask 仍未提供
  - 开机后仍需人为设置初始位姿
  - 广播中心里的两路相机角色与当前部署事实不一致

## 当前真实部署事实

- 电脑是广播中心。
- 固定相机接在电脑端，本机设备枚举显示：
  - `/dev/video2`
  - `/dev/video3`
  - 设备名：`HJ USB 2.0 Camera`
- 车载相机接在树莓派，不在电脑本机。
- 树莓派主机：
  - `leap@10.127.143.229`
  - 主机名：`leap-pi`
- ESP32 板载 HTTP 仍可在：
  - `http://10.127.143.212/status`

## 已做代码修改

- Web 控制端：
  - `ros2_ws/src/leap1/tools/run_leap1_web_control.sh`
  - `ros2_ws/src/leap1/tools/run_leap1_web_control_smoke.sh`
  - `ros2_ws/src/leap1/leap1_a20/leap1_a20/web/index.html`
  - `ros2_ws/src/leap1/leap1_a20/leap1_a20/web/app.js`
  - `ros2_ws/src/leap1/leap1_a20/leap1_a20/web/styles.css`
  - `ros2_ws/src/leap1/leap1_a20/leap1_a20/broadcast_center_server.py`
- 手柄入口：
  - `ros2_ws/src/leap1/tools/run_leap1_manual_drive_runtime.sh`
- 说明文档：
  - `README.md`

## 已验证项

- `colcon build --packages-select leap1_a20` 通过
- `/usr/bin/python3 -m pytest src/leap1/leap1_a20/test -q` 通过
- `run_leap1_web_control_smoke.sh` 通过，已验证：
  - `/api/status`
  - `/api/maps`
  - `/api/cmd_vel`
  - `/api/stop`
  - `/api/pump`
- 浏览器打开 `http://127.0.0.1:8090/`
  - 标题正常
  - 控制台 `0` 错误
- 手柄链路已验证接入当前 ROS 图：
  - `/joy` 有 `joy_node`
  - `/cmd_vel` 有 `teleop_twist_joy_node`
  - `/cmd_vel` 有订阅者 `xuege_motion_control`

## 当前阻塞

### 1. 相机角色与页面不一致

- 当前电脑端 `broadcast_center_server` 只看到本机 `vehicle_camera` 逻辑，没有看到树莓派侧 `vehicle_camera` 状态发布。
- 电脑端固定相机默认没有启用：
  - `run_leap1_center_console.sh` 里默认 `LEAP1_WITH_GROUND_CAMERA=false`
- 如果页面由电脑端提供，而车载相机在树莓派，则前端必须依赖树莓派侧发布的 `stream_url` / `snapshot_url`，不能回退到 `window.location.hostname:8091`

### 2. 树莓派相机链未接通

- 之前电脑端观察到 `/a20/camera/status` 没有发布者
- `127.0.0.1:8091` / `:8092` 在电脑端也未绑定
- 下一窗口需要上树莓派检查：
  - `leap1-vehicle-runtime.service`
  - `camera_bridge_node`
  - 是否已有 `stream_url` 发布

### 3. 导航 still needs manual init pose

- clean patrol 会话里，`amcl` 在收到 `/initialpose` 后能工作
- 不手动设初始位姿时，`map -> odom` 不能稳定建立
- `keepout filter` 缺 mask，仍会 warning

## 推荐下一步

1. SSH 到树莓派，确认这几项：
   - `systemctl status leap1-microros-agent.service leap1-vehicle-runtime.service leap1-center-console.service`
   - `ros2 node list | grep -E 'camera_bridge|ground_camera|broadcast_center'`
   - `ros2 topic info /a20/camera/status -v`
   - `ss -ltnp | grep -E '8090|8091|8092'`
2. 若树莓派车载相机链没起来：
   - 起 `run_leap1_vehicle_runtime.sh`
   - 确认 `/a20/camera/status` 有 `vehicle_camera` 的 `stream_url`
3. 电脑端把固定相机启起来：
   - 默认设备优先尝试 `/dev/video2`
   - `run_leap1_web_control.sh` / `run_leap1_center_console.sh` 应默认打开 `with_ground_camera`
4. 修前端回退逻辑：
   - `vehicle_camera` 必须优先使用后端提供的 `stream_url`
   - 不能假设车载流和页面同源
5. 手柄链路若要真正作为“电脑手柄 -> 树莓派控制小车”长期方案：
   - 优先保留当前 ROS topic 方案，不要试图把 `/dev/input/js0` 透传到树莓派
   - 可补一个更轻的“仅 joy teleop，不起本地 vehicle runtime”的脚本

## 新窗口提示词

```text
继续处理 /home/gwh/leap 的 Web / 相机 / 手柄联调。

先读：
1. /home/gwh/leap/docs/handoff/session-handoff-2026-04-19-web-camera-gamepad.md
2. /home/gwh/leap/docs/ops/leap1-runtime-runbook-2026-04-13.md
3. /home/gwh/leap/ros2_ws/src/leap1/leap1_a20/launch/a20_center.launch.py
4. /home/gwh/leap/ros2_ws/src/leap1/leap1_a20/launch/a20_vehicle.launch.py
5. /home/gwh/leap/ros2_ws/src/leap1/leap1_a20/leap1_a20/broadcast_center_server.py
6. /home/gwh/leap/ros2_ws/src/leap1/leap1_a20/leap1_a20/camera_bridge_node.py
7. /home/gwh/leap/ros2_ws/src/leap1/leap1_a20/leap1_a20/web/app.js
8. /home/gwh/leap/ros2_ws/src/leap1/tools/run_leap1_center_console.sh
9. /home/gwh/leap/ros2_ws/src/leap1/tools/run_leap1_web_control.sh
10. /home/gwh/leap/ros2_ws/src/leap1/tools/run_leap1_manual_drive_runtime.sh

当前事实：
- 电脑是广播中心
- 固定相机在电脑端，设备是 /dev/video2 或 /dev/video3，对应 HJ USB 2.0 Camera
- 车载相机在树莓派，不在电脑端
- 树莓派可登录： leap@10.127.143.229
- Web 控制端和 API 已经可用
- 手柄已枚举成 /dev/input/js0，joy + teleop_twist_joy 已验证可接入 /cmd_vel

任务目标：
1. 修正广播中心两路相机角色和默认值：
   - 固定相机默认在电脑端启用
   - 车载相机从树莓派侧状态 / stream_url 接入
2. 上树莓派检查并修复车载相机链：
   - leap1-vehicle-runtime.service
   - /a20/camera/status
   - 8091 端口
3. 让网页里两个相机都能 ready 并可看流
4. 如有必要，补一个“电脑手柄 -> 远端树莓派小车”专用轻量脚本，不要再起本地 vehicle runtime

约束：
- 不要回滚当前 work 脏改动
- 先验证，再改代码
- 每完成一批检查就汇报当前发现
```
