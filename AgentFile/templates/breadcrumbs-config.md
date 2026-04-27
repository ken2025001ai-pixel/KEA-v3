# KEA × Breadcrumbs 配置指南

> 本文档说明如何在 KEA Ontology 中使用 Breadcrumbs 插件建立**语义化链接网络**。
>
> **关键原则**：语义关系的**单一真相源**是 YAML front matter 中的 `relations` 字段，由知识萃取 Agent 自动生成。Breadcrumbs 和 Indexer 都从中消费。

---

## 关系数据的三个层级

KEA 中关系数据按优先级分层：

| 层级 | 存储位置 | 生成方式 | 消费者 |
|------|---------|---------|--------|
| **L1: 结构化关系** | YAML front matter `relations` | **Agent 自动生成** | Indexer、Validator、Codegen |
| **L2: 语义链接** | Dataview inline fields (`uses::`) | 用户/Agent 可选补充 | Breadcrumbs、Dataview |
| **L3: 普通链接** | 正文 `[[链接]]` | 用户/Agent 自然写入 | Obsidian Backlinks、Graph View |

**设计原则**：
- **Agent 提取时**自动填充 L1（`relations`），确保机器可解析
- **正文**中保留 L3（`[[链接]]`），确保人类可读和 Backlinks 工作
- **L2** 是可选增强，用于 Breadcrumbs Matrix View 的可视化

---

## L1: YAML `relations` 字段（主要）

知识萃取 Agent 在生成文档时自动填充：

```yaml
---
type: logic
domain: 订单管理
tags: [kea-logic]
relations:
  - {target: "用户", type: "uses", description: "输入数据"}
  - {target: "订单", type: "produces", description: "输出数据"}
  - {target: "扣减库存", type: "calls", description: "触发动作"}
  - {target: "支付流程", type: "precedes", description: "前置流程"}
---
```

**关系类型规范**：

| 类型 | 适用文档 | 语义 |
|------|---------|------|
| `uses` | logic/action | 使用/输入 |
| `produces` | logic/action | 产生/输出 |
| `supports` | logic | 支撑数据 |
| `calls` | logic | 调用动作 |
| `triggers` | logic | 触发动作（异步） |
| `precedes` | logic | 前置流程 |
| `follows` | logic | 后续流程 |
| `part_of` | object/logic/action | 属于某个领域/逻辑 |
| `contains` | domain/object | 包含 |
| `belongs_to` | object | 归属 |
| `has` | object | 拥有 |
| `references` | object | 引用 |
| `modifies` | action | 修改数据 |

Indexer 会自动从 `relations` 构建关系图，无需额外操作。

---

## L2: Dataview Inline Fields（可选增强）

如果你安装了 **Breadcrumbs** 插件，可以在正文中用 inline fields 增强可视化：

```markdown
# 与对象的关联

- 输入数据的对象：[[用户]]、[[订单]]
- 输出数据的对象：[[订单]]

uses:: [[用户]], [[订单]]
produces:: [[订单]]
```

Breadcrumbs 会识别这些字段并在 **Matrix View** 中展示。

### Breadcrumbs Edge Fields 配置

Breadcrumbs Settings → Edge Fields：

| Breadcrumbs 位置 | Edge Field 名称 | 说明 |
|-----------------|----------------|------|
| ↑ Up | `part_of` | 属于 |
| ↓ Down | `contains` | 包含 |
| ← Same | `related` | 相关 |
| → Next | `follows` | 后续 |
| ← Prev | `precedes` | 前置 |

**额外字段**（添加到 Same 位置）：
- `uses`, `produces`, `calls`, `modifies` — 在 Matrix View 中显示为同级关系

### Matrix View 效果示例

打开 `创建订单.md` 的 Matrix View：

```
           ↑ part_of
      [[订单管理域]]

← precedes          follows →
  [[审批订单]]        [[支付流程]]

           ↓ contains
        (无)

Same: uses → [[用户]], [[订单]]
Same: produces → [[订单]]
Same: calls → [[扣减库存]]
```

---

## L3: 普通 Wikilinks（基础）

正文中的 `[[链接]]` 是 Obsidian 的基础能力：

```markdown
# 与对象的关联
- 输入数据的对象：[[用户]]、[[订单]]
- 输出数据的对象：[[订单]]
```

功能：
- ✅ Obsidian Backlinks 面板显示引用关系
- ✅ Graph View 显示连接（配合 tags 分组着色）
- ❌ 无关系类型信息（所有边看起来一样）

---

## 配置检查清单

### 最小配置（不装任何插件也能用）

- [ ] 知识萃取 Agent 自动填充 YAML `relations`
- [ ] 正文中保留 `[[链接]]` 供人类阅读
- [ ] Graph View Groups 按 tag 着色（`kea-object`/`kea-logic`/`kea-action`）

### 推荐配置（安装 Dataview + Breadcrumbs）

- [ ] 安装 Dataview 插件
- [ ] 安装 Breadcrumbs 插件
- [ ] Breadcrumbs Settings 中配置 Edge Fields（见上文）
- [ ] 在正文中添加语义 inline fields（`uses:: [[对象]]`）
- [ ] 运行 "Breadcrumbs: Rebuild Graph"
- [ ] 使用 "Breadcrumbs: Open Matrix View" 查看关系矩阵

---

## 常见问题

**Q: 为什么 `relations` 和 inline fields 都要维护？信息不重复吗？**

A: `relations` 是**机器消费**的结构化数据（Indexer/Validator/Codegen 用它），inline fields 是**人类可视化**的辅助（Breadcrumbs Matrix View 用它）。Agent 提取时只写 `relations`，inline fields 可选补充。Indexer 会合并所有来源去重。

**Q: 不装 Breadcrumbs 会影响 KEA 工作流吗？**

A: **不会**。Breadcrumbs 是纯粹的**阅读增强**插件。KEA 的核心流水线（extract → validate → trace → codegen）完全依赖 `relations` 和 `[[链接]]`，不需要 Breadcrumbs。

**Q: 已有的大量旧文档没有 `relations` 字段怎么办？**

A: 运行 `/ontology-index`，Indexer 会从正文 `[[链接]]` 反向推断关系。然后可以批量补充 YAML `relations`（未来可由 Agent 自动完成）。
