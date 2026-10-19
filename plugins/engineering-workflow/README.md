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

## Harness 状态工具

`tools/harness.py` 是标准库 Python 3 CLI，用于读取项目当前工作项状态、记录运行情况，以及按项目 adapter 校验阶段转换。项目必须显式提供仓库内的 `.harness/project.json`；Plugin 安装不会创建或修改它。Adapter 只保存 JSON 阶段 / 转换规则和 Git 公共目录内长期状态记录的相对位置，不执行其中的 shell 或 Python 代码。

```bash
python3 <engineering-workflow-plugin>/tools/harness.py --project-root <repo> state --work-item <id> --json
python3 <engineering-workflow-plugin>/tools/harness.py --project-root <repo> migrate --work-item <id> --expected-sha <record-sha256>
python3 <engineering-workflow-plugin>/tools/harness.py --project-root <repo> capture-baseline --work-item <id> --scope task --expected-sha <record-sha256>
python3 <engineering-workflow-plugin>/tools/harness.py --project-root <repo> capture-baseline --work-item <id> --scope slice --expected-sha <record-sha256>
python3 <engineering-workflow-plugin>/tools/harness.py --project-root <repo> diff --work-item <id> --json
python3 <engineering-workflow-plugin>/tools/harness.py --project-root <repo> attest-evidence --work-item <id> --expected-sha <record-sha256> --evidence-json '<typed-json-object>'
python3 <engineering-workflow-plugin>/tools/harness.py --project-root <repo> transition --work-item <id> --to '验证 / Review' --next '<next-step>' --expected-sha <record-sha256> --evidence-json '<typed-json-array>'
python3 <engineering-workflow-plugin>/tools/harness.py --project-root <repo> set-runtime --work-item <id> --status waiting-user --reason '<reason>' --expected-sha <record-sha256>
python3 <engineering-workflow-plugin>/tools/harness.py --project-root <repo> diagnostic start --work-item <id> --problem-id <stable-id> --title '<problem>' --expected-sha <record-sha256>
python3 <engineering-workflow-plugin>/tools/harness.py --project-root <repo> diagnostic record --work-item <id> --problem-id <stable-id> --hypothesis '<why>' --action '<check>' --result '<safe-summary>' --expected-sha <record-sha256>
python3 <engineering-workflow-plugin>/tools/harness.py --project-root <repo> diagnostic wait --work-item <id> --problem-id <stable-id> --reason '<bounded wait>' --seconds 300 --expected-sha <record-sha256>
python3 <engineering-workflow-plugin>/tools/harness.py --project-root <repo> diagnostic resume --work-item <id> --problem-id <stable-id> --expected-sha <record-sha256>
python3 <engineering-workflow-plugin>/tools/harness.py --project-root <repo> diagnostic alias --work-item <id> --problem-id <stable-id> --alias <renamed-id> --expected-sha <record-sha256>
python3 <engineering-workflow-plugin>/tools/harness.py --project-root <repo> diagnostic decision --work-item <id> --problem-id <stable-id> --decision continue --reason '<user decision>' --verified-by user --source '<chat reference>' --expected-sha <record-sha256>
python3 <engineering-workflow-plugin>/tools/harness.py --project-root <repo> diagnostic report --work-item <id> --problem-id <stable-id>
```

`state --json` 返回当前生命周期、阶段、运行状态、下一步、授权摘要、记录摘要、证据类别和 Git common directory。没有 adapter 时明确返回 `connected: false`，不能作为新版 Harness 已通过的证据。只读查询不改文件、不读 `.env`、不访问网络，也不执行 adapter 命令。

