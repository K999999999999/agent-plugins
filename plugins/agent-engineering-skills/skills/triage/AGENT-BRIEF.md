# Agent Brief（代理执行说明）

Agent Brief 是写在本地 Ticket 中、供后续实现 Agent 使用的稳定执行说明。它是 Ticket 的 Contract，不是外部评论，也不依赖某个平台的 Issue 或 PR。

## 编写原则

### 持久性优先

Ticket 可能在一段时间后才实现，代码库也可能发生变化。因此：

- 描述 Interface、类型和行为 Contract；
- 指出 Agent 应该查找或修改的稳定概念；
- 不依赖容易过时的文件路径和行号；
- 不把当前实现结构当成永久结构。

### 描述行为，而不是操作步骤

说明系统应该做什么，不规定 Agent 必须使用哪种内部写法：

- 好：`SkillConfig` 的 `schedule` 接受可选的 `CronExpression`，缺省时保持当前行为；
- 不好：打开某个文件，在指定行添加一个分支。

### 验收条件必须完整

每条验收条件都应可以独立验证：

- 好：输入缺少必要字段时返回明确的 Contract 错误，且已有成功路径不变；
- 不好：功能应该正常工作。

### 明确范围

写出不需要修改的相邻能力，防止实现过程中扩张。

## 模板

```md
## Agent Brief

**Category:** bug / enhancement
**Summary:** 一句话描述要完成的行为

**Current behavior:**
描述当前状态。Bug 写出实际错误；Enhancement 写出当前基础。

**Desired behavior:**
描述完成后的行为，包括边界和错误条件。

**Key interfaces:**
- `TypeName`：需要变化的行为和原因
- `functionName()` 返回值：当前行为与期望行为
- Config shape：需要的配置形状

**Acceptance criteria:**
- [ ] 可独立验证的条件 1
- [ ] 可独立验证的条件 2
- [ ] 可独立验证的条件 3

**Out of scope:**
- 本 Ticket 不应修改的内容
- 看起来相关但应单独处理的相邻能力
```

## 写入位置

Agent Brief 追加到对应的 `.scratch/<feature>/issues/<NN>-<slug>.md`，或作为该 Ticket 的 `## Agent Brief` 区块。不要创建外部评论，不要把本地路径写成外部链接。

## 质量检查

- 是否说明了 Current behavior 和 Desired behavior；
- 是否使用项目确认的 Domain 和 Architecture 术语；
- 是否包含稳定的 Interface / Contract；
- 是否有具体可测试的 Acceptance criteria；
- 是否明确 Out of scope；
- 是否避免了过时的文件路径、行号和实现指令；
- 是否把未确认假设误写成决定。
