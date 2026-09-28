# Engineering Workflow

这是一个用户级、通用的 Codex 工程工作流插件，不属于任何单一应用仓库。

入口是 `$ask-matt`；它只判断阶段、推荐下一步，然后停止等待用户决定。阶段 Skill 使用 `workflow-*` 前缀，避免与目标环境已有的同名 Skill 冲突。执行时始终以目标仓库的 Agent instructions、Architecture、Domain、Spec、Ticket、CI 和 Git 规则为准。

`setup-engineering-workflow` 是每个仓库手动执行一次的初始化 Skill；Plugin 安装或正常工作流不会自动触发它。`wayfinder` 也需手动调用，用于大型、跨模块、跨多个 session 且决策路线不清的工程规划。普通需求澄清由 `workflow-grill-with-docs` 负责。

## 安装

把包含本插件的 marketplace 注册到 Codex 后安装 `engineering-workflow`。如果本机已有同名入口 Skill，先确认替换关系，不要让两套 `ask-matt` 同时生效。

## 设计边界

- 插件本体放在用户级或独立 workflow 仓库，不提交到业务项目；
- 业务项目只保留自己的 `AGENTS.md`、项目文档和实现规则；
- Spec / Ticket 的实际存储媒介由目标仓库决定；
- PR、Auto-merge、部署和真实外部服务操作仍受目标仓库规则与用户授权约束；
- 本插件不自动调用独立 Agent，也不使用双独立审查。
