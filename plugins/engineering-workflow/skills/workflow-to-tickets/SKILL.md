---
name: workflow-to-tickets
description: "把已确认且通过设计审查的 Spec 拆分为可独立验证、可审查、可回滚或可迁移的纵向 Ticket。"
---

# 拆分 Ticket

前置条件是 Spec 已确认，且 `workflow-design-review` Verdict 为 `PASS` 或 `PASS WITH MINOR FIXES`。没有可追溯审查结果时先返回设计审查。

Ticket 的媒介和保存位置以目标仓库为准：可以是本地 Markdown、外部 Issue tracker，或项目规定的其他记录。不要因为本 Skill 默认使用某一种媒介，就绕过目标仓库的项目规则。

## 拆分原则

- 每个 Ticket 是一个狭窄但完整的纵向行为切片；
- 每个 Ticket 记录 Change Profile、主要 Owner，必要时记录 Backup Owner、Canonical Source 和失败 / 升级路径；
- 优先覆盖用户可观察行为和已有测试 seam，不按数据库 / 服务 / 测试机械水平切片；
- `Blocked by` 只记录直接启动依赖，不制造循环依赖；
- 不混入无关重构、清理、未来能力或未经确认的架构选择；
- 小变更优先保持单一目标和短生命周期；不要创建长期集成 Ticket 或把多个无关目标串成一个 PR；
- 宽重构、公共 Contract 迁移、旧系统删除或批量生成修改只有确有必要时才使用 Expand → Migrate → Contract，并读取 [Migration and Large-Scale Change](references/migration-and-large-scale-change.md)；
- 需要发布到真实用户或运行时环境时，明确 Feature Flag、Staged Rollout、监控和 Rollback 是否适用；不对没有运行时风险的项目强制增加这些步骤。

## 交接流程

先展示草案，不写正式 Ticket。每条草案包含 Title、Change Profile、Owner、Blocked by、What to build、Acceptance Criteria、owned files、验证证据、Migration / Rollback（如适用）和 Done When。草案生成后必须由当前主 Agent 执行 `workflow-ticket-readiness`，结果为 `READY` 后再请求用户确认粒度和依赖。

用户确认后，按目标仓库规定写入或同步正式 Ticket。正式 Ticket 至少能追溯 What to build、Blocked by、Status、Owner、Acceptance criteria、Result、Comments 和验证证据；迁移或大范围变更还要能追溯切片、失败处理和防止 Backsliding 的状态。写入后不要自动实现，等待用户选择具体 Ticket。
