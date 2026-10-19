# 证据与 GitHub 只读核验

核验实际执行时读取。使用已有只读工具或已登录的 `gh`；不登录新账号、不扩大权限、不输出 Token，不触发工作流或修改远端配置。

## 证据记录

每条门禁记录：目标分支 / 环境、规则目的、规则类别（机械 / 设计 / 高风险）、定义位置、执行身份、可修改者、触发范围、失败行为、绕过者、证据版本与时间。

以下五项独立记录为“成立 / 不成立 / 未验证 / 不适用”，附来源，不是可以自动继承的成熟度分数：

| 证据项 | 足够支持的材料 | 不能据此推断 |
| --- | --- | --- |
| 文档声称存在 | 规范、Skill、AGENTS.md 的具体位置 | 已配置或强制执行 |
| 配置定义存在 | 脚本、测试、YAML 或远端规则定义 | 当前目标适用、失败会阻断 |
| 实际被强制执行 | 生效规则、分支匹配、可信检查来源与执行资格逻辑 | 已观察过失败阻断 |
| 有历史运行证据 | 对应版本的 run / check / review / merge 记录 | 最新代码也通过或失败不能合并 |
| 已验证阻断能力 | 与当前控制相容的失败案例和真实阻断记录，或获授权的隔离试验 | 所有绕过身份和新配置都安全 |

每条证据绑定仓库、HEAD / PR head SHA、base SHA 或合并组 SHA、配置版本、来源 URL / 文件行号、采集时间、命令 / API 与脱敏结果。解释 PR head、测试合并提交和最终提交的对应关系；提交 ID 不同不直接认定失配，但无法建立映射时不能当作当前组合证明。

项目依赖外部 `agent-plugins`、Skill、Plugin 或其他工程规则来源时，核对实际 Marketplace 注册来源、源 checkout 的仓库 / 分支 / HEAD、GitHub 默认分支版本、当前安装 / 缓存版本、项目引用及实际加载 / 执行证据是否一致。版本号不足以区分内容时使用 Commit 或内容摘要；区分尚未合入默认分支、安装滞后和当前会话未重新加载，不仅比较版本字符串，也不因 Squash 后 SHA 不同就判定内容不同。将来源、版本对应关系及差异记录在现有矩阵的“证据 / 缺口”中。无法访问的环节明确标为未验证并说明原因，不得将源仓库规则直接当成当前生效规则，也不能仅凭安装存在认定实际执行。审计不自动更新 Plugin 或手工修改缓存。

任务生命周期证据应同时绑定长期工作记录、项目定义的实时状态与相应 Git / PR / 验证事实。运行现有状态检查后仍需核对其检查边界和 REVIEW / 警告；退出 0、工作区干净或 CI 全绿都不能单独证明复盘、文档同步与收尾已完成。收集期间状态发生变化时重新读取受影响记录，撤销已被新证据解决的发现，保留各次证据的时间与基线。

对读取范围、分页、截断和历史保留期限做记录。对审计采用的关键成功 / 失败 / 跳过 / 门禁变更案例说明选择依据；历史案例可按风险选择，不代表所有历史已审阅。15 个领域仍须全部覆盖。

## 远端核验路径

从 Git remote 确认实际托管仓库和主机，不输出含凭证的 URL。用户有多个远端时依据实际 PR 目标及默认分支确认，不能把 Fork 的规则当成上游规则。GitHub Enterprise 使用对应 host；非 GitHub 项目查询其等价平台控制，没有访问能力标记未验证。

以下是只读查询示例，占位值须替换为已确认事实；优先使用当前环境已有工具。REST 列表按端点支持的分页方式获取，GraphQL connection 继续游标分页，不能把第一页当全部。单对象端点不盲加 `--paginate`。

```bash
gh repo view --json nameWithOwner,defaultBranchRef,url
gh api repos/OWNER/REPO/rulesets --paginate
gh api repos/OWNER/REPO/rulesets/RULESET_ID
gh api repos/OWNER/REPO/rules/branches/BRANCH
gh api repos/OWNER/REPO/branches/BRANCH/protection
gh pr list --state all --limit 50 --json number,title,headRefOid,baseRefName,mergedAt,url
gh pr view NUMBER --json headRefOid,baseRefName,reviewDecision,reviews,statusCheckRollup,mergeStateStatus,autoMergeRequest,url
gh api repos/OWNER/REPO/pulls/NUMBER/reviews --paginate
gh api repos/OWNER/REPO/commits/SHA/check-runs --paginate
gh api repos/OWNER/REPO/commits/SHA/status
gh run list --limit 50
gh run view RUN_ID --log-failed
```

`--limit 50` 只是首批历史窗口，应按风险继续读取关键记录并披露范围。分支名中的 `/` 等字符按 API 路径正确编码。404 可能源于权限隐藏、端点不支持或确实不存在；401 / 403、缺字段、访问组织规则失败均须保留原因，不能直接写“未保护”。API 结构因平台而异，必要时读取当前平台帮助或官方文档。

## 生效配置与合并记录

- Rulesets 要检查 enforcement、目标分支条件、继承的组织规则、规则详情及 bypass actor / mode；仅列出仓库规则名称不够。分支生效规则和传统 Branch Protection 都要核对。
- Required Checks 核对 context、预期 App / integration、触发事件、作业实际结果、最新 SHA、缺失或跳过的处理。不能把状态名称相同视为来源可信。
- 分别记录实际 required checks 与其他成功检查；成功检查总数不能当作 required checks 数量，也不能证明本机状态检查已在远端执行。
- Reviews 核对作者与审查者、CODEOWNERS 的强制要求、最后推送后的审批、过期审批、讨论解决、管理员与自动化例外。可用时读取实际合并资格状态及历史合并事件。
- 沿历史 PR 的改动、Reviews、workflow run、check suite / run、状态与合并提交关联起来，查验失败 / 取消 / 未执行时的实际行为，以及检查成功后目标分支是否又变更。
- 检查自动合并由平台还是机器人执行，机器人使用何身份、是否调用管理员 bypass，是否验证风险分类及组合代码；merge queue 要追踪合并组与相应工作流。
- 远端工作流与本地 YAML 版本可能不同；使用相应 Commit 的定义解释历史运行。PR 页全绿和 `mergeable` 状态均不能单独证明所有门禁可信。

## 阻断能力与安全停止

优先查找已有失败、修正和被阻断的历史案例，并确认当时控制与当前配置是否相容。只看到失败日志不证明合并被阻止；找不到失败案例也不证明门禁无效。

尚未实证的关键阻断点记录“未验证”，提出可在隔离仓库、无秘密和低权限环境验证的最小方案，例如让所需检查失败 / 跳过、目标分支移动或门禁被修改，观察合并资格。方案属于建议，本 Skill 默认不执行、不创建 PR、不切换保护设置。未验证项影响关键自动合并判断时不得给出无条件 READY。
