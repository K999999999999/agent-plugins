# 架构候选 HTML 报告格式

HTML 报告是可选输出，只在图、调用链或前后结构对比能明显改善理解时使用。报告必须是本地自包含文件：

- 写入操作系统临时目录，不写入仓库；
- 使用本地内联 CSS；
- 不依赖 Tailwind、Mermaid 或其他 CDN；
- 不包含应用代码、凭证或真实敏感数据；
- 默认不打开浏览器，除非用户明确要求预览。

## 基本结构

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <title>代码库架构候选：{仓库名称}</title>
    <style>
      /* 只保留报告所需的本地样式 */
      .seam { stroke-dasharray: 4 4; }
      .leak { stroke: #dc2626; }
      .deep { background: #1e293b; color: white; }
    </style>
  </head>
  <body>
    <main>{报告内容}</main>
  </body>
</html>
```

## 报告内容

标题区域包含仓库名称、日期和图例：

- 实线框：Module；
- 虚线：Seam；
- 红色箭头：跨 Seam 泄漏；
- 深色粗框：Deep Module。

每个候选使用一个卡片，包含：

- **名称**：简短描述要加深的 Module；
- **推荐强度**：`Strong`、`Worth exploring` 或 `Speculative`；
- **依赖类型**：四种依赖分类之一；
- **涉及范围**：相关 Module 或代码区域；
- **Problem**：当前架构摩擦；
- **Solution**：候选的 Deepening 方向；
- **Benefits**：对 Depth、Leverage、Locality 和测试的收益；
- **Before / After**：展示 Shallow Module 和 Deep Module 的结构变化；
- **ADR 提示**：只有确实涉及现有 ADR 冲突或不可逆权衡时显示。

候选阶段只展示方向，不展示最终 Interface 方案。

## 图形选择

根据候选选择最小且最清楚的图形：

- **调用关系图**：展示调用链或 Seam 泄漏；
- **前后结构框**：展示复杂度从调用方集中到 Deep Module；
- **分层截面图**：展示许多浅 Module 合并为一个有真实职责的 Module；
- **接口 / 实现面积图**：展示 Shallow Module 的 Interface 过宽，以及 Deep Module 如何隐藏复杂度；
- **调用树收敛图**：展示多个内部步骤如何收敛到一个外部 Interface。

如果图形无法独立表达问题，应重新设计图形，而不是添加大段解释。不要把每个候选都画成同一种图。

## 语言和术语

报告默认使用中文。架构词汇统一使用：Module、Interface、Implementation、Depth、Deep、Shallow、Seam、Adapter、Leverage、Locality。

领域概念使用项目 `CONTEXT.md` 中的规范术语。不要在模板中写入订单、支付、发货或其他具体行业示例。

收益应具体表达，例如：

- `locality：Bug 集中在一个 Module`；
- `leverage：一个 Interface 服务多个调用方`；
- `interface：调用者不再了解内部步骤`；
- `two adapters：真实环境和测试环境各有一个 Adapter`。

## Top Recommendation

报告末尾只保留一个 Top Recommendation 卡片：候选名称，以及优先探索它的一个原因。不要在报告中直接批准或实施候选。
