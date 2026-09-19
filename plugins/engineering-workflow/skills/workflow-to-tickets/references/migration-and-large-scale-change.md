# Migration and Large-Scale Change（迁移与大范围变更）

这份 reference 只在任务涉及公共 Contract 替换、Deprecation、批量重命名、全局生成修改、语言 / Framework 升级、旧系统删除、跨模块数据迁移或大量下游消费者时读取。

## 1. 先确认是否真的需要大范围变化

记录：

- 为什么局部改动或兼容层不能满足目标；
- 影响哪些 Module、消费者、数据、配置、测试和运行时；
- 是否有 Observable Behavior 会被现有使用者依赖；
- 是否存在不可逆操作、窗口期或恢复限制；
- 主要 Owner、Domain / Contract Reviewer 和升级路径。

不要仅因为“全局替换更整齐”就启动 Large-Scale Change。先比较局部演进、兼容层、分批迁移和一次性变更的成本与风险。

## 2. 推荐生命周期

```text
Discovery
  → 记录现有消费者、旧用法、隐藏依赖和测试闭包
Owner / Decision
  → 确认责任、目标 Contract、兼容策略和停止条件
Expand
  → 先提供新 Contract 或兼容能力，不破坏现有消费者
Migrate
  → 按 Module / Owner / 风险切片，逐批修改、测试、Review、提交
Contract
  → 删除旧用法、旧实现或兼容层，确认没有新的旧用法进入
Cleanup
  → 更新文档、依赖、配置、测试和记录，关闭迁移遗留项
```

每个切片应尽可能独立验证、Review、提交和定位失败。批量自动生成不等于无需 Review；生成结果仍需符合项目约定，并对异常和冲突保留人工检查路径。

## 3. Deprecation 门禁

- 公开 Deprecated Contract 应说明替代物、迁移方式、Owner、时间 / Milestone 和支持边界；
- 通过代码搜索、运行时采样、日志或测试发现消费者，不能只依赖旧文档；
- 迁移完成前持续监控剩余消费者和 Backsliding；
- 新代码不得继续引入已 Deprecated 用法；可以使用 Linter、Static Analysis、Visibility 或 Review 门禁阻止；
- 删除旧 Contract 前确认测试、数据、配置、文档、下游和 Rollback 限制；
- 迁移的 Done When 是可观察的，例如剩余消费者为零、旧依赖不再出现或达到明确批准的豁免清单。

## 4. Failure / Rollback

大范围变更的失败处理至少说明：

- 哪些切片可以单独回滚；
- 哪些数据或 Schema 变化不可逆；
- 如何恢复 Known-good 状态；
- 失败时暂停后续切片的条件；
- 如何处理已迁移和未迁移消费者同时存在的兼容窗口。

没有明确恢复方式时，不应把大范围变更标记为 Ready。
