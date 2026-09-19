---
name: ask-matt
description: "显式启动通用工程工作流，按需求阶段、软件生命周期、变更大小和风险路由到 Spec、Design Review、Ticket、TDD、Review 或 PR 交付。"
---

# 通用工程流程路由

使用 `$ask-matt` 作为工程任务的入口。先读取目标仓库的 `AGENTS.md`、`CLAUDE.md`、相关 `docs/agents/`、项目上下文文档、工作记录和 Git 状态，再依据目标仓库的规则判断任务应该进入哪个阶段。

本 Skill 是 router（路由器），不是隐式状态机。它可以路由到本包的阶段 Skill，但不能替代目标仓库的规则、测试、CI 或用户确认提供的硬门禁。每次跨阶段都要说明当前阶段、输入事实、完成条件和是否需要用户确认。

## 先判断变更形状

在路由前先记录以下 Change Profile（变更画像）：

- **Lifetime**：临时实验、短期工具，还是预计长期维护的代码、文档或配置；
- **Size**：局部小改动、普通 Feature，还是跨模块 / 跨团队 / 批量迁移；
- **Risk**：是否影响公共 Contract、Authorization、State、Data Scope、Dependency、Runtime、Deployment 或 Security；
- **Evidence**：需要 Software Test、Integration Test、AI Evaluation、Business Acceptance、Runtime 或 Security 哪些证据；
- **Delivery**：是否准备合入默认分支，是否需要 Rollout / Rollback / Feature Flag。

小而稳定的改动可以采用轻量路径；长期维护的普通变更进入标准路径；Deprecation、Migration、全局重命名、自动生成的大范围修改或运行时高风险变化必须提高规划和验证级别。不要用代码行数作为唯一标准，也不要让长期 Feature branch 变成未经验证的集成线。详细规则见 [Change Shaping](references/change-shaping.md)。

## 标准路由

```text
需求
  → workflow-grill-with-docs（目标、术语、事实和边界不清时）
  → workflow-to-spec（形成可确认的行为 Contract）
  → 用户确认 Spec
  → workflow-design-review（编码前只读审查）
  → workflow-to-tickets（拆分纵向 Ticket）
  → workflow-ticket-readiness（检查 Ticket 是否可实施）
  → 用户确认 Ticket 拆分
  → workflow-implement
       → workflow-tdd（行为变化时）
       → 确定性测试
       → workflow-code-review（当前上下文轻量 Review）
       → 本地 Commit
  → workflow-delivery（candidate、PR、Auto-merge 和清理）
```

## 阶段判断

### 1. 需求或边界不清

使用 `$workflow-grill-with-docs`。一次只问一个最能减少不确定性的关键问题，优先确认目标、用户场景、领域术语、范围、Contract 和验收条件。不要在需求未确认前实现代码、创建正式 Ticket 或创建 PR。

### 2. 需求清楚但没有行为 Contract

使用 `$workflow-to-spec`。Spec 的保存位置、格式和命名以目标仓库的规则为准；如果仓库没有规定，先提出最小约定，不把某个项目的路径假设带入其他仓库。Spec 未经用户确认不能作为实现授权。

### 3. Spec 已确认但未审查

使用 `$workflow-design-review`。只有 `PASS` 或 `PASS WITH MINOR FIXES` 才能进入 Ticket；`NEED FIX` 或 `BLOCKED` 返回 Spec / 设计阶段。

### 4. 需要拆分实现任务

使用 `$workflow-to-tickets`。它先展示 Ticket 草案，不在用户确认前写入正式 Ticket。草案必须经过 `$workflow-ticket-readiness` 的 `READY` 检查，并遵循目标仓库对本地记录或外部 tracker 的规定。

### 5. Ticket 已确认

使用 `$workflow-implement`。读取 Ticket、Spec、相关 Contract 和仓库规则；行为变化执行 TDD，运行 targeted tests，在当前上下文完成轻量 `code-review`，通过后只创建本地 Commit。

### 6. 需要直接补测试或审查已有变更

- 用户明确要求测试驱动开发时，使用 `$workflow-tdd`。
- 用户明确要求检查已有实现时，使用 `$workflow-code-review`。
- 这些 Skill 不自动创建独立 Agent，不替代范围控制或用户授权。

### 7. 形成可合入 candidate

使用 `$workflow-delivery`。它依据目标仓库规则判断是否需要进入 PR：

- 计划合入默认分支的代码、文档或配置变化，通常进入 `Feature branch → candidate → PR → required checks → Auto-merge → 合并后清理`；
- 小修改可以跳过不必要的 Spec / Ticket，但不能跳过相关测试、Diff Review、candidate 检查和适用的 PR 门禁；变更应保持单一目标、可审查且 Feature branch 尽快结束；
- 大范围迁移、批量重命名、旧 Contract 删除或自动生成变更，先进入 `workflow-to-tickets` 的 Migration / Large-Scale Change 规划，不把大批量修改伪装成普通小 Ticket；
- 运行时或部署变化若需要逐步启用、监控和回滚，交给 `workflow-delivery` 按目标仓库规则形成 Rollout / Rollback 计划；不对没有运行时发布的项目强制增加 Feature Flag；
- 只读咨询、诊断报告和不准备合入仓库的临时实验不进入 PR。

目标仓库明确允许直接提交或具有不同交付规则时，以目标仓库规则为准；本 Skill 不把 PR、Auto-merge 或完整 Real E2E 强加给不适用的项目。

## 不可跳过的授权边界

- 用户确认 Spec 不等于实现授权。
- 用户确认 Ticket 不等于 Push、PR 或 Merge 授权。
- 形成 candidate 后必须先向用户说明目标、Commit 范围、风险、缺失验证和后续外部动作。
- 只有用户明确确认后，才能进行最终验收、Push 和创建或更新 PR。
- Agent 不直接执行 Merge；遵循目标仓库的自动化和分支保护规则，并验证真实 PR 状态。
- PR 已合并且清理条件全部满足后，才回到默认分支、同步合并结果并清理本次 Feature branch / worktree。

## 默认协作边界

默认由当前主 Agent 连续完成需求、Spec、Ticket、实现、Review、验收和 Commit；不调用或等待独立 Agent，不使用双独立审查。只有用户和目标项目规则都明确允许时，才改变该边界。

## 路由输出

每次路由使用以下结构：

```text
当前阶段: <需求澄清 | Spec | 设计审查 | Ticket | Ticket Readiness | 实现 | 测试 | Review | candidate / PR 交付>
使用 Skill: <skill>
Change Profile: <Lifetime / Size / Risk / Evidence / Delivery>
原因: <为什么当前进入这个阶段>
输入事实: <已经读取或确认的事实>
完成条件: <本阶段 Done When>
需要用户确认: <是 / 否，以及确认会授权什么>
边界: <本阶段不做什么>
```

详细 Ticket 门禁见 `references/ticket-readiness.md`；详细 PR 和清理门禁见 `references/delivery-gates.md`；跨阶段上下文处理见 `references/phase-boundaries.md`；目标仓库适配规则见 `references/project-adapter.md`。
