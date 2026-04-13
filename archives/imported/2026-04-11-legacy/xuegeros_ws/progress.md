# Leap1 xuegeros_ws 进度日志

## 2026-03-16 09:34 CST

- 任务启动。
- 确认目标目录为 `/home/gwh/xuegeros_ws`，核心源码为 `/home/gwh/xuegeros_ws/src/leap1`。
- 扫描到的主要包:
  - `xuegecar_bringup`
  - `xuegecar_navigation2`
  - `xuegecar_description`
  - `slam_gmapping`
  - `xuegecar_cartographer`
  - `ydlidar_ros2_driver`
  - `ldlidar_stl_ros2`
- 从 `leap` 资料确认实机契约:
  - 小车固件发布 `/odom`、`/imu`、`/battery`
  - 小车固件订阅 `/cmd_vel`
  - 默认 micro-ROS UDP 端口为 `8888`
- 从 `xuegecar_bringup/launch/leap1_stack.launch.py` 确认:
  - 当前总入口是实机链路，不是仿真链路
  - 当前依赖 Docker micro-ROS agent 和 UDP 雷达桥
- 从 `xuegecar_navigation2` 和 `nav2_bringup` 确认:
  - 本轮如果采用 `gmapping` 在线建图，就必须做自定义“gmapping + navigation”入口
  - 不能直接复用 `nav2_bringup` 的 `slam:=True` 路径
- 执行构建探测:
  - `source /opt/ros/humble/setup.bash && cd /home/gwh/xuegeros_ws && colcon build --packages-select xuegecar_bringup xuegecar_description xuegecar_navigation2 slam_gmapping xuegecar_cartographer --symlink-install --event-handlers console_cohesion+`
  - 结果: 失败
- 原始错误:
  - `ModuleNotFoundError: No module named 'catkin_pkg'`
  - 调用路径显示 CMake 使用了 `/usr/local/miniconda/bin/python3`
- 根因判断:
  - 当前工作区构建首先被 conda `python3` 污染，而不是源码本身首先失败
- 下一步:
  - 固定构建解释器到 `/usr/bin/python3.10`
  - 补齐缺失依赖
  - 然后再进入 Gazebo 仿真后端实现

## 2026-03-16 10:05 CST

- 已完成第一轮结构改造，未覆盖 `xuegecar_bringup` 目录下已有的用户未提交内容。
- 已新增 Gazebo Classic 仿真包 `xuegecar_gazebo`，包含:
  - `launch/gazebo_sim.launch.py`
  - `urdf/xuegecar_gazebo.urdf.xacro`
  - `worlds/leap1_room.world`
- 已将 `xuegecar_bringup/launch/leap1_stack.launch.py` 重构为单入口 launch，新增参数:
  - `backend:=sim|real`
  - `with_mapping`
  - `with_navigation`
  - `with_rviz`
  - `gui`
  - `world`
- 已新增 `xuegecar_navigation2/launch/gmapping_navigation.launch.py`，用于 `gmapping + Nav2` 在线导航。
- 已新增 `xuegecar_navigation2/param/gmapping_nav2.yaml`，去掉静态地图依赖，统一 `base_footprint` 和在线建图导航参数。
- 已修改 `slam_gmapping/launch/slam_gmapping.launch.py`，增加 `use_sim_time` 与 `params_file` 参数透传。
- 已修改 `xuegecar_bringup/launch/xuegecar_bringup.launch.py`:
  - 新增 `use_sim_time`
  - 新增 `use_joint_state_publisher`
  - 为 `robot_state_publisher`、`joint_state_publisher`、`xuegecar_bringup` 节点统一注入 `use_sim_time`
- 已新增工具脚本:
  - `/home/gwh/xuegeros_ws/src/leap1/tools/build_leap1_workspace.sh`
  - `/home/gwh/xuegeros_ws/src/leap1/tools/run_leap1_stack.sh`
  - 两者均显式清理 conda 变量并固定 `/usr/bin/python3.10`
- 新发现:
  - `ydlidar_ros2_driver/launch/ydlidar_launch.py` 使用 `LifecycleNode`，但当前没有自动触发 configure/activate，实机链路后续大概率会卡在雷达节点未激活状态
- 下一步:
  - 先做语法级检查
  - 再跑 `colcon build`
  - 再按 `backend:=sim with_mapping:=true with_navigation:=true` 做仿真闭环验证

## 2026-03-16 10:10 CST

- 语法级检查结果:
  - `/usr/bin/python3.10 -m compileall` 已通过
  - `bash -n` 已通过
- 运行期环境细节:
  - 直接执行 `/usr/bin/xacro` 失败，提示 `没有那个文件或目录`
  - 结论: `xacro` 需要走 ROS 环境下的可执行路径，而不是假定存在于 `/usr/bin`
- 下一步:
  - 在 `source /opt/ros/humble/setup.bash` 后继续做 `xacro` 与 `colcon build` 验证

