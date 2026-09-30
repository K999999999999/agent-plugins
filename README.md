# Agent Engineering Skills

一个用于保存和分发个人 Codex 工程工作流 Skill（技能）的 Plugin（插件）仓库。

## 范围

本仓库只管理个人维护或明确纳入管理的 Plugin，不复制 Codex 官方内置 Skill、Plugin 缓存、账号配置或运行时状态。

当前有两个职责独立的 Plugin：

- `engineering-workflow`：完整软件工程工作流，包含路由、阶段处理、大型工程规划和仓库工作流初始化；
- `agent-engineering-skills`：可以脱离主流程单独使用的工程专项能力。

### `engineering-workflow`（13 个 Skill）

- `ask-matt`：用户主动询问阶段或下一步时，推荐一个 Skill 后停止；
- `setup-engineering-workflow`：每个仓库手动初始化一次，检查并复用仓库约定；
- `wayfinder`：手动规划大型、跨模块、跨多个 session 且路线未明确的工程目标；
- `workflow-discovery`：从问题 / 机会中探索候选目标；
- `workflow-grill-with-docs`：澄清已有候选目标的重要歧义；
- `workflow-to-spec`、`workflow-design-review`、`workflow-to-tickets`、`workflow-ticket-readiness`；
- `workflow-tdd`、`workflow-implement`、`workflow-code-review`、`workflow-delivery`。

### `agent-engineering-skills`（9 个 Skill）

- `codebase-design`：Module、Interface、Seam 和 Adapter 设计
- `diagnosing-bugs`：Bug、失败和性能回归诊断
- `domain-modeling`：领域术语、上下文和 ADR
- `improve-codebase-architecture`：架构摩擦和 Deep Module 改进候选
- `maintainability-refactor`：最小范围的可维护性重构
- `prototype`：逻辑、状态模型、数据形状和 UI 原型验证
- `research`：一手资料研究和本地证据记录
- `resolving-merge-conflicts`：Merge / Rebase 冲突处理
- `wizard`：需要用户本人操作的交互式本地向导

## 调用方式：Explicit Skill Invocation

本仓库的 22 个 Skill 全部采用显式调用（manual-only）：普通自然语言请求不会自动启动其中任何 Skill。知道当前要做什么时，直接调用对应 Skill；尚无候选目标时可调用 `/workflow-discovery` 探索，已有候选目标但重要歧义未解时可调用 `/workflow-grill-with-docs` 澄清。只有主动询问当前阶段或下一步时，才调用 `/ask-matt` 获取建议。目标仓库的 `AGENTS.md` 可以独立驱动新会话状态检查与播报，这不等于自动调用本插件 Skill。

`ask-matt` 只在用户主动请求导航时判断阶段、推荐一个明确的 Skill 名称并简述原因，然后停止。它不会自动调用被推荐的 Skill；用户需要自行显式启动下一步。

示例：

```text
/diagnosing-bugs
排查登录接口 500

/workflow-to-spec
把已经确认的需求整理成 Spec

/workflow-code-review
Review 当前已经实现完成的代码

/research
研究 LangGraph checkpoint 的官方实现方式
```

Codex 文档中的显式调用示例使用 `$skill-name`；若当前客户端将 Skill 暴露为斜杠命令，可使用 `/skill-name`。两种写法指向同一 Skill，具体前缀取决于客户端界面。调用策略以每个 Skill 的 `agents/openai.yaml` 中 `policy.allow_implicit_invocation` 为准，均须为 `false`。

## 目录

```text
plugins/
├── engineering-workflow/
│   ├── .codex-plugin/plugin.json
│   └── skills/<workflow-skill>/SKILL.md
└── agent-engineering-skills/
    ├── .codex-plugin/plugin.json
    └── skills/<capability-skill>/SKILL.md
```

仓库级 Marketplace（插件市场）清单位于 `.agents/plugins/marketplace.json`。

## 本地使用

从仓库根目录将这个仓库注册为本地 Marketplace：

```text
codex plugin marketplace add "E:\Kaifa\project 2026\agent-plugins"
codex plugin add agent-engineering-skills@personal
codex plugin add engineering-workflow@personal
```

更新 Plugin 内容后，应在新 Thread（会话）中测试，确保 Codex 重新加载 Skill 和工具。

## 验证

当前 22 个 Skill 都应通过 `skill-creator` 的 `quick_validate.py`；两个 Plugin 都应通过 `plugin-creator` 的 `validate_plugin.py`。中文文件在 Windows 上验证时使用 Python UTF-8 模式：

```text
python -X utf8 <skill-creator>/scripts/quick_validate.py <skill-path>
python -X utf8 <plugin-creator>/scripts/validate_plugin.py plugins/agent-engineering-skills
python -X utf8 <plugin-creator>/scripts/validate_plugin.py plugins/engineering-workflow
```

包含 Bash 模板的 Skill 还应执行 `bash -n <script>`；向导脚本不要在验证时自动端到端运行，因为它们需要人工输入。

## 发布边界

当前仓库尚未选择统一的开源许可证。`engineering-workflow` 保留了当前活动 Plugin 的 `Proprietary` 标记；确定两个 Plugin 的来源、归属和发布范围后，再将仓库公开发布或 Push 到远程仓库。
