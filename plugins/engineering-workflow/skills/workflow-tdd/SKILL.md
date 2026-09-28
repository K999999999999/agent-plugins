---
name: workflow-tdd
description: "为已确定的功能或行为变更建立测试时，按 Red-Green-Refactor 编写并验证确定性测试；不用于只定位既有故障原因或代码 Review。"
---

# Test-Driven Development

读取当前 Ticket / Spec、`AGENTS.md`、Domain、Architecture 和已有测试，先确定最高且真实的测试 seam。行为测试优先通过公共接口观察结果，不绑定私有实现、调用顺序或偶然结构。

当新增或修改 Test Double、Integration Test、End-to-End Test、测试共享代码或 Flaky Test 时，读取 [Test Maintainability](references/test-maintainability.md)。

## 循环

```text
一个行为
  → Red：先写有意义的失败测试
  → Green：最小实现使其通过
  → Refactor：保持绿色整理设计
```

Red 必须因目标 Contract 尚未实现而失败，不能是导入、路径或环境错误；Green 不得削弱断言、跳过测试或加入测试专用生产分支；Refactor 不改变外部行为。逐个推进正常、边界、空值、失败、权限和重复请求等已确认场景。

区分 Software Test、Integration Test、AI Evaluation 和 Business Acceptance。确定性测试不应无意依赖真实 LLM、外部 API、生产数据库、网络或不可控时间。完成后报告 Red 证据、定向测试、相关完整测试和仍未覆盖范围。

## 测试质量门禁

- 以 Behavior、Public API 和 Observable State 为主要观察面；不要为了覆盖每个实现方法而复制生产代码结构；
- 区分 Test Size、Test Scope 和 Fidelity：小测试负责快速反馈，较大测试负责验证组件交互和真实环境差异；不以固定比例或固定测试数量机械验收；
- 对快速、确定性、依赖简单的真实实现，优先使用真实实现；必须隔离时选择最小 Test Double，并说明它弥补的风险；
- Fake 必须通过公共 Contract Test 或等价测试保持与真实实现一致；避免让未经验证的 Fake 制造虚假信心；
- 优先测试结果和状态；只有行为本身就是状态变化、事件发送或外部副作用时，才检查必要的 Interaction；避免 Overspecification；
- 测试代码应完整、简洁、易读，不把复杂循环、条件逻辑和隐藏数据生成放入测试；允许测试使用少量 DAMP（Descriptive And Meaningful Phrases）重复换取清晰度；
- 失败信息应说明预期、实际结果和关键上下文；测试失败必须能支持快速定位；
- Flaky Test 不能被静默跳过；必须分类、记录 Owner、修复或显式隔离，并保留回收条件和未覆盖风险。
