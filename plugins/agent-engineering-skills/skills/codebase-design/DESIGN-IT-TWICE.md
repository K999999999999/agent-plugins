# Design It Twice（两次设计）

当一个候选 Module 的 Interface、Depth 或 Seam 影响较大时，不要只接受第一个想法。设计至少两种明显不同的 Interface，再根据 Leverage、Locality 和 Seam placement（接缝位置）进行比较。

使用 [SKILL.md](SKILL.md) 中的 Module、Interface、Seam、Adapter、Depth、Leverage 和 Locality 词汇。

## 1. 说明问题空间

在展开候选方案前，先向用户说明：

- 新 Interface 必须满足的约束；
- 它依赖的对象和依赖类别（见 [DEEPENING.md](DEEPENING.md)）；
- 一个简短的示意性代码或调用草图，用来说明问题，不把它当成已批准方案。

如果方案会改变模块一级职责、稳定公共 Contract 或架构方向，先等待用户确认问题边界；不要把示意草图直接当作实现指令。

## 2. 产生不同方案

至少设计 3 种差异明显的 Interface。支持独立 Reviewer / Subagent 时可以并行；不支持并行时，按独立视角依次设计，不让前一个方案限制后一个方案。

可以使用不同约束：

- **最小 Interface**：入口控制在 1–3 个，最大化每个入口的 Leverage；
- **最大灵活性**：支持多个已确认的使用场景和扩展点；
- **默认场景优先**：让最常见的调用保持最简单；
- **Ports & Adapters**：当依赖确实跨越 Seam 时，围绕 Port 和 Adapter 设计。

每个方案都说明：

1. Interface：类型、方法、参数、不变量、调用顺序和错误模式；
2. Usage：调用者如何使用它；
3. Hidden implementation：哪些复杂度被藏在 Seam 后面；
4. Dependency strategy：依赖如何注入、哪些 Adapter 存在；
5. Trade-offs：Leverage、Locality 和可变性的收益与代价。

方案必须围绕当前已确认的需求和领域语言，不为假设的未来能力扩展。

## 3. 展示和比较

先依次展示各方案，确保用户能单独理解每个方案，再用文字比较：

- 哪个 Interface 更小、更稳定；
- 哪个 Module 隐藏了更多复杂度；
- 哪个方案让变化集中在更少的位置；
- Seam 是否放在真正的变化点；
- Adapter 数量是否代表真实替换需求；
- 测试是否可以通过同一个 Interface 验证行为。

最后给出明确推荐并说明原因。如果不同方案的部分设计可以组合，说明组合后的 Interface 和新增复杂度。不要只列菜单而不做判断。