任务基线由 Agent 显式捕获：`task` 起点要求 Git 工作树、index 和未跟踪文件干净，且同一工作项不能重置；`slice` 记录上个行为切片的当前候选。`diff` 汇总两条基线以来的提交、staged、unstaged 和未跟踪文件，并单独报告 base 分支移动。候选指纹绑定仓库 / 工作项、分支、HEAD、base SHA、Git index、工作树变更和路径分类规则版本。Diff 只输出安全路径、状态和风险类别，不输出文件内容；默认敏感模式包括 `.env`、私钥 / 证书及常见 secret / token 文件名，项目可在 adapter 增补。被忽略文件不会被枚举或读取。敏感或不可读变更会使 Diff 标为不完整，不能登记候选证据。

候选验证或聊天审批通过 `attest-evidence` 关联当前 `candidate_fingerprint`，可同时绑定 `report_sha256` 和外部输入身份。附带 `git_snapshot` 的远端检查快照必须与本地仓库、HEAD、base ref / SHA 相同，且本地 index、工作树和未跟踪文件干净；工具核对的是身份，不验证远端来源或检查结论，依据仍按声明处理。快照身份摘要随证据保存，之后明确显示“需要复核”。记录继续显示实施范围授权与候选批准两项独立事实；任何 HEAD、base、index、工作树、分类规则或报告变化都会使相应旧依据过期。该命令只接受人工声明或未验证依据；它不能伪造 `machine-verified`。Candidate transition 只有在 adapter 显式设置 `candidate_required` 时，才要求提交绑定当前指纹的必需证据。

当前 Markdown 状态记录的既有顶层字段仍是其事实源；新运行数据写入单个版本化扩展块。旧记录只读识别，`migrate` 必须带读取到的完整 SHA-256，并在原子更新前按原摘要保留一份备份。转换需要最新摘要、adapter 明确允许的阶段边，以及带来源、核实人、仓库、主题、覆盖、采集时间和核实方式的 JSON 依据。`unverified` 依据不能满足必需项；CLI 自述不能标成 `machine-verified`，只有实际采集器执行核验后才能生成此类依据。每次写入使用工作项锁和同目录原子替换；摘要冲突、锁已存在、格式未知或转换非法均非零退出且不覆盖记录。遗留锁不会自动删除，需人工核实其归属及原记录后处理。

运行状态与项目生命周期阶段分开保存，可表达 `running`、`waiting-tool`、`waiting-ci`、`waiting-user`、`blocked`、`paused`、`idle` 和 `unknown`。工具只校验经过它的状态转换；它不阻止通过其他 Shell / Git 命令绕行，也不提供后台监控或进程强制停止。

同一故障的跨会话诊断预算使用稳定 `problem-id` 保存。先记录 `diagnostic start`，每轮通过 `diagnostic record` 提交原因假设、验证动作和结果；只有引用未重复、仍绑定当前候选的 `attested` 依据才计实质进展。连续3轮无进展或连续诊断累计1800秒任一触发后，继续记录诊断会被拒绝；`state` 和 `diagnostic report` 仍可查看，`attest-evidence` 仍可登记新依据，用户决定可通过 `diagnostic decision` 留痕。相同 ID / 标题不能重新开预算；同一故障改名时须用 `diagnostic alias` 指向原问题。工具不猜测两个不同标题的语义是否相同，需由 Agent 保持同一 ID 或显式登记别名。

`diagnostic wait` / `resume` 用于有起止的正常等待或暂停，单次最多3600秒。等待过期、时钟回拨或历史区间不可核实会标记需人工核实；用户明确决定继续后才开启下一段预算，原轮次、累计耗时和未知时间保留。`diagnostic report` 汇总当前候选及累计 / 本轮 Diff、尝试与失败结果、未知项和剩余预算 / 需人工决定的下一步成本。`diagnostic decision` 只记录决定来源声明，不验证用户身份；只有收到用户明确指示后才能登记继续。记录只接受安全摘要，不保存 Secret；工具只门控经 CLI 提交的诊断，不会终止已运行命令或自动撤销改动。

