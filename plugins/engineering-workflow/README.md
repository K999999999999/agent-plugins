# Engineering Workflow

这是一个用户级、通用的 Codex 工程工作流插件，不属于任何单一应用仓库。

## 显式调用

本插件中的所有 Skill 都是 manual-only。普通自然语言请求不会自动启动工作流阶段。目标仓库可以在自己的 `AGENTS.md` 中规定每个新会话自动检查工作区和恢复状态；该行为由目标仓库规则驱动，不依赖本插件自动调用 Skill。知道阶段时直接调用相应 Skill；只有主动询问“下一步是什么”时，才可选调用 `/ask-matt`。

`ask-matt` 读取目标仓库的 `AGENTS.md`、`CLAUDE.md`、相关 `docs/agents/`、项目上下文文档、工作记录和 Git 状态，判断工程阶段后，只推荐一个明确的 Skill 调用及简短原因，然后停止等待用户决定。它不是工程任务必经入口，不自动调用被推荐 Skill、不执行工作流，也不推进阶段。阶段 Skill 使用 `workflow-*` 前缀，避免与目标环境已有的同名 Skill 冲突。执行时始终以目标仓库的 Agent instructions、Architecture、Domain、Spec、Ticket、CI 和 Git 规则为准。

流程区分三个入口：

- **需求发现**（`workflow-discovery`）：知道问题 / 机会，但尚无候选目标；探索现状、证据、候选结果和取舍。
- **需求澄清**（`workflow-grill-with-docs`）：已有候选目标，但影响结果的重要行为、范围、边界或验收仍不明确。
- **阶段导航**（`ask-matt`）：用户主动询问目前阶段或下一步时，只推荐一个 Skill 并停止。

发现和澄清是不同阶段；需要哪个就显式调用哪个。两者都不会自动创建实施 Spec / Ticket 或进入实现。

示例：

```text
/ask-matt
需求已经确定，但还没有正式 Spec，下一步应该做什么？

/workflow-to-spec
把已经确认的需求整理成 Spec
```

Codex 文档中显式调用 Skill 的写法为 `$skill-name`；若当前客户端提供斜杠命令，则可用 `/skill-name`。具体前缀由客户端界面决定。

`setup-engineering-workflow` 是每个仓库手动执行一次的初始化 Skill。`wayfinder` 用于大型、跨模块、跨多个 session 且决策路线不清的工程规划。需求发现和需求澄清分别由 `workflow-discovery` 和 `workflow-grill-with-docs` 负责。它们与本插件的其他 Skill 一样，均需显式调用。

## 安装

把包含本插件的 marketplace 注册到 Codex 后安装 `engineering-workflow`。如果本机已有同名入口 Skill，先确认替换关系，不要让两套 `ask-matt` 同时生效。

## 设计边界

- 插件本体放在用户级或独立 workflow 仓库，不提交到业务项目；
- 业务项目只保留自己的 `AGENTS.md`、项目文档和实现规则；
- Spec / Ticket 的实际存储媒介由目标仓库决定；
- PR、Auto-merge、部署和真实外部服务操作仍受目标仓库规则与用户授权约束；
- 本插件不自动调用独立 Agent，也不使用双独立审查。
