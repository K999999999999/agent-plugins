# Engineering Workflow

这是一个用户级、通用的 Codex 工程工作流插件，不属于任何单一应用仓库。

## 显式调用

本插件中的所有 Skill 都是 manual-only。普通自然语言请求不会自动启动工作流阶段。知道当前阶段时，直接调用相应 Skill；不确定下一步时调用 `/ask-matt`。

`ask-matt` 读取目标仓库的 `AGENTS.md`、`CLAUDE.md`、相关 `docs/agents/`、项目上下文文档、工作记录和 Git 状态，判断工程阶段后，只推荐一个明确的 Skill 调用及简短原因，然后停止等待用户决定。它不自动调用被推荐 Skill、不执行工作流，也不推进阶段。阶段 Skill 使用 `workflow-*` 前缀，避免与目标环境已有的同名 Skill 冲突。执行时始终以目标仓库的 Agent instructions、Architecture、Domain、Spec、Ticket、CI 和 Git 规则为准。

示例：

```text
/ask-matt
需求已经确定，但还没有正式 Spec，下一步应该做什么？

/workflow-to-spec
把已经确认的需求整理成 Spec
```

Codex 文档中显式调用 Skill 的写法为 `$skill-name`；若当前客户端提供斜杠命令，则可用 `/skill-name`。具体前缀由客户端界面决定。

`setup-engineering-workflow` 是每个仓库手动执行一次的初始化 Skill。`wayfinder` 用于大型、跨模块、跨多个 session 且决策路线不清的工程规划。普通需求澄清由 `workflow-grill-with-docs` 负责。三者与本插件的其他 Skill 一样，均需显式调用。

## 安装

把包含本插件的 marketplace 注册到 Codex 后安装 `engineering-workflow`。如果本机已有同名入口 Skill，先确认替换关系，不要让两套 `ask-matt` 同时生效。

## 设计边界

- 插件本体放在用户级或独立 workflow 仓库，不提交到业务项目；
- 业务项目只保留自己的 `AGENTS.md`、项目文档和实现规则；
- Spec / Ticket 的实际存储媒介由目标仓库决定；
- PR、Auto-merge、部署和真实外部服务操作仍受目标仓库规则与用户授权约束；
- 本插件不自动调用独立 Agent，也不使用双独立审查。
