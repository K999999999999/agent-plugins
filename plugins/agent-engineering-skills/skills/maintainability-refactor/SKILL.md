---
name: maintainability-refactor
description: "已明确具体维护性问题且要求保持业务行为时，先诊断根因，再做最小范围、可验证的代码重构；不用于功能实现或全局架构改造。"
---

# 可维护性重构

在不改变业务行为的前提下处理已识别的可维护性问题。目标是让职责、模块边界、依赖、测试面和代码导航更清楚；“文件变多”本身不是成功标准。

## 适用范围与边界

- 用于已经明确问题和目标的小范围 Refactor（重构）。需求或业务行为变化使用 `workflow-implement` / `workflow-tdd`；架构方向、Module 一级职责或稳定公共 Contract（契约）仍不清楚时，交给 `codebase-design`、`improve-codebase-architecture` 或 `workflow-grill-with-docs`。
- 遵循 **Global awareness, local execution（全局感知，局部执行）**：先理解全局结构和依赖，再选择最小合理修改范围；不因调用本 Skill 就扫描并重构整个项目。
- 从最低层级开始判断：`Level 1` 函数/单文件，`Level 2` 单模块/单目录，`Level 3` 跨模块，`Level 4` 架构级。默认禁止直接做 `Level 4`；只有低层级无法消除根因时才提出扩大范围，并说明证据。触及稳定 Architecture（架构）、Domain（领域事实）、公共 Contract、权限或数据所有权时，先暂停并请求设计确认。
- 保留用户已有修改，不覆盖、不删除、不回退；遵循仓库 `AGENTS.md` 的交付、Commit 和安全边界。

## 阶段 A：Diagnose（诊断）

修改前先快速读取：仓库 `AGENTS.md`，相关 `CONTEXT.md` / `CONTEXT-MAP.md`（如果存在），相关 Architecture、Domain、Spec、Design、ADR、代码和测试。检查目录结构、当前分层和 Git 状态；用 `rg` 等方式确认目标文件的调用者、被调用者、依赖方向和相关测试。先运行或确认相关测试的基线状态。

在本阶段不修改业务代码。区分当前事实、根因、假设和建议，并检查：

- 职责是否混杂，模块边界是否真实存在，依赖方向是否稳定；
- 是否有真实重复（同一问题、同一变化原因、真实多次出现），而不是仅仅代码相似；
- 是否有过度抽象、透传层、目录横向膨胀或单文件膨胀；
- 重构是否会增加导航跳转、间接层、测试设置或耦合；
- 是否需要 characterization / regression test（特征/回归测试）保护现有行为。

先输出以下诊断，确定范围后才进入 Refactor（重构）：

```text
Scope:
Level:
Problem:
Root cause:
Refactor target:
Files affected:
Files intentionally untouched:
Test plan:
```

## 阶段 B：Refactor（重构）

- 小步修改，优先复用已有 Module、公共 Interface 和测试 Seam（接缝）；保持输入、输出、错误、不变量和业务结果不变。
- 按真实能力边界拆分，不按行数机械切分。普通源码约 `100–300` 行可作为观察信号；`>500` 行检查职责膨胀，`>800` 行列为重点候选，`>1000` 行原则上应分析重构，但配置、生成代码和大型测试可例外。目录出现十几个或更多同层文件时检查按能力/Feature/Module 分组，但不设绝对数量门槛。
- 重复观察从函数→文件→模块→跨模块→业务域→全局架构逐层扩大。抽象前确认：解决同一种问题、因同一种原因变化、真实重复、让调用方更简单且降低耦合；不确定时保留实现。可参考 Rule of Three（第三次真实重复再提炼）。
- 业务规则复杂处才使用 Domain、Value Object、Domain Service 或 Policy；纯技术能力保持直接。没有真实替换、测试隔离、依赖边界或业务职责时，不创建 `Base`、`Abstract`、`Factory`、`Manager`、`Repository`、`Service` 等空壳抽象。
- 每完成一个明确结构调整就运行最小相关测试；必要时补窄而有价值的保护性测试。完成后运行模块级测试，再按风险运行更大范围回归。确定性测试不得无意引入真实 LLM、外部 API、网络、生产数据库或不可控时间。
- 不把 Feature / Fix、无关格式化、额外清理或架构升级混入本次 Refactor。发现必须改变业务行为或稳定 Contract 才能解决根因时停止，转为单独工作项。

重构完成后由当前 Agent 做一次聚焦的轻量 Review（不调用独立 Agent）：检查范围、行为/Contract、依赖方向、测试证据、新增文件和抽象是否合理，以及修改影响面是否缩小。再重新判断：职责、导航、边界、测试性和 Locality（局部性）是否确实改善；如果只是搬移代码或增加文件而没有改善，则回退该结构调整或报告未达成。

## 完成输出

```text
Changed:
Why:
Tests:
Remaining issues:
Possible next-level refactor:
```

只把更高层的观察记录在 `Possible next-level refactor`，除非当前层级确实无法解决根因，否则不要自动扩大范围或立即实施下一层重构。
