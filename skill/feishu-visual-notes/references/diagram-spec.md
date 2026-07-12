# Diagram Specification

Read this reference whenever a Feishu note needs an editable diagram. Build a UTF-8 JSON specification, render it with `scripts/build_feishu_diagram.py`, and validate the SVG with `scripts/validate_svg_layout.py` before inserting it.

## Selection

| Relationship | Type | Variants | `auto` selection |
|-|-|-|-|
| Ordered stages or iteration | `flow` | `horizontal`, `vertical`, `loop` | Up to 5 nodes uses horizontal; 6-7 uses vertical; `closed_loop: true` uses loop |
| Hierarchy or classification | `knowledge-map` | `radial`, `layered` | `levels` uses layered; otherwise radial |
| Events or lifecycle | `timeline` | `linear`, `alternating` | Up to 4 events uses linear; 5-7 uses alternating |
| Multi-dimensional comparison | `matrix` | `comparison` | Uses comparison |
| Conditional choice | `decision` | `branch` | Uses branch |
| Multi-role handoff | `swimlane` | `lanes` | Uses horizontal lanes |
| Progressive filtering or conversion | `funnel` | `descending` | Uses a descending funnel |
| Two-axis classification | `quadrant` | `2x2` | Uses a four-quadrant field |
| Root-cause analysis | `cause-effect` | `fishbone` | Uses a fishbone structure |

Use `variant: "auto"` unless the source relationship clearly requires a specific variant. Do not choose a variant merely for novelty.

## Common Fields

```json
{
  "type": "flow",
  "variant": "auto",
  "canvas": "auto",
  "title": "评测项目流程",
  "subtitle": "从需求确认到结果交付"
}
```

Node fields:

```json
{
  "id": "dataset",
  "title": "构建评测集",
  "body": "覆盖典型场景与边界案例",
  "accent": "blue",
  "parent": "requirement",
  "meta": "第 2 周"
}
```

Allowed accents: `blue`, `green`, `orange`, `red`, `purple`, `gray`.

`canvas` accepts `auto`, `square`, or `wide`. Use `auto` for Feishu; it centers the content on a square canvas to match Feishu whiteboard previews. Use `wide` only when the user explicitly prefers a 16:9 working area.

## Type Fields

### Flow

```json
{"type":"flow","variant":"auto","title":"执行流程","nodes":["确认目标","准备数据","执行评测","输出报告"]}
```

Use 2-7 nodes. Set `closed_loop: true` and optionally `center_label` for an iterative loop.

### Knowledge Map

Radial:

```json
{"type":"knowledge-map","title":"能力地图","center":"核心能力","branches":["需求分析","数据构建","质量评估","结果表达"]}
```

Layered:

```json
{"type":"knowledge-map","title":"知识层级","levels":[[{"id":"root","title":"课程主题"}],[{"title":"方法","parent":"root"},{"title":"案例","parent":"root"}]]}
```

Use 3-7 radial branches or 2-4 levels with 1-5 nodes per level.

### Timeline

```json
{"type":"timeline","title":"项目周期","events":[{"title":"启动","meta":"第 1 周"},{"title":"试标","meta":"第 2 周"},{"title":"交付","meta":"第 4 周"}]}
```

Use 2-7 events.

### Matrix

```json
{"type":"matrix","title":"方案对比","columns":["维度","方案 A","方案 B"],"rows":[["成本","低","中"],["准确性","中","高"]]}
```

Use 2-4 columns and 1-5 rows. Each row must have one value per column.

### Decision

```json
{"type":"decision","title":"方法选择","question":{"title":"数据是否充足？","body":"先判断证据基础"},"options":[{"title":"充足","body":"进入定量评测"},{"title":"不足","body":"先补充样本"}]}
```

Use 2-4 options.

### Swimlane

```json
{"type":"swimlane","title":"协作流程","lanes":[{"title":"业务方","steps":["提出需求","验收结果"]},{"title":"评测方","steps":["设计方案","执行评测","输出报告"]}]}
```

Use 2-4 lanes and 1-5 steps per lane.

### Funnel

```json
{"type":"funnel","title":"数据筛选","stages":["原始数据","规则过滤","人工复核","有效样本"]}
```

Use 3-6 stages.

### Quadrant

```json
{"type":"quadrant","title":"任务优先级","quadrants":[{"title":"重要紧急","body":"立即处理"},{"title":"重要不紧急","body":"计划推进"},{"title":"不重要紧急","body":"授权处理"},{"title":"不重要不紧急","body":"减少投入"}]}
```

Provide exactly four quadrants. Optionally add `axis_labels` with `top`, `bottom`, `left`, and `right`.

### Cause and Effect

```json
{"type":"cause-effect","title":"问题归因","effect":{"title":"结果偏低","body":"定位根因"},"causes":[{"title":"数据","items":["覆盖不足","分布偏差"]},{"title":"规则","items":["阈值不清"]},{"title":"执行","items":["理解不一致"]}]}
```

Use 3-6 cause categories and up to three concise items per category.

## Commands

```powershell
python scripts/build_feishu_diagram.py --input diagram.json --output diagram.svg
python scripts/validate_svg_layout.py --input diagram.svg --strict
```

Insert the result as `<whiteboard type="svg" path="@diagram.svg"></whiteboard>` or inline SVG. Keep `diagram.json` and `diagram.svg` in the command working directory when using `@file` paths.