每个接入项目可以在 adapter 声明 `dynamic_file_manifest`，指向仓库内 JSON 清单，列出每项动态文件的稳定 ID、路径、Owner、权威来源、更新触发条件和历史记录位置，以及参与收尾的 Ticket、关联子工作项和是否要求远端交付。缺少清单会明确报告未配置并阻止完成；不会推测某仓库有哪些动态文件。文件清单变化属于候选变化，必须重新核对受影响文件；若清单本身在当前 Diff 中变化，还需单独登记 `manifest-review` 语义 Review。

```json
{
  "schema_version": 1,
  "delivery_required": true,
  "files": [
    {
      "id": "agent-rules",
      "path": "AGENTS.md",
      "owner": "工程负责人",
      "authority": "AGENTS.md 与 docs/agents/documentation.md",
      "triggers": ["工作流门禁或 Agent 协作规则改变"],
      "history_path": ".scratch/<work-item>/history.md"
    }
  ],
  "tickets": [{"id": "01", "path": ".scratch/<work-item>/issues/01-example.md"}],
  "child_work_items": ["<related-work-item-id>"]
}
```

完成前运行 `closeout check`。每个清单文件都必须通过 `closeout record-file` 留下 `updated`、`reviewed-no-change` 或 `not-applicable` 结论、理由和语义 Review 摘要；`updated` 还必须出现在本工作项累计 Diff。工具核对路径、摘要、Manifest、候选、Ticket 的 `Status: done` 与非空 `Result:`、关联工作项状态、未解决诊断、当前候选验证和 Code Review。结构校验不代表工具理解了文档语义，Reviewer 对“未变化 / 不适用”的结论仍是显式人工声明。

```bash
python3 <engineering-workflow-plugin>/tools/harness.py --project-root <repo> closeout check --work-item <id>
python3 <engineering-workflow-plugin>/tools/harness.py --project-root <repo> closeout record-file --work-item <id> --file-id agent-rules --disposition updated --reason '<what changed>' --reviewer '<reviewer>' --review-summary '<authority and applicability checked>' --expected-sha <record-sha256>
python3 <engineering-workflow-plugin>/tools/harness.py --project-root <repo> closeout finalize --work-item <id> --scope local --recorded-by '<reviewer>' --reason '<local candidate is complete>' --expected-sha <record-sha256>
python3 <engineering-workflow-plugin>/tools/harness.py --project-root <repo> closeout finalize --work-item <id> --scope overall --recorded-by '<reviewer>' --reason '<overall lifecycle is complete>' --expected-sha <record-sha256>
python3 <engineering-workflow-plugin>/tools/harness.py --project-root <repo> closeout recover --work-item <id>
```

本地完成与总体完成分别记录。`local` 不会把顶层状态改为 `done`；`overall` 只有在所有本地门禁满足，且清单要求的远端授权、PR 身份、Review、Merge 和清理证据均与当前候选一致时，才会将其设为 `done`。远端证据通过状态工具记录为 `attested` 声明；本地工具不会访问 GitHub 或验证远端事实。完成摘要还绑定 Ticket、关联工作项、诊断、维护记录和相关证据；这些状态后续变化时，`state` 会将旧完成记录标为失效，避免只看未变化的 Git Diff 而保留假完成。

`closeout recover` 是只读恢复视图：核对当前仓库 / worktree / HEAD、候选 Diff、状态主记录及关联记录，并标出未知或损坏。它不修复记录、不选择另一个主记录、不继承关联工作授权，也不删除用户改动；记录损坏或归属不明时应先保留现场并由人决定如何恢复。

Harness 自身复盘通过 `maintenance open` 记录具体缺口、分类、Owner、授权范围、验收标准、处置动作、替代覆盖、历史去向和复查触发条件。暂缓必须说明理由及复查触发；关闭必须引用与当前候选和报告一致的 `maintenance-effect` attested 依据。仅新增规则或登记 follow-up 不算效果验证；候选变化后旧效果证据会过期并重新阻止收尾。

