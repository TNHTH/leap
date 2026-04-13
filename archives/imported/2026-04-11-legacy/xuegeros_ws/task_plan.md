# Leap1 xuegeros_ws 全链路仿真与实车单入口任务计划

- 时间: 2026-03-16 09:34 CST
- 目标: 将 `/home/gwh/xuegeros_ws/src/leap1` 改造成一套可在 Gazebo Classic 完整跑通“感知 -> 建图 -> 导航 -> 控制”全链路、并可一键切换到实车后端的 ROS2 工作区。
- 工作目录: `/home/gwh/xuegeros_ws`
- 当前约束:
  - 上层接口与实机保持一致，最终只需要电脑端启动一条总 launch，小车上电接入即可。
  - 仿真后端固定为 Gazebo Classic。
  - 在线建图后端固定为 `gmapping`。
  - 过程必须全程记录。

## 验收标准

1. 工作区可在不依赖 conda `python3` 的前提下稳定构建。
2. 提供一条单入口 launch，可通过参数切换 `backend:=sim|real`。
3. `backend:=sim` 时，Gazebo Classic 中可完整跑通:
   - `/scan`
   - `/odom`
   - `/imu`
   - `/map`
   - `/cmd_vel`
   - 完整 TF 树
4. `backend:=sim` 下，发送导航目标后，机器人能完成在线建图导航与运动控制。
5. `backend:=real` 时，沿用当前 leap 固件和 UDP/micro-ROS 契约，不改上层导航链。
6. 全部命令、报错、根因、修复和复验结果都写入持久记录。

## 阶段

1. 建立记录文件并固化环境基线。
2. 修复工作区构建与 Python 环境问题。
3. 新增 Gazebo Classic 仿真后端并统一机器人接口。
4. 重构单入口 launch，支持 `sim|real` 双后端切换。
5. 跑通 gmapping 在线建图导航闭环。
6. 验证实车后端对齐与最终收口文档。

## 当前已知风险

- `xuegecar_bringup` 目录已有未提交修改，实施时必须兼容而不是覆盖。
- 当前工作区构建已确认受 conda `python3` 污染。
- 仓库里没有现成 Gazebo 仿真包，需要新增仿真后端。
- `base_link` / `base_footprint` / `laser_frame` 在现有包中存在不一致，需要统一。

## 2026-03-16 当前完成状态

1. 已完成工作区构建恢复，`/home/gwh/xuegeros_ws/src/leap1/tools/build_leap1_workspace.sh` 可稳定构建通过。
2. 已完成单入口总 launch 改造，支持 `backend:=sim|real`。
3. 已完成 Gazebo Classic 仿真后端，实现:
   - `/scan`
   - `/odom`
   - `/imu`
   - `/cmd_vel`
   - `/map`
   - `tf/tf_static`
4. 已完成 `gmapping + Nav2` 在线导航闭环打通，拿到:
   - 规划结果 `PLAN_POSES 77`
   - 控制输出 `CMD_MAX linear=0.2800 angular=0.4241`
   - 位姿变化 `ODOM_DELTA 0.1007`
   - 近距离目标 `NavigateToPose` 成功状态 `4`
5. 已补上 `ydlidar` 生命周期自动 configure 逻辑，实机模式下不再停在未配置状态。
6. 当前剩余项不是阻塞项:
   - Gazebo Classic EOL 警告
   - Gazebo 传感器 `Get noise index not valid` 噪声警告
   - 未连接真实雷达时，`ydlidar` 仍会因 `/dev/lidar` 缺失而退出，这是预期硬件缺失表现
