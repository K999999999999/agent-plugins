---
name: workflow-design-review
description: "在编码前只读审查已确认的 Spec 或实现设计，重点验证 Use Case、变化边界、依赖方向、复杂度、Contract、可测试性和最小充分设计。"
---

# Design Review（设计审查）

这是进入 Ticket 或编码前的 Read-Only Review（只读审查）。目标是降低系统生命周期中的理解、修改、测试、部署和维护成本，而不是检查是否使用了某种架构模式。

本 Skill 不修改 Spec、代码、测试或配置，不自动修复，不启动独立 Agent，不替代实现后的 `workflow-code-review`。它只给出证据、影响、最小修复建议和 Verdict（审查结论）。

## 与其他阶段的边界

- `ask-matt` 负责判断是否需要本阶段；本 Skill 不重新做需求访谈。
- 只审查已确认且范围唯一的 Spec 或实现设计；目标不清、事实源缺失或用户尚未确认时输出 `BLOCKED`。
- 通过后进入 `workflow-to-tickets` 或已确认的下一阶段；`PASS` 不等于获得实现、Commit、Push 或 PR 授权。
- 如果实现过程中必须改变 Module Boundary、公共 Contract、Dependency Direction、重要架构抽象或已确认的 Design Review 决策，`workflow-implement` 必须返回本 Skill 重新审查。

## Architecture Knowledge Core 的按需读取

当设计涉及以下任一项时，读取本 Skill 的 [Architecture Knowledge Core](references/architecture-knowledge-core.md)：

- 新增或移动 Module、Layer、Adapter、Service、Port 或其他抽象；
- 修改依赖方向、稳定 Core / 可替换 Edge、循环依赖或外部技术边界；
- 修改公共 Contract、跨边界数据、状态 / 生命周期或安全不变量；
- 引入新的数据库、Framework、SDK、通信方式、部署形式或供应商；
- 存在多个合理设计方向，或担心过度拆分、透传层、未来设计和 Unknown Unknowns。
- 修改可能被下游依赖的 Observable Behavior、兼容性、Deprecated Contract 或迁移策略；
- 涉及跨模块、跨团队、批量生成、全局替换或运行时 Rollout / Rollback。

纯局部、稳定 Contract 内、没有架构边界变化的小修改，可以只执行下面的核心顺序；不要为了形式强制进行重型 Design Twice。

## 前置条件

确认目标 Spec 已由用户确认，范围唯一，相关 Agent instructions、Architecture、Domain、Contract、测试、仓库结构和必要的运行时事实可读取。未确认的草稿、无法定位的目标或互相冲突且未裁决的事实源输出 `BLOCKED`。

## 决策顺序

按以下顺序审查；先确认业务与变化，再审查结构和技术细节：

