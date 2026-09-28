---
name: workflow-ticket-readiness
description: "Ticket 草案已经拆出、尚未正式写入或确认时，只读检查其范围、依赖、Owner、验收、迁移 / 回滚和验证计划是否足以安全实施。"
---

# Ticket Readiness Review

这是当前主 Agent 执行的只读门禁，不调用独立 Agent，不修改 Ticket、Spec、代码或测试，也不替代 `workflow-design-review`、实现后的 `workflow-code-review` 或 PR Review。

## 读取

读取已确认的 Spec、Ticket 草案、目标仓库的 Agent instructions、Issue / tracker 规则、Domain / Architecture / Contract，以及直接受影响的代码和测试。

## 检查

- Scope / Out of Scope；
- Lifetime、Size、Risk、Evidence 和 Delivery 的 Change Profile 是否与 Ticket 粒度匹配；
- 纵向行为是否完整；
- 直接依赖和循环依赖；
- owned files 和模块边界；
- 持续维护的 Module、测试、文档或 Migration 是否有明确 Owner；跨团队或高风险范围是否需要 Backup Owner / 升级路径；
- Spec、Ticket、Design、Contract 和实现说明是否有明确的 Canonical Source（权威来源），没有互相竞争的事实记录；
- 正常、边界和失败行为；
- Authorization、Data Scope、State、SQL Safety 或其他项目相关安全边界；
- Software Test、Integration Test、AI Evaluation、Business Acceptance、Runtime 和 Security 证据；
- 依赖、Lockfile、Framework 或构建变化是否有版本、兼容性、供应链和可复现构建验证；
- Deprecation、Migration、批量生成或大范围变化是否有 Discovery、Owner、切片、Milestone、独立测试、Review、Rollback / 恢复和防止 Backsliding 计划；
- 运行时发布是否需要 Feature Flag、Staged Rollout、监控停止条件和 Rollback；没有实际部署风险时不增加这些形式门禁；
- 可客观判断的 Done When；
- 是否仍有未解决的 Architecture、Domain、公共 Contract、权限或状态决策。

## 输出

```text
Ticket Readiness: READY | NEED FIX
Scope: <Feature、Spec 和 Ticket 草案>
Change Profile: <Lifetime / Size / Risk / Evidence / Delivery>
Owner: <主要 Owner、必要时 Backup Owner>
Findings:
- <问题、依据、影响、最小修复>
Dependencies: <依赖判断>
Migration / Rollback: <不适用，或已确认的迁移、恢复和防回退计划>
Evidence: <验证证据>
Next: <用户确认拆分，或返回 workflow-to-spec / workflow-design-review>
```

发现未决 Contract 或架构决定时必须 `NEED FIX`，不能在 Ticket 或代码中猜测。
