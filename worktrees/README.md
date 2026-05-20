# Worktrees

`/home/gwh/leap/worktrees` 只用于顶层仓库的 `git worktree` 并行开发。

使用约定：

- 不在这里存放资料、日志、下载包或历史快照。
- 每个并行任务使用独立子目录，任务结束后及时回收或归档。
- 若需要保留历史工作树内容，先迁入 `archives/worktrees/`，再移除 Git 绑定。
