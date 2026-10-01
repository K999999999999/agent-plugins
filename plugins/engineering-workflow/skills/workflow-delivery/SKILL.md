---
name: workflow-delivery
description: "实现与 Review 已完成并形成 candidate，或需要恢复 / 跟进已有 PR 时，按目标仓库规则准备交付、检查 CI、跟进合并并完成获准的收尾；远端操作仍须有明确发布授权。"
---

# PR 交付与收尾

本 Skill 只处理准备合入仓库的变更。只读咨询、诊断报告和临时实验不进入 PR。开始前读取目标仓库的 Agent instructions、Git / PR workflow、PR template、CI / automation 和当前 Git / worktree / remote 状态。

当需要判断 Presubmit / Post-submit、测试稳定性、CI 失败处理、自动合并或运行时发布时，读取 [CI Feedback](references/ci-feedback.md)。

先按工作项 ID 读取目标仓库的长期记录和本机实时状态，再核对 branch、commit、worktree 与实际 PR。授权以目标仓库记录中的用户决定为准；历史聊天、Skill 调用方式和 PR 正文都不能单独推断发布授权。若同一工作项、目标仓库与已说明范围仍一致，已取得的发布授权持续覆盖该范围内的 Push、创建 / 更新 PR、CI 修复、状态跟进、合并后复盘和安全清理；目标、范围或关键决定变化时暂停并取得新确认。

## Candidate 阶段

先只读检查：branch、HEAD、base、`git_dirty=false`、无用户已有修改、无未跟踪文件、无额外未推送 Commit；确认 Contract、相关验证、当前上下文 Review、`git diff --check` 和风险分类已完成。一个 PR 只承载一个清晰目标，不按 Commit 数量机械拆分。Feature branch 是短期交付隔离，不是长期 Dev branch；若变更不能保持小而聚焦，应说明拆分、迁移或大范围变更策略。此阶段不 Push、不创建 PR。

在聊天中向用户报告：目标仓库与 PR 目标、Commit 范围、涉及的高风险边界、验证证据及缺失项、剩余风险，以及目标仓库真实的自动合并行为。取得明确发布授权后，将工作项、仓库、授权范围和时间记入项目规定的状态记录；PR 正文只作事实留存，不代替聊天授权。

## 明确确认后的顺序

只有当前工作项已有覆盖本次目标仓库和范围的明确发布授权后，才执行：

```text
最终确认 branch / HEAD / 最终 base / git_dirty=false
  → 核对现有验证是否对应当前 HEAD、最终 base 和范围；按影响复用或重跑 Presubmit 及适用的 Integration / AI Evaluation / Business Acceptance / Runtime / Security checks
  → 区分 Presubmit、Post-submit、Scheduled 和手工验证，不把慢速或低确定性检查机械塞进每个快速门禁
  → 检查结果是否可访问、可理解、可行动，以及 Flaky Test、失败归因和未验证范围
  → Push
  → 创建或更新一个 PR
  → 立即读取并记录真实 PR 状态，在聊天交接链接、自动合并状态、CI 进度和下一检查条件
  → 按项目规则持续监控，直到合并或出现需要用户决定的阻塞
  → 合并后复盘、验证清理条件并在聊天报告完整结果
```

Agent 不直接执行 Merge。若 CI 失败、PR 未合并、分支依赖不明确或发现用户修改，保留 branch，报告阻塞，不清理。

## 依赖 PR / Stacked PR

任何依赖前置 PR 的变更在依赖满足前都保持 Draft。记录每个 parent PR、当前 base 与最终 base；在 parent 全部合并后，将子 PR 对齐到最终 base，读取实时 PR 的 Draft、head SHA、base 和状态，并确认适用的 CI / required checks 对应当前 head 与最终 base。切换 base 或 head 后重新判断受影响验证，不能把旧 base 上的 CI 结果当作当前证据。只有依赖已解决、最新状态匹配且目标仓库检查满足后，才能转为 Ready 并进入自动合并流程；如果事实无法核实，继续保持 Draft。

对于独立 PR，按目标仓库实际 Required Checks、Branch Protection 和 Auto-merge 规则推进；不得擅自增加用户 PR Review 门禁。合并自动化只在其真实条件满足时启用。

## 本机恢复记录与 Plugin 同步

若目标包含跨仓库工作，先识别唯一主记录与各仓库关联记录；关联记录指向主记录，不复制或扩大授权。清理 branch / worktree 时保留工作项要求的共享实时状态和长期记录引用。换机器或本机状态缺失时，依据长期记录及可核实的仓库 / PR 事实恢复；不确定的授权保持未知。

若目标包含本机 Plugin / Skill 同步，先核实实际 marketplace 注册项、源 checkout、仓库身份和支持的更新方式。源 checkout、marketplace 工作副本和安装缓存是不同位置；确认实际关系后才把源作为权威，不手工编辑安装缓存。清理 feature worktree 前确认它不是仍被 marketplace 使用的源目录；同步后逐项比较源与安装结果，并按支持的方式验证新会话加载。

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

只有 PR 明确为 `MERGED`，且没有用户修改、未推送 Commit、Open / Stacked PR 或其他 worktree 依赖时，才执行目标仓库规定的收尾：同步默认分支、删除本次 PR 对应的唯一 Feature branch / worktree、按项目策略清理远端 branch，并再次验证 branch、HEAD、tracking、Git status、worktree 和远端状态。将合并结果、Review / CI 证据、清理结果和仍未解决的问题记录到正式工作项及本机状态，并在聊天完整报告。

保留项目规定的 backup 分支，不批量清理历史分支；归属、合并状态或依赖不明确时暂停，不删除。
