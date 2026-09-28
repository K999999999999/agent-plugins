---
name: codebase-design
description: "需要设计或重构单个模块的 Interface、Seam 或测试边界时，用深模块方法判断模块深度及是否需要 Adapter；不用于全仓架构扫描或 Spec 审查。"
---

# Codebase Design

使用 Deep Module（深模块）思维设计或重构代码：用小而清晰的 Interface（接口）隐藏足够多的行为，把复杂度放在合适的模块内部，并让调用者和测试都通过同一个 Seam（接缝）观察它。

目标是：

- 为调用者提供 Leverage（杠杆）：学习少量接口即可获得较多能力；
- 为维护者提供 Locality（局部性）：变化、知识、Bug 和验证尽量集中；
- 让测试通过公共 Interface，而不是依赖内部实现；
- 只在真实变化或替换需求存在时引入 Seam 和 Adapter。

这个 Skill 提供设计词汇和判断框架，不要求所有代码都套用复杂抽象。

## 统一词汇

以下术语在设计讨论中保持一致，不要随意用近义词替换：

**Module（模块）**：具有 Interface 和 Implementation（实现）的任何单元，可以是函数、类、包或跨层的一段完整能力。
_避免_：只用 Unit、Component 或 Service 指代所有模块。

**Interface（接口）**：调用者正确使用 Module 必须知道的全部信息，不仅是类型签名，还包括不变量、调用顺序、错误模式、必要配置和性能特征。
_避免_：只用 API 或 Signature 表示完整接口；它们通常只表达表面类型。

**Implementation（实现）**：Module 内部的代码和逻辑。

**Depth（深度）**：Interface 带来的能力杠杆。调用者需要学习的接口越小，而接口后隐藏的行为越多，Module 越深；Interface 几乎和内部实现一样复杂时，Module 越浅。

**Seam（接缝）**：可以在不直接编辑调用位置的情况下改变行为的地方，也是 Module Interface 所处的位置。Seam 放在哪里，是独立于内部实现的设计决定。
_避免_：用 Boundary 代替 Seam；在 DDD 语境中，Boundary 还可能指 Bounded Context，含义容易混淆。

**Adapter（适配器）**：在某个 Seam 处满足 Interface 的具体实现。它描述的是角色，不是内部内容。

**Leverage（杠杆）**：调用者从 Module 深度中得到的收益，即每学习一个接口单元可以获得多少能力。一个实现如果服务多个调用方和测试，就具有较高杠杆。

**Locality（局部性）**：维护者从 Module 深度中得到的收益，即变化、Bug、知识和验证是否集中在一个地方。一次修复能否在所有调用点生效，是局部性的直观表现。

## Deep Module 与 Shallow Module

**Deep Module（深模块）**：小 Interface，较多行为和复杂度隐藏在 Implementation 内部。

```text
┌─────────────────────┐
│   Small Interface   │  ← 方法少，参数简单
├─────────────────────┤
│                     │
│  Deep Implementation│  ← 复杂逻辑被隐藏
│                     │
└─────────────────────┘
```

**Shallow Module（浅模块）**：Interface 很大，但内部只做很少的工作，调用者承担了大部分复杂度。

```text
┌─────────────────────────────────┐
│       Large Interface            │  ← 方法多，参数复杂
├─────────────────────────────────┤
│  Thin Implementation             │  ← 主要只是透传
└─────────────────────────────────┘
```

设计 Interface 时先问：

- 能否减少入口数量；
- 能否简化参数；
- 能否把更多复杂度安全地隐藏在 Module 内部；
- 调用者是否只需要理解结果和约束，而不需要理解内部步骤。

## 设计原则

- **Depth 属于 Interface。** 深模块内部可以由多个小的、可 Mock、可替换的部分组成，只要它们不泄漏到公共 Interface。
- **Deletion Test（删除测试）。** 假设删除这个 Module：如果复杂度在所有调用方重新出现，Module 可能在创造价值；如果复杂度只是消失，Module 可能只是透传层。
- **Interface 是测试面。** 调用者和测试应当跨过同一个 Seam。如果必须越过 Interface 才能测试，说明 Module 的形状或测试边界可能有问题。
- **一个 Adapter 通常只是预想中的 Seam，两个真实 Adapter 才说明替换点存在。** 不要仅为了“以后可能替换”就增加 Port / Adapter；至少要有两个合理的实现需求（通常是生产实现和测试实现）。
- **先加深，再增加表面。** 优先让已有 Module 隐藏复杂度，不要把内部步骤逐个暴露给调用者。
- **不为假设的未来建设抽象。** 如果当前没有真实变化、替换或测试隔离需求，优先保持直接实现。

## 可测试的 Interface

1. **注入依赖，不在内部创建边界依赖。** 让外部资源通过参数或 Port 进入 Module，避免在业务逻辑内部硬编码具体外部依赖、凭证或运行环境。
2. **优先返回结果。** 能通过结果表达的行为，不要只产生隐藏副作用；必须有副作用时，明确它属于哪个 Interface Contract。
3. **保持表面小。** 方法少、参数少、状态约束清晰，通常意味着更少的测试设置和更高的 Leverage。
4. **让错误和不变量可见。** 调用者必须知道哪些输入被接受、哪些错误会发生、调用顺序是否重要，以及状态如何变化。

## 设计工作流程

### 1. 描述 Module 的职责

用一句话说明 Module 为调用者提供的能力，以及它应该隐藏的复杂度。若一句话无法表达，先检查职责是否混杂。

### 2. 找到现有 Seam

先阅读代码、测试和调用方，找出已经存在的公共 Interface。优先复用可以观察外部行为的 Seam，不要为了测试方便直接暴露内部结构。

### 3. 分类依赖

根据 [DEEPENING.md](DEEPENING.md) 判断依赖属于进程内、本地可替代、远程自有还是真正外部。依赖类别决定是否需要 Port、Adapter 和哪种测试。

### 4. 设计 Interface

明确：

- 入口和返回结果；
- 不变量和调用顺序；
- 错误与失败行为；
- 必要配置和权限约束；
- 哪些复杂度藏在 Implementation 内部；
- 哪些变化真的需要通过 Seam 替换。

### 5. 评估 Depth、Leverage 和 Locality

比较调用者需要学习的内容与 Module 隐藏的行为。如果 Interface 只是把每个内部步骤透传出去，继续加深 Module；如果 Module 只剩转发，考虑是否应移除这一层。

### 6. 固定测试面

测试通过 Interface 观察行为。不要因为测试使用了内部 Fake，就把内部 Seam 提升为公共 Interface。需要多个完全不同的 Interface 方案时，使用 [DESIGN-IT-TWICE.md](DESIGN-IT-TWICE.md)。

## 会话边界

本 Skill 可以：

- 设计或比较 Module、Interface、Seam 和 Adapter；
- 评估模块是否过浅、过深或只是透传；
- 为测试和替换找到最小有效接缝；
- 为后续 `workflow-to-spec`、`workflow-tdd` 和 `workflow-implement` 提供设计语言。

本 Skill 不会自动：

- 为未来假设新增抽象；
- 修改代码、测试或数据库；
- 删除旧测试或旧实现；
- 把设计建议当成已批准的架构决定。

默认使用中文。术语、类名、函数名、文件路径、代码和必要的原始表达保持原样。
