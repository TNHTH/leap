# leap 仓库合并记录

- 创建时间：2026-04-10
- 目的：把 Leap 小车原先分散的固件仓库与 ROS 2 仓库合并为一个新的统一仓库，降低协作成本。

## 合并来源

- 固件与整车基线来源：`/home/gwh/leap/repos/leap1-robot-code`
- ROS 2 开发线来源：`/home/gwh/xuegeros_ws/src/leap1`

## 新仓库结构

```text
archives/flashed-firmware
firmware/leap_1_v1.1
ros2_ws/src/leap1
```

## 分支策略

- `main`
  - 保存已确认稳定的整车基线
- `work`
  - 保存当前 ROS 2 开发线与后续日常修改

## 迁移说明

- `main` 基于原整车聚合仓库当前稳定基线建立。
- `work` 在 `main` 基础上导入 `/home/gwh/xuegeros_ws/src/leap1` 的提交历史到 `ros2_ws/src/leap1/`。
- 旧仓库暂不删除，作为历史备份保留。