1. **Business / Use Case**：系统真正要保护的业务策略、Use Case、Domain Truth、授权、数据范围和安全不变量是什么？设计是在表达业务，还是首先表达 Framework / Database / SDK？
2. **Contract**：输入、输出、状态、不变量、失败语义、调用约束和验收条件是否清楚？哪些 Observable Behavior 可能已经被调用者、配置、日志、数据格式或下游系统依赖？是否把 ORM、Framework Request / Response 或外部 SDK 类型泄漏给不该知道的边界？
3. **Change Axes**：哪些内容因同一原因变化，哪些必须独立变化？UI、DB、外部服务、供应商、部署和业务规则是否被错误地绑在同一组件？
4. **Boundaries**：Module Boundary 是否围绕隐藏的知识、职责和变化原因，而不是单纯按目录、技术栈或执行时间顺序切割？
5. **Dependency Direction**：高层策略是否依赖低层实现？稳定 Core 是否依赖频繁变化的 Edge？是否存在循环依赖？需要反转依赖时，是否只有在真实边界存在时才引入 Contract / DIP？
6. **Repository / Runtime Reality**：真实 Package Layout、已有接口、测试 seam、配置、运行时兼容性和当前工程规则是否支持该设计？不能用假设中的目录或旧代码替代实际事实。
7. **Failure / State / Security**：依赖失败、超时、空结果、重试、生命周期、状态迁移、授权、SQL Safety 和 Fail Closed 行为是否显式且可预测？
8. **Complexity Signals**：是否出现 Change Amplification（简单变化需要改很多位置）、Cognitive Load（理解局部必须携带大量上下文）或 Unknown Unknowns（影响范围和必须检查的对象无法预测）？Unknown Unknowns 是最高优先级信号。
9. **Information Hiding / Module Depth**：每个 Module 隐藏了什么重要知识？接口是否简单而能力足够，还是只是 Shallow Module、透传方法、Wrapper 套 Wrapper 或空层？新增设计元素是否消除了比自身更多的复杂度？
10. **Cross-boundary Contract / Testability**：跨边界数据是否简单、稳定、独立？核心业务和 Use Case 能否不启动 Web Server、真实 Database、Framework 或第三方服务就被验证？每个关键行为是否对应 Software Test、Integration Test、AI Evaluation 或 Business Acceptance？
11. **Optionality / Simplicity**：是否过早绑定技术供应商？是否为猜测的未来新增 Interface、Repository、Service、Adapter、Plugin、Layer、配置或迁移？能否删除某层、某接口或某个包装而不损失真实边界？如果替换或删除旧 Contract，是否有 Discovery、Owner、Migration、Milestone 和防止 Backsliding 的计划？
12. **Alternative / Design Twice**：只有当决策会影响稳定边界、公共 Contract、依赖方向、供应商绑定或高成本未来变化时，才至少比较一个真正不同的方案，并比较复杂度、影响范围、接口、测试和当前成本。记录决策依据、Owner 和必要的 Revisit Trigger；小的局部决策不执行重型方案文档。

## 审查原则

- 先看复杂度和变化影响，再看模式、目录和类数量；不以行数、类数量、接口数量或是否“像 Clean Architecture”机械判定质量。
- 不因缺少 Interface、Repository、Service、微服务或设计模式就判定有问题；每个新增元素必须能说明隐藏了什么复杂性、隔离了什么真实变化、减少了谁的认知负担。
- 不把“现在能跑”当作充分标准，也不以战略设计为名提前实现所有未来可能性；目标是让重要变化局部化、影响范围可预测，并保持当前复杂度最小。
- 文档应记录抽象、Contract、Observable Behavior 和重要决策的原因、替代方案、Owner 与 Revisit Trigger，不能靠大量说明掩盖模糊职责、隐藏调用顺序或坏边界。
- 发现问题时只提出最小可行改进，不直接重构；若修复会改变已确认的业务、边界、Contract 或依赖方向，应返回 Spec / Design Review，而不是在本阶段擅自修改。

## Verdict

只允许：`PASS`、`PASS WITH MINOR FIXES`、`NEED FIX`、`BLOCKED`。`PASS` 仍不等于实现授权；`NEED FIX` 或 `BLOCKED` 必须返回 Spec / 设计阶段。

每个发现必须按以下结构给出，不能只有模式名称或抽象偏好：

```text
Signal: <发现了什么复杂度、边界、依赖、Contract 或可测试性信号>
Evidence: <代码、模块、依赖、Spec、配置或运行时事实>
Impact: <Change Amplification / Cognitive Load / Unknown Unknowns / Coupling / Testability / Maintainability 中的实际影响>
Recommendation: <最小可行改进；若需要重新设计，明确返回 Design Review>
```

```text
Review: PASS | PASS WITH MINOR FIXES | NEED FIX | BLOCKED
Review Target: <Spec 或设计路径>
Findings:
- <Signal / Evidence / Impact / Recommendation>
Reference: <是否读取 Architecture Knowledge Core，以及读取了哪些相关章节>
Evidence Sources: <实际读取的事实源和验证计划>
Next: <workflow-to-tickets 或返回 Spec / Design Review>
```
