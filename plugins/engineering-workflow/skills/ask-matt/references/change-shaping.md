# Change Shaping（变更形状与生命周期）

这份 reference 只在 `ask-matt` 需要判断变更大小、生命周期、分支策略、迁移范围或发布风险时读取。它把“尽早反馈、保持小变更、降低影响范围”转成通用判断，不复制特定组织的工具和规模。

## 1. 按生命周期选择流程强度

| 变更画像 | 推荐路径 |
| --- | --- |
| 临时诊断、一次性实验、不会进入默认分支 | 读取必要事实，完成实验或报告；不进入 PR 交付 |
| 局部、稳定 Contract 内的小修改 | 可跳过不必要的 Spec / Ticket；保留相关测试、Diff Review、Candidate 和项目规定的交付门禁 |
| 预计长期维护的普通行为变化 | `workflow-to-spec` → `workflow-design-review` → `workflow-to-tickets` → `workflow-ticket-readiness` → `workflow-tdd` / `workflow-implement` → `workflow-code-review` → Candidate → `workflow-delivery` |
| 公共 Contract、依赖方向、状态、安全或运行时变化 | 提高 Design Review、测试、Integration、Business Acceptance、Runtime / Security 验证级别 |
| Deprecation、Migration、全局重命名、批量生成或跨团队变化 | 使用 Migration / Large-Scale Change 规划，拆成可独立验证和提交的切片 |

软件的预期维护寿命不同，工程实践的强度也可以不同。临时 Prototype 不需要完整 Production workflow；一旦 Prototype 进入长期维护，就必须重新评估并进入标准流程。

## 2. 小变更原则

- 一个变更尽量只承载一个清晰目标；
- 保持 Diff 小而可理解，但不设通用行数硬阈值；
- 让 Reviewer 能在合理时间内理解 What、Why、Risk 和 Verification；
- 先提交小的可验证增量，再继续下一个增量；
- 不把无关重构、清理、格式化和未来能力混入当前目标；
- 小变更也必须保留与风险匹配的测试和安全门禁。

小变更是 Review 和故障定位的优化目标，不是禁止偶尔进行大变更的绝对规则。确实无法拆分时，记录为什么不能拆、如何降低风险以及如何验证。

## 3. 分支与 Source of Truth

Feature branch 可以作为 PR 交付隔离，但不应成为长期 Dev branch 或批量集成线。除非目标仓库明确采用不同策略：

- 默认分支 / 主仓库是 Source of Truth；
- Feature branch 尽量短生命周期、单一目标、及时同步；
- 不用长期分支掩盖测试、CI 或 Contract 不稳定；
- 不为每个小 Ticket、每个 Commit 或每次测试机械创建 branch；
- Release branch 只有在目标仓库确实需要可追溯发布版本时才使用；
- 不自动删除仍有 Open PR、依赖或用户修改的 branch / worktree。

## 4. 大范围变化

触发条件包括批量 API 替换、全局符号迁移、自动生成修改、语言 / Framework 升级、删除旧系统、跨模块数据迁移和可能影响大量下游消费者的 Contract 变化。

这些任务应在 Ticket 阶段记录：影响范围、Owner、切片方式、每个切片的依赖、测试闭包、Review 责任、回滚或恢复方式，以及如何阻止新的旧用法继续进入。每个切片尽可能独立测试、Review、提交和失败定位。

## 5. 运行时发布

只有当项目确实存在运行时发布、用户流量或不可逆数据影响时，才要求在 Delivery 阶段增加：

- Feature Flag 或等价的隔离机制；
- Staged Rollout / Canary；
- 监控信号和停止条件；
- Rollback 或恢复路径；
- 发布后的验证和清理。

没有部署或运行时流量的库、文档和离线工具，不应为了形式引入这些机制。
