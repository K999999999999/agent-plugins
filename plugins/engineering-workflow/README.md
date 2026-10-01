# Engineering Workflow

这是一个用户级、通用的 Codex 工程工作流插件，不属于任何单一应用仓库。

## 阶段 Skill 调用

需求发现、需求澄清、Spec、设计审查、Ticket 拆分 / Readiness、TDD、实现、Code Review 和交付共十个阶段 Skill 可在用户请求确实进入相应阶段时由主 Agent 隐式调用。用户不必用斜杠命令逐阶段启动。普通问答、仅探索或仅整理 Spec 的请求不会因此自动扩展为实现或发布。

允许阶段 Skill 隐式调用只改变 Skill 的调用方式，不构成新的授权，也不会跳过用户确认：完整 Spec、Ticket 拆分、关键行为 / 技术决定、实施范围和 Push / PR 发布仍按目标仓库规则处理。用户已授权整个目标时，Agent 可按依赖在当前上下文连续推进，不逐 Ticket 请求选择或继续。

`ask-matt` 读取目标仓库的 `AGENTS.md`、`CLAUDE.md`、相关 `docs/agents/`、项目上下文文档、工作记录和 Git 状态，判断工程阶段后，只推荐一个明确的 Skill 调用及简短原因，然后停止等待用户决定。它不是工程任务必经入口，不自动调用被推荐 Skill、不执行工作流，也不推进阶段。阶段 Skill 使用 `workflow-*` 前缀，避免与目标环境已有的同名 Skill 冲突。执行时始终以目标仓库的 Agent instructions、Architecture、Domain、Spec、Ticket、CI 和 Git 规则为准。

流程区分三个入口：

- **需求发现**（`workflow-discovery`）：知道问题 / 机会，但尚无候选目标；探索现状、证据、候选结果和取舍。
- **需求澄清**（`workflow-grill-with-docs`）：已有候选目标，但影响结果的重要行为、范围、边界或验收仍不明确。
- **阶段导航**（`ask-matt`）：用户主动询问目前阶段或下一步时，只推荐一个 Skill 并停止。

发现和澄清是不同阶段；由任务当前状态决定调用哪个。Skill 本身不会编造目标或用户决定。只有用户目标覆盖继续，且后续阶段授权 / 确认门禁都满足时，主 Agent 才继续调用下一阶段。

示例：

```text
/workflow-discovery
我发现这个流程经常让人忘记上次做到哪儿，但还不确定怎么改。

/workflow-grill-with-docs
我想在每次新会话开始时恢复上次工作，但恢复规则还没定。

/ask-matt
需求已经确定，但还没有正式 Spec，下一步应该做什么？

/workflow-to-spec
把已经确认的需求整理成 Spec
```

Codex 文档中显式调用 Skill 的写法为 `$skill-name`；若当前客户端提供斜杠命令，则可用 `/skill-name`。具体前缀由客户端界面决定。

`ask-matt` 仅在用户主动询问阶段 / 下一步时由用户显式调用；它只推荐一个 Skill 并停止。`setup-engineering-workflow` 是每个仓库手动执行一次的初始化 Skill。**仅安装 Plugin 不会修改项目文件，也不会产生自动会话入口**；新项目需要显式调用初始化 Skill，检查现有约定并由用户确认文件清单，才能将适配后的会话入口和状态恢复规则写入项目级 Agent instructions。`wayfinder` 是需要明确启动的大型、跨模块、跨多个 session 工程规划入口。需求发现和需求澄清分别由阶段路由判断，专项 agent-engineering-skills 仍为手动能力。

需求形成 Contract 后，`workflow-to-spec` 按仓库约定与风险产出短 Spec 或完整 Spec：短 Spec 按项目规则判断用户明确的小任务是否已构成实施授权；完整 Spec 必须经用户确认，再进入设计审查、Ticket 拆分和 Readiness 门禁。

## 安装

把包含本插件的 marketplace 注册到 Codex 后安装 `engineering-workflow`。如果本机已有同名入口 Skill，先确认替换关系，不要让两套 `ask-matt` 同时生效。

## 设计边界

- 插件本体放在用户级或独立 workflow 仓库，不提交到业务项目；
- 业务项目只保留自己的 `AGENTS.md`、项目文档和实现规则；
- Spec / Ticket 的实际存储媒介由目标仓库决定；
- PR、Auto-merge、部署和真实外部服务操作仍受目标仓库规则与用户授权约束；
- 跨仓库记录由目标工作流指定唯一主记录和关联记录；清理 feature worktree 不应删除仍需恢复的记录。若要同步本机 Plugin / Skill，先核实 marketplace 来源、源 checkout 与安装缓存，再使用受支持的同步方式；不要手工修改安装缓存，也不要清理仍在使用的源 checkout；
- 本插件不自动调用独立 Agent，也不使用双独立审查。
