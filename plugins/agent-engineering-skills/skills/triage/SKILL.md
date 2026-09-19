---
name: triage
description: "在本地 Spec / Ticket 上进行分类、验证和状态整理，判断下一步应澄清、规划、实现还是暂缓。"
---

# Triage

对 `.scratch/` 下的本地 Spec、Ticket 或待处理工作进行轻量分类和验证。Triage 的结果是让工作项进入正确的下一阶段，而不是替用户直接实现需求。

本 Skill 只使用本地 Markdown，不查询或修改外部 Issue tracker，不处理外部 PR，不使用外部 Label，也不创建评论。

## 本地字段

每个被整理的工作项最多保持一个 Category 和一个 Triage 结论：

```text
Category: bug | enhancement
Triage: needs-triage | needs-info | ready | human-review | wontfix
Status: open | in-progress | done | blocked
```

字段含义：

- `bug`：现有行为与已确认 Contract 或用户预期不一致；
- `enhancement`：新增能力或已有能力的改进；
- `needs-triage`：尚未完成判断；
- `needs-info`：缺少复现、场景、约束或验收信息；
- `ready`：信息完整，可以进入 `to-spec`、`to-tickets` 或 `implement`；
- `human-review`：需要用户判断、外部访问或手工操作；
- `wontfix`：用户明确决定当前不处理；
- `Status` 记录实际工作状态，不替代 Triage 结论。

这些是本地 Markdown 字段，不是外部标签。

## Invocation

用户可以直接提供本地路径，或说明要查看哪些待处理工作，例如：

- “整理这个 Ticket”；
- “看看哪些工作还没有判断”；
- “这个需求应该进入 Spec 还是直接实现”；
- “把这个 Bug 的信息补完整”。

如果用户没有提供路径，扫描 `.scratch/` 下带有 `Triage: needs-triage` 的工作项，以及 `Triage: needs-info` 且有新 Comments 的工作项。没有本地工作项时明确报告，不创建空任务。

## 流程

### 1. 读取完整上下文

读取工作项的正文、Comments、Result、关联本地 Spec / Ticket，以及：

- `AGENTS.md` 或 `CLAUDE.md`；
- `docs/agents/issue-tracker.md`；
- `docs/agents/domain.md`；
- `CONTEXT.md`、`CONTEXT-MAP.md` 和相关 ADR；
- 相关代码和测试。

使用项目的领域术语和事实源优先级。不要只按用户原话的关键词判断。

### 2. 检查重复实现

按领域概念搜索当前代码库中是否已经存在请求的行为，而不是只搜索工作项的原句。记录搜索范围和结论：

- 已经完整实现：向用户说明代码和测试证据，追加或更新 `Result`，并将 `Status` 更新为 `done`；不要使用 `wontfix`；
- 只有部分实现：说明缺口，不能简单判定已完成；
- 尚未发现：继续验证范围和设计。

不要因为代码里出现相似名称，就断定行为等价。

### 3. 检查历史排除项

读取 `.scratch/out-of-scope/` 下相关记录。如果发现概念相似，向用户说明之前的决定和理由，询问当前请求是否仍然适用。不要自动删除或覆盖历史记录。

### 4. 提出分类建议

向用户报告：

- `Category` 建议及理由；
- `Triage` 建议及理由；
- 当前代码库中已发现的相关行为；
- 已知缺口、风险和最少需要补充的信息。

等待用户确认分类和下一步。不要在建议阶段修改工作项。

### 5. 验证用户描述

用户确认继续后，再按类型验证：

- **Bug**：使用用户步骤或最小 Fixture 复现准确症状；
- **Enhancement**：确认当前能力、受影响模块、领域边界和目标行为；
- **已有实现**：通过公共 Interface、代码和测试核实，不只看文件名；
- **信息不足**：列出具体、可回答的问题，避免只说“请提供更多信息”。

如果验证需要修改代码、创建测试或调用真实外部系统，停止并交给相应流程；Triage 不承担实现。

### 6. 需要时澄清

如果需求需要补充目标、场景、术语、Contract 或边界，使用 `grill-with-docs` 的一次一个问题流程，并按 `domain-modeling` 规则更新领域文档。不要调用不存在的 `grilling` 或 `Skill tool`。

澄清完成后，把已经解决的内容整理成 Agent Brief；仍未解决的内容保持在 `needs-info`。

### 7. 应用结果

用户确认最终结果后，才更新本地工作项：

- `ready`：补充 Agent Brief，说明下一步应进入哪个 Skill；
- `human-review`：说明需要用户完成的判断、访问或手工验证；
- `needs-info`：追加具体问题和当前已确认事实；
- `wontfix`：追加决定和持久理由，必要时写入 `.scratch/out-of-scope/`；
- `needs-triage`：保留未决状态，并写明下一次应从哪里继续。

更新后保持原有 Comments 和 Result，不覆盖用户已有内容。不要删除工作项；如果它已经实现或明确不处理，用字段记录状态。

## “待关注”清单

列出以下本地工作项，按文件时间或编号排序：

1. `Triage: needs-triage`：从未完成判断；
2. `Triage: needs-info`：有新的用户补充，需要重新判断；
3. `Status: blocked`：当前工作被明确前置条件阻塞。

每项只显示文件名、Category、Triage、Status 和一句摘要，让用户选择要深入哪一项。

## 会话边界

本 Skill 可以读取、分析和更新本地工作项及本地 Out-of-Scope 记录。

本 Skill 不会：

- 创建或查询 GitHub / GitLab Issue；
- 处理 PR 或外部评论；
- 添加外部 Label；
- 自动关闭或删除工作项；
- 自动实现代码或创建测试；
- 跳过用户确认直接改变分类；
- 把 `ready` 直接当成实现授权。

默认使用中文。Skill 名称、命令名、API、类名、函数名、文件路径、代码和必要的原始术语保持原样。
