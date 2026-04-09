# AGENTS.md

## Scope
- 本文件适用于 `/home/gwh/leap/repos/leap1-robot-code`，优先于上级 `/home/gwh/AGENTS.md`。
- 本仓库的长期工作流规则统一写在这里；如用户要求写入 `agent.md` 或 `AGENTS.md`，默认更新本文件。

## Output
- 默认使用中文回复。
- 先给结论，再给执行细节。

## Git Workflow
- `main` 只作为同步基线使用，不在 `main` 上直接做长期开发、临时堆改动或并行试验。
- 开始任何非琐碎开发前，先从最新 `origin/main` 创建功能分支，例如 `feature/*`、`fix/*`、`chore/*`。
- 默认使用 `git worktree` 为每个并行任务创建独立工作目录，避免多个任务共用同一工作区。
- 功能完成后，先在对应功能分支自测，再提交、推送，并通过 PR 合并回 `main`。
- 若当前工作区出现未提交改动，不要继续在 `main` 上叠加新任务；先提交、stash，或迁移到独立分支/worktree 后再继续。
- 拉取远程更新前，先确认当前工作区干净，避免把本地实验性改动和同步动作混在一起。

## Safety
- 不要自动回滚或覆盖用户已有改动。
- 对删除、覆盖、迁移这类不可逆操作，先列出候选项再执行。

## Recording
- 多步骤调试、迁移、上传、发布与 PR 修复任务，按 `/home/gwh/docs/codex/recording-standard.md` 记录到 Obsidian。
