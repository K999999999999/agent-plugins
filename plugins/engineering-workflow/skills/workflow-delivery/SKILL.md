---
name: workflow-delivery
description: "实现和 Review 已完成并形成 candidate，用户要求交付时，按仓库规则检查候选、处理 CI 与 PR，并在获准后跟进合并和清理；不用于编写功能。"
---

# PR 交付与收尾

本 Skill 只处理准备合入仓库的变更。只读咨询、诊断报告和临时实验不进入 PR。开始前读取目标仓库的 Agent instructions、Git / PR workflow、PR template、CI / automation 和当前 Git / worktree / remote 状态。

当需要判断 Presubmit / Post-submit、测试稳定性、CI 失败处理、自动合并或运行时发布时，读取 [CI Feedback](references/ci-feedback.md)。

## Candidate 阶段

先只读检查：branch、HEAD、base、`git_dirty=false`、无用户已有修改、无未跟踪文件、无额外未推送 Commit；确认 Contract、相关验证、当前上下文 Review、`git diff --check` 和风险分类已完成。一个 PR 只承载一个清晰目标，不按 Commit 数量机械拆分。Feature branch 是短期交付隔离，不是长期 Dev branch；若变更不能保持小而聚焦，应说明拆分、迁移或大范围变更策略。此阶段不 Push、不创建 PR。

向用户报告：PR 目标、Commit 范围、涉及的高风险边界、必须执行的最终验证、缺失证据和剩余风险。

## 明确确认后的顺序

只有用户明确确认后，才执行：

```text
最终确认 branch / HEAD / git_dirty=false
  → 按风险运行快速可靠的 Presubmit checks，以及适用的 Integration / AI Evaluation / Business Acceptance / Runtime / Security checks
  → 区分 Presubmit、Post-submit、Scheduled 和手工验证，不把慢速或低确定性检查机械塞进每个快速门禁
  → 检查结果是否可访问、可理解、可行动，以及 Flaky Test、失败归因和未验证范围
  → Push
  → 创建或更新一个 PR
  → 说明目标仓库的 Auto-merge 策略
  → 按项目规则监控真实 PR 状态
```

Agent 不直接执行 Merge。若 CI 失败、PR 未合并、分支依赖不明确或发现用户修改，保留 branch，报告阻塞，不清理。

## 风险验证

- 文档、注释、纯测试、纯 CI 或不影响运行行为的整理：执行相关 targeted checks；
- Authorization、State、API Contract、Data Scope、数据库迁移、部署或安全变化：执行对应 module / integration / runtime / security checks，并完成适用的 Business Acceptance；
- 影响外部服务、模型、检索、生成、评估或其他不可控运行链路：按目标仓库规则执行额外的 Integration、AI Evaluation 或 Real E2E；
- 依赖、Lockfile、Framework 或构建工具变化：检查版本来源、兼容性、Transitive Dependency、供应链安全和可复现构建；
- Deprecation、Migration、批量生成或大范围修改：检查切片、Owner、独立验证、回滚 / 恢复和防止新旧用法继续混用；
- 运行时发布变化：只有在目标项目确实有用户流量或部署风险时，补充 Feature Flag、Staged Rollout、监控信号、停止条件和 Rollback；
- 不把本地通过表述为托管 CI、业务准确率或 Production Readiness 已证明。

## CI 反馈与失败处理

- Presubmit 应优先包含快速、可靠、确定性高且能阻塞合入的检查；慢速、资源密集或稳定性不足的验证放入目标仓库定义的 Post-submit、Scheduled 或手工阶段；
- 每个阻塞检查必须能提供可定位的失败日志、失败历史、受影响范围和下一步修复动作；
- Flaky Test 不得静默忽略。必须分类、记录 Owner、修复或显式隔离，并说明临时替代验证、影响和回收条件；
- 失败的 required check、无法解释的测试重跑或 CI 红线未恢复时，不得声称 candidate 可安全合入；必要时保留或恢复 Known-good 版本，按目标仓库规则 Rollback；
- Auto-merge 只能建立在目标仓库的 Required Checks、Branch Protection 和自动化策略真实满足的基础上。Agent 不直接 Merge，也不把 Auto-merge 当作跳过验证的理由。

## 合并后清理

只有 PR 明确为 `MERGED`，且没有用户修改、未推送 Commit、Open / Stacked PR 或其他 worktree 依赖时，才执行目标仓库规定的收尾：同步默认分支、删除本次 PR 对应的唯一 Feature branch / worktree、按项目策略清理远端 branch，并再次验证 branch、HEAD、tracking、Git status、worktree 和远端状态。

保留项目规定的 backup 分支，不批量清理历史分支；归属、合并状态或依赖不明确时暂停，不删除。
