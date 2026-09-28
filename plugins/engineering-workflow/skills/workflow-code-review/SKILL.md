---
name: workflow-code-review
description: "代码或配置已有待审 Diff，且需要判断它是否满足 Spec / Ticket 时，进行只读实现 Review，检查正确性、范围、测试证据和受影响边界；不审查编码前设计。"
---

# Code Review

以 Ticket / Spec、BASE_SHA 和 owned files 为审查边界，只读取理解本次变更所需的内容，不扫描无关历史问题，不创建或等待独立 Agent，也不重复已通过的测试。

## 检查顺序

1. Acceptance Criteria、Contract、输入输出、错误、状态和不变量；
2. 变更是否单一、可审查，Change Description 是否说明 What、Why、Risk 和 Verification，是否混入无关重构、生成物或 Secret；
3. 正常、边界、失败行为是否有确定性证据，测试是否验证公共行为 / 状态而不是脆弱的实现细节或过度指定的 Interaction；
4. Correctness：实现是否正确，错误处理、权限、数据范围、SQL Safety、配置和日志行为是否符合 Contract；
5. Comprehension / Consistency：名称、控制流、公开接口和错误信息是否容易理解，是否遵循目标代码库已有约定，是否留下足够的变更原因；
6. 实际触及的 Architecture、Domain、依赖方向、公共 Contract、运行时和安全边界；
7. 变更是否让未来修改、测试、回滚或定位问题更困难，是否需要返回 `workflow-design-review` 或补充 Migration / Rollback 计划。

## Review 边界

- Code Review 检查已确认设计的实现，不借 Review 重新争论已经确认的架构方案；
- 如果实现必须改变 Module Boundary、公共 Contract、Dependency Direction 或重要设计决策，停止并返回 `workflow-design-review`；
- 机械格式、静态检查和可自动验证的规则交给项目已有工具，人工 Review 聚焦语义、可理解性、真实风险和维护成本；
- 小变更是降低 Review 和故障定位成本的优化目标，不以固定行数作为硬阈值；无法拆分的大变更必须说明原因、影响范围和额外验证。

测试结果只能证明对应的确定性软件行为，不自动证明 AI Evaluation、真实 Integration、Business Acceptance 或 Production Readiness。

## 输出

```text
Review: PASS | NEED FIX | BLOCKED
Scope: <BASE_SHA 和文件范围>
Change Description: <What / Why / Risk / Verification>
Findings:
- <严重度、文件、问题、依据和最小修复>
Review Dimensions: <Correctness / Comprehension / Consistency / Testability / Architecture / Security>
Tests: <已复用证据；没有则说明>
Next: <无需动作，或修复与受影响验证>
```
