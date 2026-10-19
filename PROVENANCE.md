# Provenance（来源记录）

本次初始化从本机以下用户 Skill 目录复制了 12 个 Skill：

```text
C:\Users\Administrator\.codex\skills\
```

没有复制以下内容：

- `C:\Users\Administrator\.codex\skills\.system` 下的官方/系统 Skill；
- `C:\Users\Administrator\.codex\plugins\cache` 下的缓存内容；
- Codex 账号、配置、Hook、数据库、日志或其他运行时状态。

## `engineering-workflow` Plugin

第二个 Plugin 从当前 Codex 正在使用的完整来源复制：

```text
C:\Users\Administrator\.codex\workflows\engineering-workflow\plugins\engineering-workflow
```

迁移时它包含 10 个 Workflow Skill。之后从专项能力包迁入 `wayfinder` 和仓库初始化能力，并将后者重命名为 `setup-engineering-workflow`；当前 Workflow Plugin 共 12 个 Skill：`ask-matt`、`setup-engineering-workflow`、`wayfinder`、`workflow-code-review`、`workflow-delivery`、`workflow-design-review`、`workflow-grill-with-docs`、`workflow-implement`、`workflow-tdd`、`workflow-ticket-readiness`、`workflow-to-spec` 和 `workflow-to-tickets`。

初始的专项能力包从 12 个 Skill 调整为当前 9 个：保留独立能力，迁入 2 个 Workflow Skill，并移除 1 个不符合当前使用场景的 Skill。

迁移时保留了规范的 `.codex-plugin/plugin.json`、Plugin README 和全部 Skill；来源目录下旧的顶层 `plugin.json` 是重复的简化清单，没有复制。迁移记录中的 12 个 Skill 是历史数量；当前 `engineering-workflow` 目录有 13 个 Skill，包含 `workflow-discovery`。此处迁移记录不代表当前安装版本或会话加载状态。

迁移时活动来源与本机已安装缓存逐文件一致；此后本仓库独立演进，当前不能据此推断它仍与来源或缓存相同。

## 分发与元数据确认

2026-10-19，仓库维护者确认本文件记录的 Skill 来源与改写范围准确，相关内容有权继续公开分发。`engineering-workflow` 的 Plugin manifest 保留作者 `Local Workflow Maintainer` 和许可证标记 `Proprietary`；仓库没有统一的开源许可证，本次不新增开源许可或改变其他 Plugin 的许可证元数据。

本确认记录沿用已登记的迁移来源，不表示当前安装缓存与本仓库仍然同步。公开分发前仍须确保提交中不包含真实凭证或项目私有数据。
