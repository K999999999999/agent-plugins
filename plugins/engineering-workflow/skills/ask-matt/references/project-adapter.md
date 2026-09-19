# 目标仓库适配层

本参考资料只提供通用读取顺序和适配原则，不定义任何特定项目的业务规则、目录结构、测试数量或运行服务。目标仓库自己的 `AGENTS.md`、`CLAUDE.md`、Architecture、Domain、Spec、Contract、CI 和 Git workflow 始终优先。

## 开始工作时读取

按目标仓库实际存在的文件读取：

- Agent instructions（例如 `AGENTS.md`、`CLAUDE.md` 或 `.github/copilot-instructions.md`）；
- Architecture、Domain、Engineering、ADR 和模块文档；
- Spec、Ticket、Issue tracker 或其他项目工作记录；
- 测试、CI、部署和运行时配置；
- 当前 branch、HEAD、worktree、remote 和 Git status。

不要因为本 Skill 提供了某个默认路径，就假设目标仓库必须使用该路径。先搜索并确认项目的实际事实源，再把路径和命令写入当前阶段报告。

## 项目差异的处理

- 目标仓库的工程规则覆盖本包的默认流程；
- 目标仓库没有规定时，选择最小、可追溯、可回滚的约定，并在报告中标记为建议而不是事实；
- 本包只负责流程门禁，不替目标项目定义业务语义、模块职责、质量阈值或发布政策；
- 任何真实外部服务、生产数据、模型 API、部署或破坏性 Git 操作，都必须同时满足目标仓库规则和用户授权。

## 验证分类

根据目标项目实际情况区分：

- code：格式、Lint、Type Check 或静态检查；
- logic：Unit Test、Functional Test、Deterministic Test 和回归测试；
- integration：模块、API、数据库、消息队列或其他外部依赖集成；
- runtime：启动、健康检查、Smoke Test、构建和可部署性；
- security：依赖、Secret、权限、数据范围和安全扫描；
- AI Evaluation：模型或 AI 链路的行为评测；
- Business Acceptance：业务目标和实际使用场景验收。

不要把其中一类证据表述成另一类已经通过；测试数量、服务状态、PR 状态和分支状态都必须在当前 checkout 重新读取。
