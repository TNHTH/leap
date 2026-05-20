# Leap 第一轮瘦身清单 2026-04-12

- 时间：2026-04-12
- 目标：只清理归档目录、历史仓库和工作树中的可再生生成物，不触碰活跃仓库 `/home/gwh/leap` 的构建产物。

## 本轮执行删除

- `185M` `/home/gwh/leap/archives/imported/2026-04-11-legacy/leap_root_downloads/2026-03-12/Leap1_专用资料_2026-03-12/03_源码/leap_1_v1.1/.pio`
- `4.0K` `/home/gwh/leap/archives/imported/2026-04-11-legacy/leap_root_downloads/2026-03-12/leap1工具包/1.源码/leap_1_v1.1/build`
- `90M` `/home/gwh/leap/archives/imported/2026-04-11-legacy/leap_root_downloads/2026-03-12/leap1工具包/1.源码/leap_1_v1.1/.pio`
- `497M` `/home/gwh/leap/archives/imported/2026-04-11-legacy/leap_root_firmware/leap_1_v1.1/.pio`
- `51M` `/home/gwh/leap/archives/imported/2026-04-11-legacy/xuegeros_ws/build`
- `2.0M` `/home/gwh/leap/archives/imported/2026-04-11-legacy/xuegeros_ws/install`
- `2.6M` `/home/gwh/leap/archives/imported/2026-04-11-legacy/xuegeros_ws/log`
- `502M` `/home/gwh/leap/archives/repos/leap1-robot-code/firmware/leap_1_v1.1/.pio`
- `1.7M` `/home/gwh/leap/archives/repos/leap1-robot-code/ros2_ws/build`
- `156K` `/home/gwh/leap/archives/repos/leap1-robot-code/ros2_ws/install`
- `244K` `/home/gwh/leap/archives/repos/leap1-robot-code/ros2_ws/log`
- `507M` `/home/gwh/leap/worktrees/leap1-archive-original-debug/firmware/leap_1_v1.1/.pio`
- `508M` `/home/gwh/leap/worktrees/codex-fire-inspection-v1-flash/firmware/leap_1_v1.1/.pio`

## 保留未删

- 活跃仓库明确保留：
  - `/home/gwh/leap/firmware/leap_1_v1.1/.pio`
  - `/home/gwh/leap/ros2_ws/build`
  - `/home/gwh/leap/ros2_ws/install`
  - `/home/gwh/leap/ros2_ws/log`
- 本轮未纳入清理、留待下轮复核的候选：
  - `50M` `/home/gwh/leap/archives/imported/2026-04-11-legacy/xuegeros_ws/build_syspy`
  - `1.8M` `/home/gwh/leap/archives/imported/2026-04-11-legacy/xuegeros_ws/install_syspy`
  - `768K` `/home/gwh/leap/archives/imported/2026-04-11-legacy/xuegeros_ws/log_syspy`

## 可再生依据

- `.pio`：可由 PlatformIO 在对应固件目录重新构建
- `ros2_ws/build`、`ros2_ws/install`、`ros2_ws/log`：可由 `colcon build` 重新生成
- `xuegeros_ws/build`、`xuegeros_ws/install`、`xuegeros_ws/log`：属于历史工作区构建产物，可由旧工作区重新生成

