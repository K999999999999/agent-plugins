# Issue tracker：本地 Markdown

本仓库的 Spec 和 Ticket 使用 `.scratch/` 下的 Markdown 文件保存。

## 使用约定

- 一个 Feature 使用一个目录：`.scratch/<feature-slug>/`
- Spec 文件为：`.scratch/<feature-slug>/spec.md`
- 实现 Ticket 每个使用一个独立文件：`.scratch/<feature-slug>/issues/<NN>-<slug>.md`，从 `01` 开始编号，不合并成单个 Tickets 文件
- 如需记录状态，在 Ticket 文件顶部使用 `Status:` 行，推荐状态为 `open`、`in-progress`、`done` 和 `blocked`
- 评论和会话历史追加到文件底部的 `## Comments` 区块下

## Skill 要求“发布到 Issue tracker”时

在 `.scratch/<feature-slug>/` 下创建文件；如果目录不存在，先创建目录。

## Skill 要求“获取相关 Ticket”时

读取指定路径的文件。用户通常会直接提供文件路径或 Ticket 编号。

## 任务关系

不配置 Wayfinding、Map 或 Frontier。需要表达任务关系时，在 Ticket 文件中使用简单的 `Blocked by:` 行。

- **阻塞关系**：在 Ticket 顶部使用 `Blocked by: 01, 02`，所有被阻塞的 Ticket 完成后再继续当前 Ticket。
- **Ticket 状态**：使用顶部的 `Status:` 行记录 `open`、`in-progress`、`done` 或 `blocked`。
- **完成 Ticket**：补充验证结果，在 `## Result` 区块记录结论，并将 `Status:` 更新为 `done`。
