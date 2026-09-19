# Ticket Readiness Review

Ticket Readiness Review 是正式 Ticket 写入和用户确认前的只读门禁。它由当前主 Agent 执行，不启动独立 Agent，也不替代 `design-review`、实现后的 `code-review` 或 PR Review。

## 输入

- 已确认并通过 `design-review` 的 Spec；
- `to-tickets` 生成的 Ticket 草案；
- 目标仓库的 Agent instructions、Issue / tracker 规则和相关 Domain / Architecture / Contract；
- 直接受影响的代码、测试和运行时事实。

## 检查项

逐条检查：

1. Scope 和 Out of Scope 是否明确；
2. Ticket 是否交付一个可观察的纵向行为，而不是单纯的一层技术任务；
3. `Blocked by` 是否只记录真正的直接启动依赖，是否存在循环依赖；
4. owned files 和受影响模块是否可判断；
5. 正常、边界和失败行为是否可以被观察；
6. Authorization、Data Scope、State、SQL Safety 等边界是否已有依据；
7. Software Test、Integration Test、AI Evaluation 或 Business Acceptance 证据是否分类正确；
8. Done When 是否可以由测试、报告或其他客观证据判断；
9. 是否存在尚未解决的 Architecture、Domain、公共 Contract、权限或状态决策。

## Verdict

只输出两个 Verdict：

- `READY`：可以交给用户确认 Ticket 拆分；
- `NEED FIX`：指出最小修复，不能写入正式 Ticket 或进入实现。

如果发现第 9 项未解决的问题，不在 Ticket 中猜测，返回 `to-spec` 或 `design-review`。

## 输出

```text
Ticket Readiness: READY | NEED FIX
Scope: <检查的 Feature、Spec 和 Ticket 草案>
Findings:
- <问题、依据、影响、最小修复>
Dependencies: <依赖图是否合理>
Evidence: <测试 / Evaluation / Acceptance 证据>
Next: <用户确认拆分，或返回 Spec / design-review>
```