项目初始化必须显式运行 `onboard discover`。它只读取 Git 身份、Agent instructions、已知栈标记、声明的测试入口、CI 文件摘要和当前改动路径；不执行项目命令、不读取 `.env`，不把 CI 文件存在 / Job 成功说成远端 required check。栈、测试命令和覆盖均作为待人工确认的观察值；未知项目不会生成测试命令或空壳绿色 Job。

本地文件通过 `onboard plan` 先展示单文件 Diff。请求使用 JSON stdin，指定目标路径、完整目标内容以及从发现 / 检查中读到的旧文件 SHA-256；新文件使用 `null`。计划身份绑定仓库、HEAD、分支、文件系统对象、旧摘要和新内容摘要。只有用户已确认的精确路径才可通过 `onboard apply` 写入；应用前重核计划和文件身份，拒绝路径越界、符号链接、敏感路径、未提交用户改动和计划后并发变化。写入使用同目录临时文件、原子替换和读回核验，重复执行相同内容只报告 `already-present`。原来干净且受 Git 跟踪的文件可从 Git 恢复；新文件的删除需要人工复核，工具不自动回滚或清理。

```bash
python3 <engineering-workflow-plugin>/tools/harness.py --project-root <repo> onboard discover
python3 <engineering-workflow-plugin>/tools/harness.py --project-root <repo> onboard plan --request-stdin <<'JSON'
{"schema_version":1,"path":"docs/agent-workflow.md","content":"# Confirmed rules\n","expected_sha256":null}
JSON
python3 <engineering-workflow-plugin>/tools/harness.py --project-root <repo> onboard apply --request-stdin --plan-fingerprint <sha256-from-plan> --confirm-path docs/agent-workflow.md <<'JSON'
{"schema_version":1,"path":"docs/agent-workflow.md","content":"# Confirmed rules\n","expected_sha256":null}
JSON
```

可选的 `remote_plan` 必须列出目标仓库、已核实 required checks 的来源、strict 更新目标和回退计划；没有真实检查来源时拒绝把空列表当绿色门禁。计划只展示为 `proposed-not-applied`，Plugin 没有远端写入能力。`onboard remote-check` 校验外部工具提供的 GitHub 快照与本地 origin / 可用 base ref 身份，分别列出 branch-protection 或 repository-ruleset 来源、required checks 与成功 Job，并核对 Job 的来源 App、head SHA 和结论。它不访问 GitHub；`attested` 仍是输入来源的声明，`complete` 保持 false，直到外部授权读取 / 应用 / 读回流程留下可核验证据。权限不足、错仓库、base 过期、规则缺失或只看到其他成功 Job 时都不能报告远端完成。其他托管平台明确返回 unsupported，不套用 GitHub 语义。

Plugin 仓库的 [Harness tests workflow](../../.github/workflows/harness-tests.yml) 从当前源码运行 Python 3.11 标准库回归，关闭依赖缓存，不连接模型、业务库或远端规则读取服务。新增 workflow 文件和本地回归通过只证明候选配置 / 代码就绪；本分支尚无托管 CI run，且 workflow 不会自动把 Job 加入 GitHub required checks，也不修改 branch protection。

## 安装

把包含本插件的 marketplace 注册到 Codex 后安装 `engineering-workflow`。如果本机已有同名入口 Skill，先确认替换关系，不要让两套 `ask-matt` 同时生效。

## 设计边界

- 插件本体放在用户级或独立 workflow 仓库，不提交到业务项目；
- 业务项目只保留自己的 `AGENTS.md`、项目文档和实现规则；
- Spec / Ticket 的实际存储媒介由目标仓库决定；
- PR、Auto-merge、部署和真实外部服务操作仍受目标仓库规则与用户授权约束；
- 跨仓库记录由目标工作流指定唯一主记录和关联记录；清理 feature worktree 不应删除仍需恢复的记录。若要同步本机 Plugin / Skill，先核实 marketplace 来源、源 checkout 与安装缓存，再使用受支持的同步方式；不要手工修改安装缓存，也不要清理仍在使用的源 checkout；
- 本插件不自动调用独立 Agent，也不使用双独立审查。
