---
name: wayfinder
description: "把无法在一个上下文中完成的大型工作拆成可逐个解决的本地决策 Ticket，直到进入 Spec 或实现的路径清晰。"
---

# Wayfinder

Wayfinder（路径规划）用于处理规模大、决策多、当前路线不清晰的工作。它的目标是找到通往 Destination（目标）的路，不是直接冲到目标，更不是替代 `to-spec`、`to-tickets` 或 `implement`。

## 本地地图

地图和决策 Ticket 使用本地 Markdown：

```text
.scratch/<effort-slug>/wayfinder.md
.scratch/<effort-slug>/decisions/<NN>-<slug>.md
```

地图是索引，不是所有决定的存储位置：

- 地图记录 Destination、Notes、已完成决定的简短摘要、尚未明确的区域和 Out of Scope；
- 每个决定的完整问题与结论只存在于对应的决策 Ticket；
- 地图通过相对路径指向决策 Ticket，不使用外部 Issue ID 或 URL；
- Ticket 之间的阻塞关系使用 `Blocked by:`；
- `Status: open / in-progress / done / blocked` 表示本地工作状态；
- `Owner:` 可选，用于多会话时声明当前处理者。

不要把 Wayfinder 地图和实现 Ticket 混为一类：Wayfinder Ticket 解决“需要做出什么决定”，`to-tickets` Ticket 描述“已经决定后要实现什么行为”。

## Plan, don't do

Wayfinder 默认只做规划。每个决策 Ticket 都应该解决一个具体问题，地图在以下条件同时满足时完成：

- Destination 已经清楚；
- 所有开始实现前必须解决的决定已经有结论；
- 不再存在无法表达的关键不确定性；
- 下一步可以交给 `to-spec`、`to-tickets` 或 `implement`。

如果工作已经足够清晰、一个会话可以完成，不要创建 Wayfinder 地图，直接进入合适的下一阶段。

## 使用稳定名称

用户看到的叙述、地图的 Decisions so far 和 Ticket 摘要使用决策名称，不要只说编号。编号和文件路径用于定位，但不能替代人能快速理解的标题。

## 决策 Ticket 类型

每个决策 Ticket 选择一种类型：

- **Research（研究）**：查阅文档、源码、标准或其他高可信资料，以解除一个事实问题；使用 `research`；
- **Prototype（原型）**：用便宜、具体的临时产物验证 UI、逻辑或状态模型；使用 `prototype`；
- **Grilling（澄清）**：通过一次一个问题确认目标、术语、范围或 Contract；使用 `grill-with-docs` 和 `domain-modeling`；
- **Task（人工任务）**：必须由用户完成的访问、配置或手工动作，以便后续做出决定；可使用 `wizard` 生成引导。

Research 可以在不依赖其他决定时独立执行；其他类型默认一次只解决一个决策 Ticket，避免地图在同一会话中失去焦点。

## Fog of war（未知区域）

地图应该有意保持不完整。无法精确表达的问题写进 `Not yet specified`，不要提前伪装成多个 Ticket：

- **Ticket**：现在已经能清楚说出要解决的问题，即使它暂时被阻塞；
- **Not yet specified**：知道大概会遇到某个问题，但还不能准确描述它。

当一个决定完成后，检查它是否让未知区域变得可表达。只有真正可表达的内容才从 `Not yet specified` 变成新的决策 Ticket；可能不会出现 Ticket 的模糊方向继续留在未知区域。

## Out of Scope

Destination 决定范围。超出目标的工作不属于 Fog，而属于 Out of Scope：

- 不将 Out of Scope 内容列入 `Not yet specified`；
- 只有用户明确确认范围外决定后才写入；
- 已经创建但后来被确认超出范围的 Ticket，标记 `Status: done` 并在地图记录排除理由，不删除历史内容；
- 如果未来重新定义 Destination，应建立新的 effort，而不是悄悄恢复旧路线。

## Chart the map：创建地图

用户提出一个过大的模糊想法时：

1. **确认 Destination。** 用 `grill-with-docs` 和 `domain-modeling` 明确最终要得到的 Spec、决定或变更；Destination 决定整个范围。
2. **宽度优先查看未知区域。** 先从多个方向找出决策问题和能立即开始的前置研究，不要深入单一分支后才发现目标错了。
3. **判断是否真的需要地图。** 如果路线已经清楚，直接报告不需要 Wayfinder，并建议进入 `to-spec` 或 `to-tickets`。
4. **用户确认后创建地图。** 写入 Destination、Notes、空的 Decisions so far、Not yet specified 和 Out of Scope。
5. **创建当前可精确描述的决策 Ticket。** 从 `01` 开始编号，按依赖关系填写 `Blocked by:`；无法精确描述的部分留在未知区域。
6. **停止。** 创建地图本身不解决任何决定，也不实现目标。

## Work through the map：推进地图

用户提供地图路径或明确要求继续时：

1. 只读取地图的低分辨率信息，按需读取相关 Ticket；
2. 用户点名 Ticket 时使用指定项，否则选择第一个 `Status: open` 且所有 `Blocked by` 都已 `done` 的 Ticket；
3. 开始工作前将其标记为 `Status: in-progress`，必要时填写 `Owner:`；
4. 只解决当前一个决策，按 Ticket 类型使用 `research`、`prototype`、`grill-with-docs` 或 `wizard`；
5. 将答案写入该 Ticket 的 `## Resolution`，附上事实证据和未决风险；
6. 更新为 `Status: done`，再在地图的 Decisions so far 添加一行摘要和相对路径；
7. 检查哪些未知区域现在可以具体化为新 Ticket，并清除地图中已毕业的模糊描述；
8. 如果决定显示某个 Ticket 超出 Destination，更新 Out of Scope，而不是继续解决它。

同一个会话不要解决多个相互依赖的决策。完成一个后先更新地图，让下一次工作从新的已知状态开始。

## 地图模板

```md
# {Effort 名称}

## Destination

{到达终点的具体定义：要形成的 Spec、要锁定的决定或要完成的变更。}

## Notes

- Domain：{相关领域}
- Skills：{后续会使用的 Skill}
- Constraints：{持续适用的约束}

## Decisions so far

- [{已完成决定名称}](./decisions/{NN}-{slug}.md)：{一句话结论}

## Not yet specified

- {目前知道会遇到，但还不能精确表达的问题}

## Out of Scope

- {明确排除的内容和理由}
```

## 决策 Ticket 模板

```md
# <NN>: <决策名称>

Type: research | prototype | grilling | task
Status: open
Blocked by: None (can start immediately)

## Question

{这个 Ticket 必须解决的一个决定或事实问题。}

## Context

{需要知道的领域、架构和当前事实。}

## Resolution

{完成后填写结论、证据、取舍和未决风险。}
```

## 会话边界

本 Skill 可以创建和更新本地地图、决策 Ticket 及其关系。

本 Skill 不会：

- 创建或查询 GitHub / GitLab Issue；
- 使用外部 tracker 的子 Issue、Label、native blocking 或 frontier 查询；
- 自动实现代码、测试或生产变更；
- 在没有明确决定时创建大量未来 Ticket；
- 自动删除地图、Ticket 或历史决定；
- 把决策 Ticket 当成实现 Ticket。

默认使用中文。Skill 名称、命令名、API、类名、函数名、文件路径、代码和必要的原始术语保持原样。
