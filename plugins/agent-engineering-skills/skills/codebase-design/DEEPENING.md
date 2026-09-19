# 加深模块

本文件说明如何根据依赖类型安全地把一组 Shallow Module（浅模块）加深。使用 [SKILL.md](SKILL.md) 中的 Module、Interface、Seam 和 Adapter 词汇。

## 依赖类型

评估候选 Module 时先分类依赖。依赖类型决定加深后的 Module 如何跨 Seam 测试。

### 1. In-process（进程内）

纯计算或内存状态，不涉及 I/O。通常可以直接合并相关模块，并通过新的 Interface 测试，不需要 Adapter。

### 2. Local-substitutable（本地可替代）

存在本地测试替代物的依赖，例如隔离的测试 Database 或内存文件系统。如果替代物已经存在，可以加深 Module，并在测试中运行该替代物。Seam 保持在内部，不必为了它扩展 Module 的外部 Interface。

### 3. Remote but owned（远程但自有）

由本团队拥有、但通过网络通信的服务或内部接口。可以在 Seam 定义 Port（端口接口）：Deep Module 拥有业务逻辑，传输方式作为 Adapter 注入。测试使用内存 Adapter，实际运行使用相应的网络或消息 Adapter。

推荐形态：在 Seam 定义 Port，为实际环境和测试环境分别提供 Adapter，让核心逻辑集中在一个 Deep Module 中。

### 4. True external（真正外部）

团队不控制的第三方服务或平台。Deep Module 接受注入的外部 Port，测试提供受控的 Mock Adapter；不要让第三方 SDK 渗透到领域和应用逻辑中。

## Seam 纪律

- **一个 Adapter 通常只是预想中的 Seam，两个合理 Adapter 才是现实的替换点。** 不要只因为未来可能替换就添加 Port；一个 Adapter 的 Seam 往往只是间接层。
- **区分内部 Seam 和外部 Seam。** Deep Module 可以有仅供自身测试使用的内部 Seam，也可以有供调用者使用的外部 Interface。不要因为测试需要就把内部 Seam 暴露出去。
- **不要用 Adapter 隐藏错误的职责边界。** 如果所有逻辑都在 Adapter 中，核心 Module 可能没有真正的深度。

## 测试策略：替换，而不是叠加

- 新的 Deep Module Interface 已经覆盖旧浅模块的同一外部行为时，可以把旧测试标记为候选清理项；只有在覆盖证据充分、范围已确认时，才单独删除或迁移旧测试。
- 新测试应位于 Deep Module 的 Interface；Interface 是测试面。
- 测试断言通过 Interface 观察到的结果，不断言内部状态。
- 测试应能承受内部重构；如果内部实现变化就必须改测试，说明测试可能越过了 Interface。
