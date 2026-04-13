# Leap

`/home/gwh/leap` 是 Leap 小车项目的唯一仓库根，当前主线围绕“服创 A20 消防小车”闭环方案推进，重点是把巡检发现、停车处置、安全保护和广播上报组织成一条可联调、可演示、可答辩的完整链路。

## 项目主线

- A20 总体方案：`docs/project/a20-fire-inspection-project-framework-2026-04-10.md`
- 项目概览：`docs/project/leap-project-overview.md`
- 文档入口：`docs/README.md`

## 顶层结构

```text
archives/
docs/
firmware/leap_1_v1.1
materials/
ros2_ws/src/leap1
runtime/
worktrees/
```

## 目录分工

- `docs/`
  - 项目说明、硬件现状、联调记录和仓库合同。
- `firmware/leap_1_v1.1`
  - ESP32 固件源码与板级控制逻辑。
- `ros2_ws/src/leap1`
  - ROS 2 工作空间源码、导航、工具脚本与 A20 扩展包。
- `runtime/`
  - 运行时占位目录；日志、地图等运行产物默认不提交。
- `materials/`
  - 相机、雷达、整车厂商资料与历史参数副本。
- `archives/`
  - 已烧录固件、旧导入快照、历史仓库副本和历史 worktree 归档。
- `worktrees/`
  - 仅用于未来顶层仓库的 `git worktree` 并行开发。
- `_legacy_2026-04-11`
  - 指向旧导入快照，仅作历史参考，不是现役入口。

## 分支约定

- `main`
  - 只存放已验证通过、适合作为稳定基线的内容。
- `work`
  - 当前日常开发与联调主线。
- `feature/*`、`fix/*`、`chore/*`
  - 默认从最新 `origin/main` 或明确指定分支切出，完成后经评审再合并回主线。

## 推荐阅读顺序

1. 先读 `docs/project/a20-fire-inspection-project-framework-2026-04-10.md`，明确比赛目标与系统闭环。
2. 再读 `docs/README.md`，找到当前项目、硬件与运维入口。
3. 若需快速判断现状，读 `docs/project/leap-project-overview.md`。
4. 若涉及固件、IO、泵控、micro-ROS 或网页控制，再读 `docs/hardware/firmware-current-state-2026-04-11.md`。
5. 若要查厂商资料，再进 `materials/cameras/`、`materials/lidar/`、`materials/robot/`。

## 常用命令

查看仓库状态：

```bash
git -C /home/gwh/leap status -sb
```

抽水工具：

```bash
cd /home/gwh/leap/ros2_ws/src/leap1/tools
./run_leap1_pump.sh --backend http --host 192.168.5.7 --pulse 2.0
```

固件编译：

```bash
cd /home/gwh/leap/firmware/leap_1_v1.1
pio run
```

ROS 2 编译：

```bash
source /opt/ros/humble/setup.bash
cd /home/gwh/leap/ros2_ws
colcon build --packages-select xuegecar_bringup
```

单入口启动：

```bash
source ~/.bashrc
ros2 launch xuegecar_bringup leap1_stack.launch.py
```
