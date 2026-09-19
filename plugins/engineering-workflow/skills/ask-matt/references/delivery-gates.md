# Candidate、PR 与合并后清理

本参考资料只适用于准备合入仓库的变更。它不把只读咨询、诊断报告或临时实验强行变成 PR；目标仓库自身的交付规则优先。

## Candidate 门禁

在本地形成 candidate 后，先检查：

- 当前 branch、HEAD、base 和初始工作区状态；
- 没有用户已有修改、未跟踪文件或额外未推送 Commit；
- Contract、相关验证、当前上下文 Review 和 `git diff --check` 已完成；
- Commit 范围只覆盖一个清晰的业务或工程目标；
- 是否涉及 API Contract、Authorization、State、Data Scope、数据库 / Schema、外部服务、模型链路、运行时、部署或安全等高风险边界；
- 仍缺少哪些 Software Test、Integration Test、AI Evaluation、Business Acceptance、Runtime 或 Security 证据。

Candidate 阶段不自动 Push 或创建 PR。

## 用户确认后的交付顺序

用户必须明确确认后，才能执行：

```text
最终确认 branch / HEAD / git_dirty=false
  → 按风险运行 targeted tests / Integration / AI Evaluation / Business Acceptance / Runtime / Security checks
  → 检查结果和未验证范围
  → Push
  → 创建或更新一个 PR
  → 说明 Auto-merge 行为和策略
  → 监控 PR 状态和 required checks
```

不要把本地测试通过表述为真实业务验收、Production Readiness 或托管 CI 已通过。

## 风险验证

- 文档、注释、纯测试、纯 CI 或不影响运行行为的整理：执行相关 targeted checks，不要求完整 Real E2E；
- Authorization、State、API Contract、Data Scope、数据库迁移、部署或安全变化：执行对应 module / integration / runtime / security checks，并完成适用的 Business Acceptance；
- 影响外部服务、模型、检索、生成、评估或其他不可控运行链路：按目标仓库规则执行额外的 Integration、AI Evaluation 或 Real E2E；
- 真实外部服务需要用户明确授权，并使用目标项目规定的本地配置；不暴露 Secret。

## Auto-merge 与清理

- Agent 不直接执行 Merge；遵循目标仓库的自动化和 branch protection（分支保护）；
- 创建或更新 PR 后，按目标仓库要求监控真实状态，至少读取 `state`、`mergedAt`、base/head、Auto-merge 状态、required checks 和失败原因；
- 只有 PR 明确为 `MERGED`，且当前 worktree 无用户修改、无未推送 Commit、无 Open / Stacked PR 或其他 worktree 依赖时，才可以清理本次唯一 Feature branch；
- 回到目标仓库默认分支，按项目规则同步合并结果，再清理本次 PR 对应的 branch / worktree；
- 保留项目规定的 backup 分支，不批量清理历史分支；
- 归属、合并状态或依赖不明确时暂停，不删除。
