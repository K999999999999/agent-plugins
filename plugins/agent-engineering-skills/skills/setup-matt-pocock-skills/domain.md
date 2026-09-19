# Domain 文档

说明工程 Skills 在探索本仓库代码时，如何读取和使用领域文档。

## 探索前先读取

- 根目录的 **`CONTEXT.md`**，或者
- 如果根目录存在 **`CONTEXT-MAP.md`**，读取它指向的、与当前主题相关的各个 Context 的 `CONTEXT.md`。
- **`docs/adr/`**：读取与当前工作范围相关的 ADR。对于 multi-context 仓库，还要检查 `src/<context>/docs/adr/` 下的 Context 专属决策。

如果这些文件或目录不存在，**静默继续**。不要把它们缺失当成问题，也不要在没有实际领域决策时建议提前创建。只有在术语或决策真正被解决时，`/domain-modeling` 才会按需创建它们；该 Skill 可以由 `/grill-with-docs` 触发。

## 文件结构

Single-context 仓库（大多数仓库）：

```
/
├── CONTEXT.md
├── docs/adr/
│   ├── 0001-event-sourced-orders.md
│   └── 0002-postgres-for-write-model.md
└── src/
```

Multi-context 仓库（根目录存在 `CONTEXT-MAP.md`）：

```
/
├── CONTEXT-MAP.md
├── docs/adr/                          ← 系统级决策
└── src/
    ├── ordering/
    │   ├── CONTEXT.md
    │   └── docs/adr/                  ← Context 专属决策
    └── billing/
        ├── CONTEXT.md
        └── docs/adr/                  ← Context 专属决策
```

## 使用 Glossary 中的词汇

当输出中出现领域概念时，例如 Spec 标题、Ticket 标题、重构提案、假设或测试名称，使用 `CONTEXT.md` 中定义的术语。不要改用 Glossary 明确避免的同义词。

如果需要的概念还没有出现在 Glossary 中，这说明两种可能：你正在创造项目并未使用的语言，应重新考虑；或者 Glossary 确实存在缺口，应记录给 `/domain-modeling`。

## 标记 ADR 冲突

如果输出与已有 ADR 冲突，必须明确指出，不要静默覆盖：

> _与 ADR-0007（event-sourced orders）冲突，但由于……值得重新打开讨论。_
