---
title: Leap 仓库治理清单
created: 2026-04-25
type: repository-hygiene
status: implemented
---

# Leap 仓库治理清单

## 结论

本轮治理不改写 Git 历史、不删除本地资料实体，只从当前分支的 Git 索引移除生成物、历史导入副本和不应版本管理的二进制交付物。这样可以降低日常 diff 噪音，避免队友或自动化工具误改历史目录，同时保留本机资料可查。

## 本轮处理范围

- 从索引移除 `archives/imported/`、`archives/worktrees/`、`archives/repos/`。
- 从索引移除 `ros2_ws/build/`、`ros2_ws/install/`、`ros2_ws/log/`。
- 从索引移除 `firmware/leap_1_v1.1/.pio/`。
- 从索引移除 `__pycache__/`、`.pytest_cache/`。
- 从索引移除 `.bin`、`.elf`、`.exe`、`.log` 交付物。
- 更新 `.gitignore`，避免上述文件再次进入版本管理。

## 发现摘要

- 本轮从 Git 索引移除的历史、生成物和二进制条目：1763 个。
- 清理后 `git ls-files` 中历史归档、生成目录、缓存和 `.bin/.elf/.exe/.log` 匹配数：0 个。
- 最大重复二进制为厂商烧录工具 `xueger_tool.exe`，单文件约 43 MB，存在于 `materials/robot/...` 和 `archives/imported/...`。
- 固件构建产物 `firmware.elf` 约 28 MB，属于 PlatformIO 生成物。
- ROS2 与 micro-ROS 构建日志分布在 `ros2_ws/log/` 和 `.pio/libdeps/.../log/`，属于运行产物。
- 厂商 PDF 暂保留在 `materials/`，作为资料层索引，不在本轮删除或迁移。

## 后续建议

- 已发布固件 `.bin` 应进入 GitHub Release，并在仓库中只保留版本、SHA256 和烧录说明。
- 厂商资料继续保留在 `materials/`，但长期可改为外部资料索引，避免主仓库体积继续增长。
- 如果后续需要彻底缩小远端仓库历史体积，再单独规划 `git filter-repo`，并提前通知所有协作者重新 clone。
