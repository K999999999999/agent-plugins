---
name: workflow-implement
description: "根据已确认的 Spec、Ticket 或明确的小范围任务，在 Contract 内完成可靠、可测试、职责清晰且最小充分的实现、Review 和本地 Commit。"
---

# 实现任务

前置条件是已确认的 Spec / Ticket，或用户明确给出的稳定小范围任务。开始前读取目标仓库的 Agent instructions、Spec、Ticket、相关项目文档、Contract、代码和测试，并记录 branch、BASE_SHA、初始 Git 状态和 owned files。无法区分用户已有修改时停止。

## 范围与实现

- 只覆盖确认的 Goal、Scope、Contract 和 Done When；
- 保持 Domain、Application、Port / Contract、Infrastructure 的依赖边界；
- 行为变化使用 `workflow-tdd` 的 Red-Green-Refactor；
- 纯文档、配置或机械变化按风险执行最小确定性验证；
- 发现稳定公共 Contract、模块一级职责、权限不变量或架构方向需要变化时返回设计阶段；
- 实现阶段按已确认设计施工，不在实现过程中重新设计架构。

## Clean Code Core

### 1. Correct & Verifiable

代码首先必须正确，并且能通过自动化测试证明。不可测试的核心逻辑是设计警告；先寻找真实的公共测试 seam，不用测试专用生产分支掩盖设计问题。

### 2. Clear Intent

名称、控制流、结构和 API 应准确表达真实意图。优先让代码表达意图，不依靠注释解释本可以由命名、结构或 Contract 表达的内容。避免为了减少行数使用隐式、嵌套或聪明的压缩写法。

### 3. Focused Responsibility

函数、类和模块应围绕清晰职责。重点判断它有多少个独立的修改原因，而不是机械判断代码长度、方法数量或文件行数。相关行为保持高内聚，职责放在自然拥有它的位置。

### 4. Explicit Behavior

副作用、状态变化、失败行为和调用顺序必须清楚。避免隐藏副作用、含糊 API、隐式时序约束，以及通过 `Selector` 驱动多个不相关行为。

### 5. Controlled Dependencies

保持低耦合。核心逻辑避免绑定具体基础设施实现；需要隔离时依赖稳定 Contract，并从外部注入具体依赖。构造与使用分离，第三方实现细节停留在系统边界。

### 6. Information Hiding

模块只暴露调用者真正需要知道的内容。避免泄漏内部状态、实现细节和第三方类型；接口应尽量小而清楚。

### 7. DRY

同一个业务知识、规则或算法尽量只有一个权威来源。不要因为代码表面相似就提前抽象；先确认它们是否具有相同的变化原因和稳定语义。

### 8. Simple Design

优先最少必要复杂度。不要为了 SOLID、设计模式、未来需求或“Clean 感”增加无价值的类、接口、层和抽象。

“最小充分实现”不是“最少行数实现”：在不降低 Contract 正确性、错误语义、测试性、安全性和可读性的前提下，使用最少的必要概念、状态、依赖和代码完成目标。

### 9. Safe Continuous Cleanup

发现代码味道时不要立即大改。先确认它是否真的增加阅读、修改、测试、耦合或错误成本；如果值得修改，在测试保护下采用最小改动并重新验证。不得把无关重构混入当前 Scope。

## Implementation Signals

实现和 Review 时重点警觉：

- 名称与真实意图不符；
- 一个函数、类或模块存在多个独立修改原因；
- 抽象层级混杂；
- 隐藏副作用；
- 参数或 `Selector` 暗示职责过多；
- 重复业务知识；
- 高耦合 / 低内聚；
- 核心逻辑直接绑定外部实现；
- 构造逻辑与业务逻辑混杂；
- 第三方细节向核心扩散；
- 正常流程被错误处理淹没；
- 隐藏调用顺序；
- 公开接口过大；
- 死代码 / 失效注释；
- 边界、异常和重要分支缺少测试；
- 为“整洁”制造过度抽象；
- 存在可以删除、复用或合并的无必要代码，但不能仅依据行数决定。

## SOLID Policy

SOLID 不是机械检查表。实现阶段重点使用：

- `SRP`：职责是否集中，是否存在多个独立修改原因；
- `DIP`：核心是否绑定具体实现，具体依赖是否在边界注入；
- `OCP`：新增已确认的正常变体是否反复修改同一核心结构。

只有在真实存在继承替换或接口拆分问题时，才使用 `LSP` / `ISP`。不要为了符合 SOLID 创建没有实际价值的抽象。

## Implementation Priority

按以下优先级判断实现质量：

1. Tests pass；
2. 没有不必要的业务知识重复；
3. Intent 清晰，正常、边界和失败行为可读；
4. 职责和依赖边界明确；
5. 在不牺牲前面条件的情况下，让类、函数、状态和抽象保持尽可能少。

代码行数只是需要进一步理解的信号，不是单独的验收指标。清晰的 20 行实现优于难以理解的 5 行实现；同等清晰和可靠时，选择更小的实现。

## Stop Rule

`workflow-implement` 负责按已确认设计施工，不负责重新设计架构。如果必须改变以下任一内容，停止实现并返回 `workflow-design-review`：

- 模块边界；
- 公共 Contract；
- 依赖方向；
- 重要架构抽象；
- 已确认的 design-review 决策。

## 完成门禁

运行与变更直接相关的 targeted tests，必要时运行相关完整确定性测试、`compileall`、`uv lock --check` 或项目已有静态检查。随后在当前上下文执行一次 `workflow-code-review`，检查 Acceptance Criteria、范围、测试证据、测试是否验证公共行为 / 状态且没有复杂测试逻辑或过度指定 Interaction、实际触及的安全 / Domain / Architecture 边界、依赖方向、职责集中度、最小充分实现和 Secret。不得调用独立 Agent 或重复无关全仓库审查。

确认以下内容后，才允许创建本地 Commit：

- Contract 和 Done When 已满足；
- 正常、边界和失败行为有适用的测试证据；
- Diff 没有无关变更、死代码、失效注释、无必要抽象或可避免的重复业务知识；
- 实现没有为了少写代码而牺牲可读性、错误处理、测试性或安全性；
- Review、最终 Diff 和 `git diff --check` 均通过。

Commit 使用项目规定的 `<type>(<scope>): <中文摘要>`，不在本 Skill 内 Push、创建 PR 或直接 Merge；形成 candidate 后交给 `workflow-delivery`。

```text
Mode: Main Agent
Status: PASS | BLOCKED
Tests: <定向和相关完整验证>
Review: PASS | NEED FIX
Clean Code: PASS | NEED FIX
Commit: <hash> <message> | None
Remaining: <剩余问题>
```
