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

它包含 10 个 Workflow Skill：`ask-matt`、`workflow-code-review`、`workflow-delivery`、`workflow-design-review`、`workflow-grill-with-docs`、`workflow-implement`、`workflow-tdd`、`workflow-ticket-readiness`、`workflow-to-spec` 和 `workflow-to-tickets`。

迁移时保留了规范的 `.codex-plugin/plugin.json`、Plugin README 和全部 Skill；来源目录下旧的顶层 `plugin.json` 是重复的简化清单，没有复制。

当前活动来源与本机已安装缓存逐文件一致；本次保存的是当前工作版本，不是旧 staging 或旧备份。

## 发布前待确认

- 仓库许可证尚未选择。
- `engineering-workflow` 的 manifest 当前标记为 `Proprietary`，作者为 `Local Workflow Maintainer`。公开发布前需要确认它的实际作者、改写来源和发布许可证，并按确认结果更新元数据。
- `setup-matt-pocock-skills` 的名称包含外部人物名称。公开发布前需要确认它是本人的独立实现、允许的改写，或补充必要的来源和许可证说明。
- 其他 Skill 也应在公开发布前确认没有混入第三方受限内容、真实凭证或项目私有数据。
