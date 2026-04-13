# Leap1 xuegeros_ws 发现记录

## 2026-03-16 09:34 CST

1. 主工作区源码位于 `/home/gwh/xuegeros_ws/src/leap1`，而不是 `src/ydlidar_ros2_driver` 的外层副本。
2. 现有 `xuegecar_bringup/launch/leap1_stack.launch.py` 是实机链路，包含:
   - Docker 版 micro-ROS agent
   - UDP 雷达桥
   - `ydlidar_ros2_driver`
   - `xuegecar_bringup`
   - 可选 `slam_gmapping`
3. 固件资料表明实机 ROS2 契约为:
   - 发布 `odom`
   - 发布 `imu`
   - 发布 `battery`
   - 订阅 `cmd_vel`
4. 当前工作区没有现成 Gazebo 仿真包、world 或 Gazebo 插件链，因此“完整仿真”需要新增后端，而不是只改 launch。
5. `slam_gmapping` 当前参数使用:
   - `base_frame: base_footprint`
   - `odom_frame: odom`
6. `xuegecar_bringup` 当前节点会把 `/odom` 广播为 `odom -> base_footprint`。
7. `xuegecar_description/urdf/xuegecar.urdf` 已定义:
   - `base_footprint`
   - `base_link`
   - `laser_frame`
   - `imu_link`
8. `xuegecar_navigation2` 现有 launch 主要面向静态地图导航，不适合本次锁定的 `gmapping` 在线导航链。
9. `nav2_bringup` 的标准 `bringup_launch.py` 在 `slam:=True` 时会接 `slam_toolbox`，不适合直接拿来作为 `gmapping` 在线导航入口。
10. 当前构建存在环境阻塞:
    - CMake/ament 调用了 `/usr/local/miniconda/bin/python3`
    - 缺 `catkin_pkg`
11. `xuegecar_bringup` 目录当前已有未提交变更:
    - `CMakeLists.txt`
    - `package.xml`
    - `config/`
    - `launch/leap1_stack.launch.py`
12. 本机已安装关键系统依赖:
    - Gazebo Classic
    - Nav2
    - Cartographer
    - slam_toolbox
    - xacro
    - robot_state_publisher
    - joint_state_publisher

## 2026-03-16 10:05 CST

13. `xuegecar_bringup/launch/leap1_stack.launch.py` 已具备被改造成统一总入口的条件，因为现有实机链路本身已经集中在这一个文件里。
14. `xuegecar_navigation2` 现有目录结构允许直接新增一条 `gmapping_navigation.launch.py`，不需要新建独立导航包。
15. 通过新增 `xuegecar_gazebo` 包，可以在不改动现有实机协议的情况下为上层复刻这些接口:
    - `/scan`
    - `/odom`
    - `/imu`
    - `/cmd_vel`
    - `odom -> base_footprint -> base_link -> laser_frame/imu_link`
16. 仿真里 `odom -> base_footprint` 最好沿用现有 `xuegecar_bringup` 节点发布，Gazebo diff drive 插件只发布 `/odom`，并关闭自身 `odom TF`，这样能与实机路径保持更接近的 TF 拓扑。
17. `ydlidar_ros2_driver/launch/ydlidar_launch.py` 当前只启动 `LifecycleNode`，但没有生命周期状态迁移逻辑；这是实机总入口潜在阻塞项，必须在仿真主链稳定后补上。
18. 工作区中的 `build/` 缓存确实固化了 `/usr/local/miniconda/bin/python3`，但通过:
    - 清理前缀环境变量
    - `--cmake-clean-cache`
    - 显式指定 `Python3_EXECUTABLE`
   已足以恢复正常构建，不必先做整仓删除。
19. `xuegecar_bringup` 作为总入口包依赖 `xuegecar_gazebo` 是合理的，但反向依赖会形成拓扑环，因此仿真包不能再直接依赖 `xuegecar_bringup`。
20. `gmapping_navigation.launch.py` 和 `slam_gmapping.launch.py` 如果复用同名 `params_file`，会在父 launch 中发生参数串台。实际证据是 `controller_server` 命令行同时带上了 `slam_gmapping.yaml` 和 Nav2 临时参数文件。
21. sim 模式下如果继续复用 `xuegecar_bringup.launch.py` 的 `robot_description`，被注入 Gazebo 的会是实机 URDF 而不是带 Gazebo 插件的仿真 URDF，结果就是:
    - `/scan` 无发布者
    - `/odom` 无发布者
    - `/imu` 无发布者
22. 当前 Gazebo Classic 仿真中真正能证明“从控制到运动”闭环成立的最直接证据，是手动 `/cmd_vel` 测试得到 `MANUAL_ODOM_DELTA 0.3001`。
23. 当前 Gazebo Classic 仿真中真正能证明“从规划到控制”闭环成立的最直接证据，是:
    - `PLAN_POSES 77`
    - `CMD_MAX linear=0.2800 angular=0.4241`
    - `ODOM_DELTA 0.1007`
24. `NavigateToPose` 的近距离目标在当前参数下会因为 `xy_goal_tolerance=0.20` 很快返回成功，因此“目标成功状态”需要和“实际位姿变化”一起看，不能单独拿状态码作为唯一验收依据。
25. `ydlidar_ros2_driver` 当前在没有真实 `/dev/lidar` 的机器上会正常进入 SDK 初始化，然后因串口绑定失败退出；这说明当前阻塞点已从 launch 配置转为真实硬件可达性。
