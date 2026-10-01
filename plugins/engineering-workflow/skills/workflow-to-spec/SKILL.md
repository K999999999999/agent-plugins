---
name: workflow-to-spec
description: "需求已澄清且仓库事实已核实，需要固化为行为 Spec 时，整理范围、行为、决策和验证，并遵守目标仓库的确认 / 授权边界；有关键问题未决时先继续澄清。"
---

# 生成 Spec

把已确认的对话和仓库事实整理为行为 Spec。这是综合和固化，不是继续访谈；需求、术语、边界或 Contract 不清楚时返回 `workflow-grill-with-docs`。

## 选择 Spec 粒度

依据目标仓库规则、变更范围和风险选择短 Spec 或完整 Spec；不为了形式把小任务扩成完整文档，也不因任务名称小就略过会改变稳定 Contract 的关键设计。

- **短 Spec**：适用于范围局部、预期单会话完成且不改变稳定公共 Contract / 关键架构边界的改动。至少写清目标、预期结果、验收方式、验证方式和授权依据；按目标仓库约定简短保存。若目标仓库规定明确、稳定的用户任务构成实施授权，记录原指令后直接进入 `$workflow-implement`；否则取得一次必要确认。无需机械增加设计审查或 Ticket 拆分。
- **完整 Spec**：适用于多阶段、跨模块、有显著架构 / 领域 / 公共 Contract 影响或风险较高的改动。继续使用下方 Contract 模板，并只纳入适用的状态、失败 / 恢复行为、兼容性、数据、安全、迁移和交付约束。用户确认后进入 `$workflow-design-review`，通过后再拆分 Ticket。

如果规模或风险无法判断，先结合目标仓库规则检查证据；仍有会改变处理路径的重要不确定性时，返回 `workflow-grill-with-docs` 澄清。Spec 保存位置、命名、格式由目标仓库决定。

## 读取事实源

先读取目标仓库实际存在的 Agent instructions、Architecture、Domain、Engineering、ADR、上下文文档、Spec / Ticket 记录、相关代码和测试。Spec 的保存位置、命名、模板和状态规则以目标仓库为准；不要把本 Skill 或其他项目的路径假设写成仓库事实。

遵守目标项目定义的 Source of Truth 优先级，不把旧代码、Derived Artifact 或模型推测写成决定。发现用户描述与仓库事实冲突时，先报告冲突，不用 Spec 偷渡解决方案。

## 完整 Spec 参考模板

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

对完整 Spec，按需明确 Scope、输入输出、状态、异常、稳定 Contract、Architecture / Domain 影响、验证 seam、正常 / 边界 / 失败行为和非目标。根据任务情况补充：

- Change Profile：预期维护寿命、变更大小、风险、验证证据和交付方式；
- Observable Behavior：可能被调用者、用户、配置、日志、数据格式或下游系统依赖的可观察行为；
- Decision Record：重要方案、替代方案、取舍、决策依据、Owner 和未来 Revisit Trigger；
- Canonical Source：Spec、Design、Ticket、代码和文档的权威位置，避免多份互相竞争的真相；
- Compatibility / Migration：公共 Contract、Dependency、旧行为或旧数据需要兼容、迁移、Deprecated 或 Rollback 时的计划；
- Runtime Delivery：确有部署和用户流量时的 Rollout、监控、停止条件和 Rollback；
- Documentation：目标受众、What / When / Where / Why、维护 Owner 和生命周期。

不把上述字段机械加入每个小任务；仅在对应风险真实存在时写入。避免写具体源代码路径、大段代码或未经确认的未来能力。

## 交接门禁

写入后检查事实、术语、范围、Contract、测试边界和待确认项，并报告 Spec 路径。完整 Spec 必须由用户确认后才进入 `workflow-design-review`；创建或更新完整 Spec 本身不代表用户接受关键决定。短 Spec 按目标仓库授权规则处理：用户已给出稳定且完整的实施指令时不重复确认；否则先取得一次确认。用户意图只是整理 Spec 时，报告后停止；用户要求完成目标且授权已覆盖时，主 Agent 可在当前上下文继续调用下一阶段 Skill。不得因可隐式调用而绕过必要决定或授权。此 Skill 不创建外部 Issue、PR、Commit 或业务代码。
