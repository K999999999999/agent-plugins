---
name: improve-codebase-architecture
description: "用户要求评估代码库或子系统的架构问题时，只读扫描架构摩擦并提出 Deep Module 改进候选；不直接重构代码。"
---

# 改善代码库架构

扫描代码库，找出可以通过 Deep Module（深模块）改善的架构摩擦：让复杂度集中在 Module 内部，用更小的 Interface 隐藏实现，改善测试性和 AI 可导航性。

这是一个只读的架构探索 Skill。它提出候选，不直接重构代码；候选被用户选择并澄清后，再进入 `workflow-to-spec`、`workflow-to-tickets` 和 `workflow-implement`。

## 设计语言

所有候选使用 `codebase-design` 的统一词汇：

- Module（模块）；
- Interface（接口）；
- Implementation（实现）；
- Depth（深度）；
- Seam（接缝）；
- Adapter（适配器）；
- Leverage（杠杆）；
- Locality（局部性）。

领域名称使用当前项目的 `CONTEXT.md` / `CONTEXT-MAP.md` 词汇。不要把实现中的文件名、类名或临时命名当成领域概念，也不要为了表达方便随意引入同义词。

## Phase 1：探索

### 先确定范围

- 用户指定 Module、子系统或痛点时，只扫描该方向；
- 用户没有指定方向时，读取近期 `git log --oneline` 和相关 Diff，优先关注最近反复变化的区域；
- 热点不明显时，再扩大扫描范围；
- 不为了寻找架构问题而修改代码、测试、数据库或运行环境。

开始扫描前读取：

- `AGENTS.md` 或 `CLAUDE.md`；
- `CONTEXT.md` 或 `CONTEXT-MAP.md`；
- 相关 `docs/adr/`；
- 相关 Architecture、模块、代码和测试。

### 观察架构摩擦

不机械套用指标，结合代码阅读和调用关系寻找：

- 理解一个概念需要在许多浅 Module 之间来回跳转；
- Module 的 Interface 几乎和 Implementation 一样复杂；
- 为了测试抽出了纯函数，但真正的 Bug 隐藏在调用链中，Locality 没有改善；
- 紧耦合的 Module 泄漏了不该穿过 Seam 的细节；
- 代码缺少测试，或无法通过当前 Interface 测试关键行为；
- 一个逻辑变化导致许多调用方散落修改；
- 中间 Module 主要只是透传，没有提供足够的 Depth。

对疑似浅 Module 使用 Deletion Test：假设删除它，复杂度是在调用方重新出现，还是只是消失？只有复杂度会在多个调用方重新出现时，才是值得考虑的 Deepening 候选。

## Phase 2：形成候选

提出不超过 5 个最有价值的候选，按推荐强度排序。每个候选包含：

- **名称**：明确描述要加深的 Module；
- **涉及范围**：相关 Module 或代码区域；
- **当前摩擦**：为什么现状影响理解、测试或变化；
- **Deepening 方向**：哪些复杂度应该隐藏在一个 Interface 后；
- **收益**：对 Depth、Leverage、Locality 和测试的具体改善；
- **依赖类型**：In-process、Local-substitutable、Remote but owned 或 True external；
- **风险和前置条件**：可能影响的 Contract、ADR 或模块职责；
- **推荐强度**：`Strong`、`Worth exploring` 或 `Speculative`。

候选阶段不要设计最终 Interface，也不要给出可以直接执行的重构清单。先回答“哪里有真实架构摩擦，为什么值得深入”。

## Phase 3：展示候选

默认直接用中文 Markdown 展示候选，保持简洁。建议结构：

```md
# Architecture Improvement Candidates

## Candidate 1：{名称}

- 涉及范围：{Module 或区域}
- 当前摩擦：{问题}
- Deepening 方向：{要隐藏的复杂度}
- 预期收益：{Depth / Leverage / Locality / 测试}
- 依赖类型：{分类}
- 风险：{风险}
- 推荐强度：{Strong / Worth exploring / Speculative}

## Top Recommendation

{最值得先探索的候选和原因。}
```

只有在关系图、调用链或前后结构对比确实能显著提升理解时，才生成临时 HTML。HTML 规则见 [HTML-REPORT.md](HTML-REPORT.md)。默认不生成文件、不打开浏览器、不依赖 CDN。

展示候选后只问一个问题：

> 你想先深入哪个候选？

在用户选择前，不开始 Interface 设计，也不修改任何文件。

## Phase 4：深入选中的候选

用户选择后，按以下顺序澄清：

1. 用 `workflow-grill-with-docs` 的规则确认问题、场景、范围和约束；
2. 用 `codebase-design` 的词汇确定 Module、Interface、Seam、Adapter 和隐藏的 Implementation；
3. 按 [DEEPENING.md](../codebase-design/DEEPENING.md) 分类依赖和测试策略；
4. 需要比较不同 Interface 时使用 [DESIGN-IT-TWICE.md](../codebase-design/DESIGN-IT-TWICE.md)；
5. 新领域术语按 `domain-modeling` 规则确认并更新 `CONTEXT.md`；
6. 只有满足 ADR 的三个条件时才建议记录 ADR：难以逆转、没有背景会令人意外、存在真实权衡。

一次只问一个关键问题。不要在候选选择后直接实现，也不要把候选报告当成已批准的架构决定。

## 交接

当选中候选的目标、范围、Interface、测试 Seam、Contract 和验收方向已经明确时，建议进入 `workflow-to-spec`。不要自动调用下一阶段。

后续流程：

```text
架构候选
    ↓
workflow-grill-with-docs
    ↓
domain-modeling / codebase-design
    ↓
workflow-to-spec
    ↓
workflow-to-tickets
    ↓
workflow-implement
```

本 Skill 不会：

- 自动实施架构重构；
- 创建 Issue、PR 或外部任务；
- 修改远程仓库；
- 重新讨论项目已经确认且没有现实摩擦的 ADR；
- 为了测试方便删除旧测试；
- 为假设中的未来需求新增抽象。

默认使用中文。Skill 名称、命令名、API、类名、函数名、文件路径、代码和必要的原始术语保持原样。
