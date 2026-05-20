# AGENTS.md

## Scope
- 本文件适用于 `/home/gwh/leap`，优先于上级 `/home/gwh/AGENTS.md`。
- 本仓库的长期工作流规则统一写在这里；如用户要求写入 `agent.md` 或 `AGENTS.md`，默认更新本文件。

## Output
- 默认使用中文回复。
- 先给结论，再给执行细节。

## Default Context
- 项目上下文入口：`/home/gwh/文档/Obsidian Vault/03_项目记录/Leap项目上下文入口_2026-04-27_22-02.md`。当用户要求“了解/接手 Leap 项目”时先读该入口。
- 当用户提到“leap 项目”“Leap 小车”“leap 仓库”或路径 `/home/gwh/leap` 时，先读取 `docs/README.md` 作为默认仓库入口。
- 若任务涉及项目要求、展示目标、系统闭环或 A20 方案，优先读取：
  - `docs/project/a20-fire-inspection-project-framework-2026-04-10.md`
  - `docs/project/leap-project-overview.md`
- 若任务涉及固件、网页控制、泵控制、IO、micro-ROS 传输或板级行为，再补充读取 `docs/hardware/firmware-current-state-2026-04-11.md`。
- 若任务涉及仓库合并来源、目录收口、分支策略或历史迁移，再补充读取 `docs/project/repository-merge-2026-04-10.md`。
- 若任务涉及相机或雷达资料，优先读取：
  - `docs/hardware/cameras/README.md`
  - `docs/hardware/lidar/README.md`
- 当前现役代码目录以 `firmware/`、`ros2_ws/`、`runtime/`、`docs/` 为准；`materials/` 与 `archives/` 默认视为资料层和历史层，不作为现役改动入口。

## Git Workflow
- `main` 只存放已经验证通过、适合作为稳定基线的代码，不在 `main` 上直接做长期开发、临时堆改动或并行试验。
- `work` 是默认开发分支；若无特殊说明，新的功能开发、调试修复和实验性改动都先落在 `work`。
- 开始任何非琐碎开发前，先从最新 `origin/main` 创建功能分支，例如 `feature/*`、`fix/*`、`chore/*`。
- 默认使用 `git worktree` 为每个并行任务创建独立工作目录，工作树统一放在 `/home/gwh/leap/worktrees/`。
- 功能完成后，先在对应功能分支或 `work` 自测，再提交、推送，并通过 PR 或评审式合并回 `main`。
- 若当前工作区出现未提交改动，不要继续在 `main` 上叠加新任务；先提交、stash，或迁移到独立分支/worktree 后再继续。
- 拉取远程更新前，先确认当前工作区干净，避免把本地实验性改动和同步动作混在一起。
- 涉及固件与 ROS 2 联动调整时，优先同时说明受影响的固件目录和 ROS 2 目录，避免只改一侧。

## Safety
- 不要自动回滚或覆盖用户已有改动。
- 对删除、覆盖、迁移这类不可逆操作，先列出候选项再执行。
- 清理 `archives/`、`materials/` 和历史 worktree 时，优先保留内容、去除 Git 绑定，而不是直接删除资料本体。

## Recording
- 多步骤调试、迁移、上传、发布与 PR 修复任务，按 `/home/gwh/docs/codex/recording-standard.md` 记录到 Obsidian。
