---
name: setup-matt-pocock-skills
description: "为当前仓库配置本地 Markdown 任务、Spec、Ticket 和领域文档布局。首次使用其他工程 Skills 前运行一次。"
---

# 配置本地工程 Skills

为当前仓库建立工程 Skills 所需的最小项目配置：

- **Local task tracker**：使用 `.scratch/` 保存 Spec 和 Ticket
- **Domain docs**：约定 `CONTEXT.md` 和 ADR 的位置，以及读取规则

本 Skill 是一个由对话驱动的初始化流程，不是确定性脚本。先探索，再展示发现和草稿，得到用户确认后才写入。

本 Skill 不配置外部任务系统、远程任务同步、PR、Triage labels 或 Wayfinding。远程仓库如果存在，只用于代码 Push，不作为 Spec / Ticket 的存储位置。

## 流程

### 1. 探索

读取当前仓库，了解实际起点，不要假设文件已经存在：

- 根目录的 `AGENTS.md` 和 `CLAUDE.md`：是否存在？是否已经有 `## Agent skills` 区块？
- 根目录的 `CONTEXT.md` 和 `CONTEXT-MAP.md`
- `docs/adr/` 以及任何 `src/*/docs/adr/` 目录
- `docs/agents/`：本 Skill 是否已经生成过配置？
- `.scratch/`：是否已经存在本地 Spec / Ticket 约定？
- Monorepo 信号：`pnpm-workspace.yaml`、`package.json` 中的 `workspaces` 字段，或包含独立 `src/` 的 `packages/*`。没有这些信号时，按 single-context 处理；如果发现这些信号，不要静默套用 single-context，先展示发现并请求用户确认上下文归属，确认前不写入配置。

### 2. 展示发现并确认

总结已有内容和缺失内容，然后给出本地配置方案。对未检测到 Monorepo 信号的仓库，本 Skill 固定使用 Local markdown + single-context，不再询问外部 Issue tracker 或 Triage labels 的选择；检测到 Monorepo 信号时，必须先确认上下文归属，不直接进入写入流程。

如果仓库已有明确的本地任务约定，优先复用；如果没有，推荐：

- Spec 和 Ticket 保存在 `.scratch/<feature>/`；
- 每个 Ticket 使用独立 Markdown 文件；
- 使用 single-context 结构；
- `CONTEXT.md` 和 ADR 只在真正需要时懒创建。

请用户确认这个本地方案，确认后进入草稿阶段。

### 3. 展示草稿

向用户展示以下内容的草稿：

- 要编辑的 `AGENTS.md` 或 `CLAUDE.md` 中的 `## Agent skills` 区块；
- `docs/agents/issue-tracker.md`；
- `docs/agents/domain.md`。

让用户检查并修改草稿，确认后再写入。

### 4. 写入

**选择要编辑的文件：**

- 如果只存在 `CLAUDE.md`，编辑 `CLAUDE.md`；
- 如果只存在 `AGENTS.md`，编辑 `AGENTS.md`；
- 如果 `AGENTS.md` 和 `CLAUDE.md` 同时存在，先读取两者，依据其中明确声明的规则优先级或相互引用确认主规则文件；无法确认时询问用户，不要自行选择；
- 如果两者都不存在，询问用户要创建哪一个，不要自行选择。

如果目标文件已经有 `## Agent skills` 区块，就原地更新，不要重复追加，也不要覆盖周围的用户内容。

写入以下配置：

- `docs/agents/issue-tracker.md`：使用本地 Markdown 模板；
- `docs/agents/domain.md`：使用 single-context 领域文档规则；
- `AGENTS.md` 或 `CLAUDE.md`：写入 `## Agent skills` 区块。

除非用户明确要求，否则不要现在创建 `CONTEXT.md`、`CONTEXT-MAP.md` 或 `docs/adr/`。这些文件由 `/domain-modeling` 在真正出现领域术语或不可逆决策时按需创建。

不要修改源代码、测试、数据库、远程仓库或外部 Issue / PR。

### 5. 完成

告诉用户配置已完成，以及后续会读取这些文件的工程 Skills。说明用户以后可以直接编辑 `docs/agents/*.md`；只有切换本地任务约定或重新开始配置时才需要再次运行本 Skill。

## `AGENTS.md` / `CLAUDE.md` 区块

默认写入：

```markdown
## Agent skills

### Issue tracker

本仓库使用本地 Markdown 保存 Spec 和 Ticket，文件位于 `.scratch/<feature>/`。详见 `docs/agents/issue-tracker.md`。

### Domain docs

本仓库采用 single-context 结构。处理领域相关任务前，读取 `CONTEXT.md` 和 `docs/adr/` 下相关 ADR。详见 `docs/agents/domain.md`。
```
