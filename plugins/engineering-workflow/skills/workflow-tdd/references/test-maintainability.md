# Test Maintainability（测试可维护性与 Fidelity）

这份 reference 在测试设计复杂、需要 Test Double、需要较大测试或出现 Flaky Test 时读取。目标不是追求测试数量，而是让测试在系统演进中持续提供可信、快速、可诊断的反馈。

## 1. 三个测试维度

- **Size**：运行测试需要的时间、进程、内存、网络和其他资源；
- **Scope**：测试验证的代码和组件范围；
- **Fidelity**：测试环境、数据和依赖是否反映真实行为。

Narrow Scope 不一定代表执行资源少，Large Scope 也不一定代表测试设计差。选择测试类型时，先看目标风险和缺失的证据，再决定使用 Small、Medium 或 Large Test。

## 2. 维护性规则

- 通过用户会使用的 Public API 验证行为；
- 测试 Behavior，而不是机械地为每个 Method 建立一个测试；
- 优先观察返回值、持久化状态和其他 Observable State，而不是无关的调用序列；
- 测试应在不改变需求的实现重构后保持稳定；
- 测试主体应包含理解该行为所需的信息，不把关键前置条件隐藏在过度共享的 Setup 中；
- 不在测试中加入需要另一个测试来证明的复杂逻辑；
- 测试名称和失败信息要说明行为、Expected、Actual 和关键输入；
- 生产代码通常优先 DRY，测试代码可选择 DAMP，以降低阅读和诊断成本。

## 3. Test Double 决策

优先使用快速、确定性、依赖简单的真实实现，例如 Value Object、纯计算和内存集合。使用 Double 前回答：

1. 真实实现为什么不可用？是速度、非确定性、外部副作用、成本还是隔离边界？
2. 这个 Double 验证了什么真实 Contract？
3. 是否需要额外 Integration / Contract Test 证明真实实现和 Double 的一致性？

Fake 通常比大量 Stubbing 更能保留真实行为，但 Fake 也需要维护和验证。Stubbing 过多会让测试只验证作者当前写出的协作方式；只有真实需要验证的错误、状态变化或外部副作用才使用 Interaction Testing。

避免：

- 为每个依赖机械创建 Mock；
- 验证不属于本测试目标的参数和调用顺序；
- 用测试专用生产分支掩盖无法建立真实 seam 的问题；
- 让不可信的 Fake 替代真实 Integration 证据。

## 4. Larger Test 与 CI

较大测试用于覆盖 Unit Test 无法发现的交互、配置、负载、部署和 Emergent Behavior。尽量构造最小的 System Under Test：

```text
取得 SUT → 准备测试数据 → 执行行为 → 验证结果
```

Presubmit 适合快速、可靠、确定性高的测试；慢速、低确定性或高资源测试可以进入 Post-submit、Scheduled 或明确授权的验证阶段。较大测试应有 Owner，失败日志要可访问、可复现、可诊断。

## 5. Flaky Test

Flaky Test 会持续消耗团队对 CI 的信任。处理时应：

- 区分产品回归、测试缺陷、环境问题和真正的非确定性；
- 记录失败历史和 Owner；
- 优先缩小 SUT、消除共享环境、随机性、时间竞态和不必要 Sleep；
- 临时隔离必须写明原因、影响、替代验证和回收条件；
- 不能把“重跑通过”当作修复，也不能静默禁用失败测试。

不要把书中的测试比例、组织规模或工具名称当作本项目的硬规则；根据当前风险、成本和真实测试能力调整。
