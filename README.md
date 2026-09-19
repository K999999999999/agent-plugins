# Agent Engineering Skills

一个用于保存和分发个人 Codex 工程工作流 Skill（技能）的 Plugin（插件）仓库。

## 范围

本仓库只管理个人维护的 Skill，不复制 Codex 官方内置 Skill、Plugin 缓存、账号配置或运行时状态。

当前 Plugin：`agent-engineering-skills`

包含的 Skill：

- `codebase-design`：Module、Interface、Seam 和 Adapter 设计
- `diagnosing-bugs`：Bug、失败和性能回归诊断
- `domain-modeling`：领域术语、上下文和 ADR
- `improve-codebase-architecture`：架构摩擦和 Deep Module 改进候选
- `maintainability-refactor`：最小范围的可维护性重构
- `prototype`：逻辑、状态模型、数据形状和 UI 原型验证
- `research`：一手资料研究和本地证据记录
- `resolving-merge-conflicts`：Merge / Rebase 冲突处理
- `setup-matt-pocock-skills`：本地 Spec、Ticket 和领域文档配置
- `triage`：本地工作项分类和状态整理
- `wayfinder`：大型工作的决策 Ticket 拆分
- `wizard`：需要用户本人操作的交互式本地向导

这些 Skill 默认采用显式调用策略（例如 `$triage`、`$wizard`）。不要把仓库中的个人工程约定误认为 Codex 官方标准。

## 目录

```text
plugins/agent-engineering-skills/
├── .codex-plugin/plugin.json
└── skills/
    └── <skill-name>/
        ├── SKILL.md
        └── agents/openai.yaml
```

仓库级 Marketplace（插件市场）清单位于 `.agents/plugins/marketplace.json`。

## 本地使用

从仓库根目录将这个仓库注册为本地 Marketplace：

```text
codex plugin marketplace add "E:\Kaifa\project 2026\agent-plugins"
codex plugin add agent-engineering-skills@personal
```

更新 Plugin 内容后，应在新 Thread（会话）中测试，确保 Codex 重新加载 Skill 和工具。

## 验证

每个 Skill 都应通过 `skill-creator` 的 `quick_validate.py`；完整 Plugin 应通过 `plugin-creator` 的 `validate_plugin.py`。中文文件在 Windows 上验证时使用 Python UTF-8 模式：

```text
python -X utf8 <skill-creator>/scripts/quick_validate.py <skill-path>
python -X utf8 <plugin-creator>/scripts/validate_plugin.py plugins/agent-engineering-skills
```

包含 Bash 模板的 Skill 还应执行 `bash -n <script>`；向导脚本不要在验证时自动端到端运行，因为它们需要人工输入。

## 发布边界

当前仓库尚未选择开源许可证。确定许可证和各 Skill 的来源/归属后，再将仓库公开发布或 Push 到远程仓库。
