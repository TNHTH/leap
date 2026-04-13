# Leap 仓库合并与收口记录

- 创建时间：2026-04-10
- 最近更新：2026-04-13
- 目的：记录 Leap 小车从分散仓库到统一顶层仓库的收口过程，便于后续协作、评审和追溯。

## 合并来源

- 固件与整车基线来源：历史仓库 `archives/repos/leap1-robot-code`
- ROS 2 开发线来源：历史工作区 `archives/imported/2026-04-11-legacy/xuegeros_ws/src/leap1`

## 当前仓库结构

```text
archives/
docs/
firmware/leap_1_v1.1
materials/
ros2_ws/src/leap1
runtime/
worktrees/
```

## 分支策略

- `main`
  - 保存已确认稳定的整车基线
- `work`
  - 保存当前 ROS 2 开发线与后续日常修改

## 收口里程碑

- 2026-04-10
  - 建立统一仓库历史，把固件主线与 ROS 2 开发线合并到同一 Git 历史中。
- 2026-04-11
  - 把资料层、历史层和并行工作树放到顶层目录，形成“现役代码 + 资料 + 归档 + worktrees”的工作区布局。
- 2026-04-13
  - 把现役仓库根正式提升为 `/home/gwh/leap`。
  - 将 `docs/`、`firmware/`、`ros2_ws/`、`runtime/` 与 `archives/flashed-firmware/` 抬升到顶层。
  - 移除旧的内层现役入口与符号链接入口，不再保留双入口结构。
  - 历史 worktree 统一归档到 `archives/worktrees/2026-04-13-pre-top-level-root/`。
  - 历史仓库保留在 `archives/repos/`，但后续只作为普通历史副本使用。

## 当前操作合同

- 唯一仓库根：`/home/gwh/leap`
- 现役代码入口：
  - `firmware/leap_1_v1.1`
  - `ros2_ws/src/leap1`
  - `runtime/`
  - `docs/`
- 资料层：
  - `materials/` 保存厂商资料、历史参数、PDF 与参考包
- 归档层：
  - `archives/` 保存旧快照、烧录固件与历史 worktree
- 并行开发层：
  - `worktrees/` 只用于未来顶层仓库的 `git worktree`

## 备注

- `_legacy_2026-04-11` 仍作为旧导入快照的历史别名保留，但不作为现役入口。
- 后续凡是说明仓库路径、启动命令或阅读顺序，都应以 `/home/gwh/leap` 为基准，不再引用旧入口结构。
