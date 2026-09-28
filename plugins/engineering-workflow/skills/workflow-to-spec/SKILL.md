---
name: workflow-to-spec
description: "需求已澄清且仓库事实已核实，需要固化为行为 Spec 时，整理范围、行为、决策和验证供用户确认；有关键问题未决时先继续澄清。"
---

# 生成 Spec

把已确认的对话和仓库事实整理为行为 Spec。这是综合和固化，不是继续访谈；需求、术语、边界或 Contract 不清楚时返回 `workflow-grill-with-docs`。

## 读取事实源

先读取目标仓库实际存在的 Agent instructions、Architecture、Domain、Engineering、ADR、上下文文档、Spec / Ticket 记录、相关代码和测试。Spec 的保存位置、命名、模板和状态规则以目标仓库为准；不要把本 Skill 或其他项目的路径假设写成仓库事实。

遵守目标项目定义的 Source of Truth 优先级，不把旧代码、Derived Artifact 或模型推测写成决定。发现用户描述与仓库事实冲突时，先报告冲突，不用 Spec 偷渡解决方案。

## Spec 必须包含

```md
# 标题

## Problem Statement
## Solution
## User Stories
## Implementation Decisions
## Testing Decisions
## Out of Scope
## Further Notes
```

至少明确 Scope、输入输出、状态、异常、稳定 Contract、Architecture / Domain 影响、验证 seam、正常 / 边界 / 失败行为和非目标。根据任务情况补充：

- Change Profile：预期维护寿命、变更大小、风险、验证证据和交付方式；
- Observable Behavior：可能被调用者、用户、配置、日志、数据格式或下游系统依赖的可观察行为；
- Decision Record：重要方案、替代方案、取舍、决策依据、Owner 和未来 Revisit Trigger；
- Canonical Source：Spec、Design、Ticket、代码和文档的权威位置，避免多份互相竞争的真相；
- Compatibility / Migration：公共 Contract、Dependency、旧行为或旧数据需要兼容、迁移、Deprecated 或 Rollback 时的计划；
- Runtime Delivery：确有部署和用户流量时的 Rollout、监控、停止条件和 Rollback；
- Documentation：目标受众、What / When / Where / Why、维护 Owner 和生命周期。

不把上述字段机械加入每个小任务；仅在对应风险真实存在时写入。避免写具体源代码路径、大段代码或未经确认的未来能力。

## 交接门禁

写入后检查事实、术语、范围、Contract、测试边界和待确认项，向用户报告 Spec 路径并等待确认。用户确认后必须进入 `workflow-design-review`；不能直接进入 `workflow-to-tickets` 或实现。此 Skill 不创建外部 Issue、PR、Commit 或业务代码。
