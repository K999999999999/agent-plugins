---
name: ask-matt
description: "用户明确要求判断工程任务所处阶段或推荐下一步时，读取仓库规则并路由到一个 workflow Skill；只给建议后停止，不执行工作流。"
---

# 通用工程流程路由

`$ask-matt` 是可选的阶段路由器，仅在用户主动询问“现在在哪个阶段 / 下一步该做什么”或明确要求路由建议时使用。它不是新会话或工程任务的必经入口。目标仓库的 `AGENTS.md` 可以独立规定新会话状态恢复；不要用本 Skill 代替仓库规则要求的检查。

路由前读取目标仓库适用的 `AGENTS.md`、`CLAUDE.md`、相关 `docs/agents/`、项目上下文文档、工作记录和 Git 状态，再依据仓库规则判断阶段。首先区分：用户尚无候选目标时是 `需求发现`；已有候选目标但重要行为、范围、边界或验收不清时是 `需求澄清`。

本 Skill 是可选 router（路由器），不是新会话或工程任务的必经入口。它可以路由到本包的阶段 Skill 或独立专项 Skill，但不能替代目标仓库的规则、测试、CI 或用户确认提供的硬门禁。用户主动要求导航时，每次只推荐一个最合适的下一步，给出明确 Skill 调用和简短原因后立即停止；它本身不执行工作流。其他阶段 Skill 可由当前主 Agent 按任务上下文调用，用户不必逐阶段手动触发。调用方式不会跳过 Spec、实施范围、关键方案、Ticket 拆分或发布授权门禁。

## 先判断变更形状

在路由前先记录以下 Change Profile（变更画像）：

- **Lifetime**：临时实验、短期工具，还是预计长期维护的代码、文档或配置；
- **Size**：局部小改动、普通 Feature，还是跨模块 / 跨团队 / 批量迁移；
- **Risk**：是否影响公共 Contract、Authorization、State、Data Scope、Dependency、Runtime、Deployment 或 Security；
- **Evidence**：需要 Software Test、Integration Test、AI Evaluation、Business Acceptance、Runtime 或 Security 哪些证据；
- **Delivery**：是否准备合入默认分支，是否需要 Rollout / Rollback / Feature Flag。

小而稳定的改动可以采用轻量路径；长期维护的普通变更进入标准路径；Deprecation、Migration、全局重命名、自动生成的大范围修改或运行时高风险变化必须提高规划和验证级别。不要用代码行数作为唯一标准，也不要让长期 Feature branch 变成未经验证的集成线。详细规则见 [Change Shaping](references/change-shaping.md)。

## 标准路由

在普通工程阶段路由前，先识别两个需要用户手动选择的专用入口：

- 如果用户明确要求为当前仓库初始化工程工作流，推荐 `$setup-engineering-workflow`；它只在用户手动调用时运行，不因 Plugin 安装或配置缺失自动启动。推荐后停止。
- 如果目标跨多个模块或 session，规模很大且关键决策路径尚不清楚，推荐 `$wayfinder`。普通单项需求澄清继续使用 `$workflow-grill-with-docs`。推荐后停止，不自动创建规划地图。

其他任务按以下工作流路由：

```text
问题 / 机会但尚无候选目标
  → workflow-discovery（探索问题、证据、候选结果和选项）
已有候选目标但行为 / 范围 / 边界 / 验收有重要歧义
  → workflow-grill-with-docs（需求澄清）
目标结果和范围足够明确
  → workflow-to-spec（按目标仓库规则形成短 / 完整 Spec）
  → 用户确认（完整 Spec 必须确认；短 Spec 按目标仓库授权规则判断是否需要）
       ├─ 短 Spec / 单会话小改动 → 已明确授权则 workflow-implement；否则一次确认
       └─ 完整 Spec / 多阶段工作（用户确认后）
            → workflow-design-review（编码前只读审查）
            → workflow-to-tickets（拆分纵向 Ticket）
            → workflow-ticket-readiness（检查 Ticket 是否可实施）
            → 用户确认 Ticket 拆分；整体实施授权已覆盖时按依赖连续执行全部 Ticket，不逐项等待选择
            → workflow-implement
  → workflow-tdd（行为变化时）
  → 确定性测试
  → workflow-code-review（当前上下文轻量 Review）
  → 本地 Commit
  → workflow-delivery（candidate、PR、Auto-merge 和清理）
```

## 阶段判断

### 1. 尚无候选目标：需求发现

使用 `$workflow-discovery`。当用户知道问题或机会、但还不知道应该追求什么结果时，先检查相关事实，与用户探索证据、候选结果和选项。不要把探索当成已澄清需求或自动形成实施授权。

### 2. 已有候选目标但边界不清：需求澄清

使用 `$workflow-grill-with-docs`。一次只问一个最能减少不确定性的关键问题，优先确认目标、用户场景、领域术语、范围、Contract 和验收条件。不要在需求未确认前实现代码、创建正式 Ticket 或创建 PR。

### 3. 需求清楚但没有行为 Contract

使用 `$workflow-to-spec`。由目标仓库规则和变更规模决定短 Spec 或完整 Spec。短 Spec 至少写明目标、预期结果、验收方式和验证方式；范围稳定且目标仓库认可用户明确任务作为授权时，记录该依据后可直接实施，不重复确认短 Spec，否则一次确认。完整 Spec 面向多阶段工作，须先由用户确认，再继续设计审查和 Ticket 流程。Spec 的保存位置、格式和命名以目标仓库规则为准；如果仓库没有规定，先提出最小约定，不把某个项目的路径假设带入其他仓库。

### 4. Spec 已确认但未审查

使用 `$workflow-design-review`。只有 `PASS` 或 `PASS WITH MINOR FIXES` 才能进入 Ticket；`NEED FIX` 或 `BLOCKED` 返回 Spec / 设计阶段。

