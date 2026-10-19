# Harness 工具与阶段 Skill 的协作边界

本参考是 `engineering-workflow` 中 Harness CLI 的唯一通用调用说明。阶段 Skill 只在任务与相关工作项已存在、且对应操作适用时引用它；不要求纯咨询或每个小任务都创建状态记录，也不复制某个项目的命令、路径或工作阶段。

## 工具发现和可用性

- 从当前已加载的 `engineering-workflow` Plugin 根目录解析 `tools/harness.py`；命令模板中的 `<engineering-workflow-plugin>` 是占位符。不要从当前 shell 目录、其他仓库、用户缓存或已知机器绝对路径猜 Plugin 位置。
- 从目标仓库实际 `AGENTS.md` / 项目规则读取 adapter 路径、状态目录和工作项 ID。只把能由仓库身份和主记录核实的现有工作项传给 CLI；不为查询新建工作项，不推断授权。
- CLI 不在当前已加载 Plugin 中、adapter / 状态记录缺失、命令失败或格式不支持时，明确报告 `unavailable`、未配置或失败原因。可以继续做授权范围内的普通工程工作，但不能声称 Harness 状态、证据、转换、预算或收尾门禁已通过；不得悄悄改用未安装的源码 checkout 来声称当前会话已经加载新工具。
- Plugin 源码、用户安装副本和当前会话已加载版本是三个不同事实。检查各自实际路径和版本；编辑源码、发现本地 CI 文件或测试通过，都不证明已安装或已在会话生效。不要手改安装缓存或自动安装 / 同步。
- `state`、`diff`、`closeout check`、`closeout recover`、`onboard discover` 和 `onboard plan` 是只读入口。写入状态只经适用的语义命令并提供当前预期摘要；项目文件只经逐文件计划、精确确认和 `onboard apply` 写入。CLI 不执行项目 adapter 中的命令，不读 `.env`，不访问 GitHub。
- 用户明确决定停止工作项时可使用 `cancel`；先核对当前记录、原因、`PRs: None` 和确认来源，再提供当前 SHA。该命令将工作项设为终态 `cancelled`，不代表交付完成，不清理分支 / worktree、不关闭 PR，也不级联变更 Ticket / 关联工作项。确认来源是调用者声明，Harness 不验证用户身份。取消后状态只读。

## 按阶段使用

| 阶段 | 适用操作 | 边界 |
| --- | --- | --- |
| 需求发现、澄清、Spec、设计审查、Ticket 拆分 / Readiness | 已存在对应工作项时只读 `state --json` | 不因纯讨论、咨询或用户未选择的候选创建工作项或授权；项目事实源仍决定内容 |
| TDD、实现 | 开始前读取当前状态和适用 `diff --json`；已确认切片边界时按项目规则捕获 `slice` baseline，完成后重新生成 Diff 与验证证据 | 不重置已有 baseline；只有干净工作树可捕获 `task` baseline；Diff 不展示文件内容 |
| 长时间诊断 / 工具等待 | 对已确认的同一问题创建稳定 `problem-id`，每轮记录假设、检查和结果；等待使用有界 `diagnostic wait/resume`；用 `diagnostic report` 交接 | 到达预算、时间不确定或状态需人工核实时，停止该问题的继续诊断并反馈用户；不通过改名、重复证据或新 ID 清零，也不声称 CLI 会终止外部进程 |
| 实施中的阶段转换 | 仅当目标项目 adapter 存在精确允许的转换且所需证据已经核实，才用 `transition` | 不跳过项目自己的 Spec / Ticket / Review / 授权门禁，不把模型声明标成机器验证，不凭聊天步骤推断已合并 |
| 用户明确停止工作项 | 核对无未处理 PR、原因和用户决定后使用 `cancel` | `cancelled` 不表示完成；保留关联工作项与 Ticket 自身状态，不自动清理工作区或远端 |
| Code Review、交付和任务收尾 | 对当前候选运行 `diff --json`；验证 / Review 后运行 `closeout check`；恢复异常时用只读 `closeout recover` | Diff、测试、PR 或 CI 任一事实均不能单独宣布整体完成；文件语义由 Reviewer 对照权威来源判断 |
| 显式仓库初始化 | 仅由用户手动调用 `setup-engineering-workflow` 后运行 `onboard discover`，再逐文件 `onboard plan` | 展示具体文件 Diff、来源和回退；逐文件取得确认后调用 `onboard apply`；安装 Plugin 不触发初始化 |
| GitHub / 远端门禁 | 只有现有授权读取工具提供结构化快照后，才用 `onboard remote-check` 核对仓库、base、规则来源、required checks 与 observed jobs | 快照声明不等于实时核实；不从绿色 Job 推断它是 required；工具不写 Ruleset / branch protection，不应用、不读回远端 |

## 结果与候选反馈

每次有实际代码 / 文档 / 配置改动的更新，向用户简要说明本轮改动文件、主要增删行为、当前候选风险、已运行与未运行的验证，以及下一步。完整文件级差异以当前 `diff` 为准；将验证或授权绑定到工具给出的候选指纹 / 报告摘要，不用旧候选结果代替新结果。阶段 Skill 原有的用户确认、实施、Review、交付和纯探索边界继续有效。
