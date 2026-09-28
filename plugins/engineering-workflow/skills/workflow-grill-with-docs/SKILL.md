---
name: workflow-grill-with-docs
description: "工程需求的目标、用户场景、术语或范围仍需向用户确认时，逐次询问一个关键问题并形成已确认边界；不实现，也不代写 Spec。"
---

# 需求澄清

只处理需求澄清，不实现代码、不创建正式 Ticket、不提交 Commit、不创建 PR。开始前读取当前仓库的 Agent instructions、项目上下文、Architecture、Domain、Spec、测试和代码（按实际存在的文件选择）。

## 访谈规则

- 每轮只问一个最能减少不确定性的关键问题；
- 优先顺序：目标 → 用户和场景 → 术语和业务规则 → Scope → Architecture / Module → Contract → 验收和测试；
- 用户描述与仓库事实冲突时，先检查实际代码和文档，再明确报告冲突；
- 区分已确认事实、用户意图、待确认假设和建议；
- 重要概念至少验证一个正常场景和一个边界或失败场景；
- 不为了形式提前创建 ADR、Spec、Ticket 或外部 Issue。

## 结束条件

以下内容明确后结束：问题、目标用户、核心场景、术语、In Scope、Out of Scope、受影响边界、稳定 Contract、验收条件和测试方向。

输出：

```text
已确认事实
已确认术语
已确认决策
范围与边界
仍待确认的问题
建议下一步: workflow-to-spec / 继续澄清
```