### 5. 需要拆分实现任务

使用 `$workflow-to-tickets`。它先展示 Ticket 草案，不在用户确认前写入正式 Ticket。草案必须经过 `$workflow-ticket-readiness` 的 `READY` 检查，并遵循目标仓库对本地记录或外部 tracker 的规定。确认拆分后，如果用户已授权完成整个目标，Agent 按依赖连续实施全部 Ticket；没有整体授权时一次确认具体实施范围，不逐 Ticket 询问是否继续。

### 6. Ticket 已确认

使用 `$workflow-implement`。读取 Ticket、Spec、相关 Contract 和仓库规则；行为变化执行 TDD，运行 targeted tests，在当前上下文完成 `$workflow-code-review`，通过后按项目规则创建本地 Commit。完整目标已获授权时跨 Ticket 连续推进；实现 Review 不是额外的用户 PR Review。

### 7. 需要直接补测试或审查已有变更

- 用户明确要求测试驱动开发时，使用 `$workflow-tdd`。
- 用户明确要求检查已有实现时，使用 `$workflow-code-review`。
- 这些 Skill 不自动创建独立 Agent，不替代范围控制或用户授权。

### 8. 形成可合入 candidate

使用 `$workflow-delivery`。它依据目标仓库规则判断是否需要进入 PR：

- 计划合入默认分支的代码、文档或配置变化，通常进入 `Feature branch → candidate → PR → required checks → Auto-merge → 合并后清理`；
- 小修改可以跳过不必要的 Spec / Ticket，但不能跳过相关测试、Diff Review、candidate 检查和适用的 PR 门禁；变更应保持单一目标、可审查且 Feature branch 尽快结束；
- 大范围迁移、批量重命名、旧 Contract 删除或自动生成变更，先进入 `workflow-to-tickets` 的 Migration / Large-Scale Change 规划，不把大批量修改伪装成普通小 Ticket；
- 运行时或部署变化若需要逐步启用、监控和回滚，交给 `workflow-delivery` 按目标仓库规则形成 Rollout / Rollback 计划；不对没有运行时发布的项目强制增加 Feature Flag；
- 只读咨询、诊断报告和不准备合入仓库的临时实验不进入 PR。

目标仓库明确允许直接提交或具有不同交付规则时，以目标仓库规则为准；本 Skill 不把 PR、Auto-merge 或完整 Real E2E 强加给不适用的项目。

## 专项能力路由

当用户的问题属于独立专项能力，而不是主工作流阶段时，推荐最匹配的一项并停止：

| 用户目标 | 推荐 Skill | 适用边界 |
|---|---|---|
| 诊断已有 Bug、异常、测试失败或性能回归 | `/diagnosing-bugs` | 定位现有故障；不默认进入修复 |
| 查证仓库外部事实、第三方 API 或当前版本行为 | `/research` | 一手资料研究并记录来源 |
| 快速验证具体逻辑、状态模型、数据形状或 UI 方案 | `/prototype` | 一次性原型；不作为正式实现 |
| 设计具体模块的接口、Seam 或测试边界 | `/codebase-design` | 单模块设计；不做全仓架构扫描 |
| 校准领域概念、术语、边界场景或业务规则 | `/domain-modeling` | 领域模型；不替代一般需求澄清 |
| 寻找代码库或子系统的架构改进机会 | `/improve-codebase-architecture` | 只读探索并提出候选；不直接重构 |
| 保持业务行为不变，修复已明确的局部维护性问题 | `/maintainability-refactor` | 有范围的重构；不实现功能或改造整体架构 |
| 解决当前 Git Merge / Rebase 冲突 | `/resolving-merge-conflicts` | 仓库已处于冲突状态 |
| 引导用户完成 AI 无法代办的人工配置或迁移步骤 | `/wizard` | 一次性交互式本地向导 |

完整工作流阶段同样按前面的标准路由推荐具体 Skill。用户要求导航时，无论推荐工作流 Skill 还是专项 Skill，都只报告调用名称和原因，不继续执行。

## 不可跳过的授权边界

- 完整 Spec 确认和 Ticket 拆分确认不是实施授权；一次整体授权可以覆盖按依赖完成整个目标，无需逐 Ticket 再授权。
- 发布授权独立于实施授权。发布前说明目标、提交范围、风险、验证证据和目标仓库的自动合并行为；明确授权后，同一目标 / 范围内的 PR 更新、CI 修复、复盘和安全清理不重复询问。
- 用户确认 Ticket 不等于 Push、PR 或 Merge 授权。
- candidate 形成后，先在聊天说明目标、Commit 范围、风险、验证证据和后续外部动作，再取得发布授权。
- 只有用户明确授权后，才能 Push 或创建 / 更新 PR。
- Agent 不直接执行 Merge；遵循目标仓库的自动化和分支保护规则，并验证真实 PR 状态。
- PR 已合并且清理条件全部满足后，才回到默认分支、同步合并结果并清理本次 Feature branch / worktree。

## 默认协作边界

默认由当前主 Agent 连续完成需求、Spec、Ticket、实现、Review、验收和 Commit；不调用或等待独立 Agent，不使用双独立审查。只有用户和目标项目规则都明确允许时，才改变该边界。

## 路由输出

每次路由使用以下结构：

```text
当前阶段: <阶段名称>
推荐 Skill: /<skill-name>
原因: <为什么这是下一步；一句话>
```

详细 Ticket 门禁见 `references/ticket-readiness.md`；详细 PR 和清理门禁见 `references/delivery-gates.md`；跨阶段上下文处理见 `references/phase-boundaries.md`；目标仓库适配规则见 `references/project-adapter.md`。