## 2026-03-16 10:18 CST

- 继续验证时发现两个新增阻塞:
  - `xuegecar_gazebo/package.xml` 里的 `maintainer email="gwh@local"` 不符合 package.xml 规范
  - `xuegecar_bringup` 与 `xuegecar_gazebo` 存在依赖环，导致 `colcon` 无法拓扑排序
- 已采取修复:
  - 将 `xuegecar_gazebo/package.xml` 修正为合法邮箱与 `Apache-2.0`
  - 将 `xuegecar_gazebo` 改为只负责 Gazebo 与实体生成，不再直接启动 `xuegecar_bringup`
  - 将 `sim` 模式下的 `xuegecar_bringup.launch.py` 收回到 `leap1_stack.launch.py`
  - 强化 `tools/build_leap1_workspace.sh` 与 `tools/run_leap1_stack.sh`:
    - 清理 `AMENT_PREFIX_PATH`、`COLCON_PREFIX_PATH`、`CMAKE_PREFIX_PATH`
    - 清理 conda 变量
    - `source` ROS setup 前临时关闭 `set -u`
    - `colcon build` 增加 `--cmake-clean-cache`
    - 显式传入 `-DPython3_EXECUTABLE=/usr/bin/python3.10`
- 构建结果:
  - `/home/gwh/xuegeros_ws/src/leap1/tools/build_leap1_workspace.sh` 已成功完成
  - `9 packages finished [15.9s]`
  - 目前仅有若干上游 warning，无阻塞性错误
- 下一步:
  - 启动 `backend:=sim with_mapping:=true with_navigation:=true`
  - 逐项验证话题、TF、地图与导航控制

## 2026-03-16 10:58 CST

- 仿真主链首次完整激活成功，关键节点进入 active:
  - `controller_server`
  - `planner_server`
  - `bt_navigator`
  - `velocity_smoother`
  - `slam_gmapping`
- 关键中间问题与修复:
  - `controller_server` 初始报错 `No critics defined for FollowPath`
    - 根因 1: `gmapping_navigation.launch.py` 与 `slam_gmapping.launch.py` 使用了同名 `params_file`
    - 结果: `controller_server` 实际读到了 `slam_gmapping.yaml`
    - 修复: 改为 `nav2_params_file` 与 `slam_params_file`
  - `controller_server` 随后报错 `parameter 'height' has invalid type`
    - 根因: `local_costmap.height/width` 用了浮点值，而当前控制器内部先按整数声明
    - 修复: 将 `width/height` 改为整数 `4`
  - `/scan`、`/odom`、`/imu` 初始没有发布者
    - 根因: sim 模式下被注入的是实机 URDF，不带 Gazebo 插件
    - 修复: `xuegecar_gazebo/launch/gazebo_sim.launch.py` 重新接管 sim 模式下的 `robot_state_publisher`，使用仿真 xacro；`leap1_stack.launch.py` 在 sim 模式只保留 `xuegecar_bringup` TF 广播节点
- 数据面复验结果:
  - `ros2 topic info /scan`: `Publisher count: 1`
  - `ros2 topic info /odom`: `Publisher count: 1`
  - `ros2 topic info /imu`: `Publisher count: 1`
  - `ros2 topic info /map`: `Publisher count: 1`
  - `ros2 topic info /cmd_vel`: `Publisher count: 5`, `Subscription count: 1`
- 话题实测:
  - `/scan` 已收到 `frame_id: laser_frame`
  - `/odom` 已收到 `child_frame_id: base_footprint`
  - `/imu` 已收到 `frame_id: imu_link`
  - `/map_metadata` 已收到 `resolution: 0.05`, `width: 384`, `height: 384`
- 底盘物理链验证:
  - 手动给 `/cmd_vel linear.x=0.15` 持续 4 秒
  - 结果: `MANUAL_ODOM_DELTA 0.3001`
- 导航闭环验证:
  - `ComputePathToPose` 成功返回 `PLAN_POSES 77`
  - `NavigateToPose` 被接受
  - 监测到:
    - `CMD_NONZERO True`
    - `CMD_MAX linear=0.2800 angular=0.4241`
    - `ODOM_DELTA 0.1007`
  - 近距离目标探针返回 `SUCCESS_PROBE_STATUS 4`
- 实机链路准备度验证:
  - `ros2 launch ydlidar_ros2_driver ydlidar_launch.py` 已出现日志 `ydlidar 生命周期节点已启动，准备自动 configure。`
  - 随后因当前无真实设备，报错 `cannot bind ... /dev/lidar`
  - 结论: 生命周期自动触发逻辑已生效，当前退出原因是硬件缺失而不是 launch 漏转态
- 当前残留警告:
  - Gazebo Classic EOL 提示
  - Gazebo 传感器 `Get noise index not valid`
  - `static_transform_publisher` 旧参数风格 warning
