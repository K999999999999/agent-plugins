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

迁移时保留了规范的 `.codex-plugin/plugin.json`、Plugin README 和全部 Skill；来源目录下旧的顶层 `plugin.json` 是重复的简化清单，没有复制。

迁移时活动来源与本机已安装缓存逐文件一致；此后本仓库独立演进，当前不能据此推断它仍与来源或缓存相同。

## 发布前待确认

- 仓库许可证尚未选择。
- `engineering-workflow` 的 manifest 当前标记为 `Proprietary`，作者为 `Local Workflow Maintainer`。公开发布前需要确认它的实际作者、改写来源和发布许可证，并按确认结果更新元数据。
- 仓库内 Skill 的来源、改写范围和分发权限仍需在公开发布前逐项确认。
- 其他 Skill 也应在公开发布前确认没有混入第三方受限内容、真实凭证或项目私有数据。
