# 领域文档约定发现

这是 `setup-engineering-workflow` 初始化时使用的只读检查清单，不规定仓库必须使用某一种领域文档结构。

## 探索顺序

- 先读取 Agent instructions、README 和工程文档中说明的事实源及优先级；
- 搜索根目录、`docs/`、各应用或领域模块中的 Domain、Context、Glossary、Architecture 和 ADR 文档；
- 对照实际代码和目录结构，确认文档归属单一应用、整个系统还是某个 bounded context；
- 检查现有文档格式、命名、状态和更新约定；
- 记录冲突、过期内容和无法确认的所有权，不擅自覆盖。

## 提出配置建议

- 现有结构可用时沿用它；
- 多个领域上下文按项目现有边界定位，不强制 single-context；
- 只有确有领域术语、边界或架构决策需要长期记录时，才建议新增文档；按需交给 `domain-modeling` 和 `workflow-grill-with-docs`；
- 不为了“完整”创建空的 Context、Glossary 或 ADR 文件；
- 如果必须引入新位置或格式，先说明准确路径、用途和维护方式，等待用户确认。
